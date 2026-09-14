import re

import requests
from incidentbot.configuration.settings import settings
from incidentbot.exceptions import IndexNotFoundError
from incidentbot.incident.automations import run as run_automations
from incidentbot.incident.core import format_channel_name
from incidentbot.incident.event import EventLogHandler
from incidentbot.incident.status import (
    apply_status_change,
    build_postmortem_title,
    is_final,
)
from incidentbot.logging import logger
from incidentbot.models.database import ApplicationData, engine
from incidentbot.models.incident import IncidentDatabaseInterface
from incidentbot.models.slack import User
from incidentbot.slack.client import (
    get_digest_channel_id,
    get_formatted_channel_history,
    get_slack_user,
    slack_web_client,
)
from incidentbot.slack.messages import (
    BlockBuilder,
    IncidentChannelDigestNotification,
    IncidentUpdate,
)
from incidentbot.util import gen
from slack_sdk.errors import SlackApiError
from sqlmodel import Session, select

err_msg = ":robot_face::heart_on_fire: I've run into a problem processing commands for this incident: I cannot find it in the database. Let an administrator know about this error."


def _refresh_roles_panel(channel_id: str) -> None:
    """
    Update the live roles panel message in the incident channel.

    Reads the stored message timestamp from ApplicationData, rebuilds the
    block payload with current participant data, and calls chat_update.
    Silently no-ops if no panel TS is found (e.g. older incidents or Matrix).
    """
    try:
        with Session(engine) as session:
            entry = session.exec(
                select(ApplicationData).filter(
                    ApplicationData.name == f"role_panel_{channel_id}"
                )
            ).first()

        if not entry or not entry.json_data:
            return

        ts = entry.json_data.get("ts")
        if not ts:
            return

        incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)
        if not incident:
            return

        participants = IncidentDatabaseInterface.list_participants(incident=incident)

        slack_web_client.chat_update(
            channel=channel_id,
            ts=ts,
            blocks=BlockBuilder.roles_panel(
                incident=incident, participants=participants
            ),
            text="Role assignments for this incident.",
        )
    except Exception as error:
        logger.exception("error refreshing roles panel", channel_id=channel_id, error=error)


def _get_channel_topic(channel_id: str) -> list[str]:
    """Fetch and split the current channel topic into its pipe-delimited segments."""
    return [
        item.strip()
        for item in slack_web_client.conversations_info(channel=channel_id)
        .get("channel")
        .get("topic")
        .get("value")
        .split("|")
    ]


def _get_existing_postmortem_link(incident_id: int) -> str | None:
    existing = IncidentDatabaseInterface.get_postmortem(parent=incident_id)
    if existing and existing.url:
        return existing.url
    return None


def _is_confluence_postmortem_link(postmortem_link: str | None) -> bool:
    if not postmortem_link:
        return False

    confluence_base_url = None
    if (
        settings.integrations
        and settings.integrations.atlassian
        and settings.integrations.atlassian.confluence
    ):
        confluence_base_url = getattr(
            settings.integrations.atlassian.confluence, "url", None
        )

    if not isinstance(confluence_base_url, str) or not confluence_base_url:
        fallback = getattr(settings, "ATLASSIAN_API_URL", None)
        confluence_base_url = fallback if isinstance(fallback, str) else None

    if confluence_base_url and confluence_base_url in postmortem_link:
        return True

    return "/wiki/" in postmortem_link and "atlassian.net" in postmortem_link


def _extract_confluence_page_id(postmortem_link: str) -> str | None:
    patterns = [
        r"/pages/(\d+)",
        r"pageId=(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, postmortem_link)
        if match:
            return match.group(1)
    return None


def _load_workspace_records(record_name: str) -> list[dict]:
    try:
        with Session(engine) as session:
            record = session.exec(
                select(ApplicationData).filter(ApplicationData.name == record_name)
            ).first()
            if record and isinstance(record.json_data, list):
                return record.json_data
    except Exception as error:
        logger.exception(
            "error loading workspace record for pinned-content parsing", record_name=record_name, error=error
        )
    return []


def _parse_pinned_message_content(message: str) -> str:
    channel_pattern = r"<#([A-Z0-9]+)\|?.*?>"
    username_pattern = r"<@([A-Z0-9]+)>"

    channels = _load_workspace_records("slack_channels")
    users = _load_workspace_records("slack_users")
    channel_lookup = {
        item.get("id"): item.get("name")
        for item in channels
        if item.get("id") and item.get("name")
    }
    user_lookup = {
        item.get("id"): item.get("real_name")
        for item in users
        if item.get("id") and item.get("real_name")
    }

    def replace_channel(match: re.Match) -> str:
        channel_id = match.group(1)
        name = channel_lookup.get(channel_id)
        return f"#{name}" if name else match.group(0)

    def replace_user(match: re.Match) -> str:
        user_id = match.group(1)
        real_name = user_lookup.get(user_id)
        return f"@{real_name}" if real_name else match.group(0)

    message = re.sub(channel_pattern, replace_channel, message)
    message = re.sub(r"<(https?://[^|>]+)\|[^>]+>", r"\1", message)
    message = re.sub(r"<(https?://[^>]+)>", r"\1", message)
    message = re.sub(username_pattern, replace_user, message)
    return message


def _build_existing_pin_event_keys(incident) -> set[tuple[str, str, str, str]]:
    keys = set()
    timeline = EventLogHandler.read(incident_id=incident.id) or []

    for item in timeline:
        if item.source != "pin":
            continue
        message_ts = item.message_ts or ""
        if item.image is not None:
            keys.add(("image", message_ts, item.title or "", item.mimetype or ""))
        else:
            keys.add(("text", message_ts, item.text or "", ""))

    return keys


def _message_has_pin_marker(message: dict) -> bool:
    if message.get("pinned_to"):
        return True
    reactions = message.get("reactions") or []
    for reaction in reactions:
        if reaction.get("name") == settings.pin_content_reacji:
            return True
    return False


def _is_postmortem_announcement_message(message: dict) -> bool:
    blocks = message.get("blocks") or []
    for block in blocks:
        elements = block.get("elements") if isinstance(block, dict) else None
        if not isinstance(elements, list):
            continue
        for element in elements:
            if (
                isinstance(element, dict)
                and element.get("action_id") == "view_postmortem"
            ):
                return True
    return False


def _resolve_pinned_event_user(message: dict) -> str:
    user_id = message.get("user")
    if isinstance(user_id, str) and user_id:
        user = get_slack_user(user_id)
        if user and isinstance(user, dict):
            return user.get("real_name", user_id)
        return user_id
    return "NotAvailable"


def _download_pinned_image(file: dict) -> bytes | None:
    file_id = file.get("id")
    file_name = file.get("name") or file.get("title") or "unknown"
    url_private = file.get("url_private")

    if not file_id or not url_private:
        logger.error("pinned file is missing required metadata", file_name=file_name)
        return None

    made_public = False
    if not file.get("public_url_shared") and getattr(settings, "SLACK_USER_TOKEN", None):
        try:
            slack_web_client.files_sharedPublicURL(
                file=file_id,
                token=settings.SLACK_USER_TOKEN,
            )
            made_public = True
        except SlackApiError as error:
            logger.exception("error preparing pinned file for copy", file_name=file_name, error=error)

    try:
        params = None
        permalink_public = file.get("permalink_public")
        if isinstance(permalink_public, str):
            parts = permalink_public.split("-")
            if len(parts) > 3:
                params = {"pub_secret": parts[3]}

        response = requests.get(
            url_private,
            headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.content
    except Exception as error:
        logger.exception("error downloading pinned file", file_name=file_name, error=error)
        return None
    finally:
        if made_public:
            try:
                slack_web_client.files_revokePublicURL(
                    file=file_id,
                    token=settings.SLACK_USER_TOKEN,
                )
            except SlackApiError as error:
                logger.exception(
                    "error revoking public url for pinned file", file_name=file_name, error=error
                )


def _upsert_pinned_message_event(
    incident,
    message: dict,
    existing_keys: set[tuple[str, str, str, str]],
) -> int:
    created = 0
    message_ts = message.get("ts")
    if not isinstance(message_ts, str) or not message_ts:
        return created

    event_user = _resolve_pinned_event_user(message)

    files = message.get("files") or []
    if files:
        if not settings.enable_pinned_images:
            return created

        for file in files:
            mimetype = file.get("mimetype")
            if not isinstance(mimetype, str) or "image" not in mimetype:
                continue

            title = (
                file.get("name") or file.get("title") or file.get("id") or "pinned-image"
            )
            title = str(title)
            key = ("image", message_ts, title, mimetype)
            if key in existing_keys:
                continue

            content = _download_pinned_image(file)
            if content is None:
                continue

            EventLogHandler.create(
                image=content,
                incident_id=incident.id,
                incident_slug=incident.slug,
                message_ts=message_ts,
                mimetype=mimetype,
                source="pin",
                title=title,
                user=event_user,
            )
            existing_keys.add(key)
            created += 1

        return created

    raw_text = message.get("text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        return created

    parsed_text = _parse_pinned_message_content(raw_text).strip()
    if not parsed_text:
        return created

    key = ("text", message_ts, parsed_text, "")
    if key in existing_keys:
        return created

    EventLogHandler.create(
        event=parsed_text,
        incident_id=incident.id,
        incident_slug=incident.slug,
        message_ts=message_ts,
        source="pin",
        user=event_user,
    )
    existing_keys.add(key)
    return created + 1


def _list_channel_messages(channel_id: str) -> list[dict]:
    messages = []
    cursor = None

    while True:
        params = {"channel": channel_id, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        response = slack_web_client.conversations_history(**params)
        messages.extend(response.get("messages") or [])
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not response.get("has_more") or not cursor:
            break

    return messages


def _backfill_pinned_content_from_channel(incident) -> dict[str, int]:
    try:
        messages = _list_channel_messages(incident.channel_id)
    except Exception as error:
        logger.exception(
            "unable to scan channel history for pinned-content backfill", channel=incident.channel_name, error=error
        )
        return {"messages_scanned": 0, "pin_candidates": 0, "events_created": 0}

    existing_keys = _build_existing_pin_event_keys(incident)
    pin_candidates = 0
    events_created = 0

    for message in messages:
        if not _message_has_pin_marker(message):
            continue
        if _is_postmortem_announcement_message(message):
            continue
        pin_candidates += 1
        events_created += _upsert_pinned_message_event(
            incident=incident,
            message=message,
            existing_keys=existing_keys,
        )

    logger.info(
        "pinned-content backfill complete",
        channel=incident.channel_name,
        scanned=len(messages),
        candidates=pin_candidates,
        created=events_created,
    )

    return {
        "messages_scanned": len(messages),
        "pin_candidates": pin_candidates,
        "events_created": events_created,
    }


def _build_postmortem_message_blocks(postmortem_link: str) -> list[dict]:
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "{} Incident Postmortem".format(
                    settings.icons.get(settings.platform).get("postmortem"),
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "A starter postmortem has been composed based on "
                + "data gathered during this incident.",
            },
        },
        {
            "block_id": "buttons",
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Postmortem"},
                    "style": "primary",
                    "url": postmortem_link,
                    "action_id": "view_postmortem",
                },
            ],
        },
    ]


def _announce_postmortem(incident, postmortem_link: str):
    try:
        result = slack_web_client.chat_postMessage(
            channel=incident.channel_id,
            blocks=_build_postmortem_message_blocks(postmortem_link),
            text=postmortem_link,
        )
        slack_web_client.pins_add(
            channel=incident.channel_id,
            timestamp=result.get("ts"),
        )
    except SlackApiError as error:
        logger.exception("error sending postmortem update to incident channel", error=error)


def _create_confluence_postmortem(
    incident, participants, timeline, title: str
) -> str | None:
    if not (
        settings.integrations
        and settings.integrations.atlassian
        and settings.integrations.atlassian.confluence
        and settings.integrations.atlassian.confluence.enabled
    ):
        return None

    from incidentbot.confluence.postmortem import IncidentPostmortem

    try:
        return IncidentPostmortem(
            incident=incident,
            participants=participants,
            timeline=timeline,
            title=title,
        ).create()
    except Exception as error:
        logger.exception("error creating confluence postmortem", error=error)
        return None


def _create_gitlab_postmortem(
    incident, participants, timeline, title: str
) -> str | None:
    if not (
        settings.integrations
        and settings.integrations.gitlab
        and settings.integrations.gitlab.enabled
    ):
        return None

    from incidentbot.gitlab.postmortem import IncidentPostmortem

    try:
        return IncidentPostmortem(
            incident=incident,
            participants=participants,
            timeline=timeline,
            title=title,
        ).create()
    except Exception as error:
        logger.exception("error creating gitlab postmortem", error=error)
        return None


def _create_new_postmortem(incident) -> str | None:
    participants = IncidentDatabaseInterface.list_participants(incident=incident)
    timeline = EventLogHandler.read(incident_id=incident.id)
    title = build_postmortem_title(incident)

    providers = (
        ("Confluence", _create_confluence_postmortem),
        ("GitLab", _create_gitlab_postmortem),
    )

    for provider_name, creator in providers:
        link = creator(incident, participants, timeline, title)
        if link:
            logger.info(
                "created postmortem",
                provider=provider_name,
                channel=incident.channel_name,
                url=link,
            )
            return link

    return None


def _get_or_create_postmortem_link(incident) -> str | None:
    existing_link = _get_existing_postmortem_link(incident.id)
    if existing_link:
        return existing_link

    postmortem_link = _create_new_postmortem(incident)
    if not postmortem_link:
        return None

    IncidentDatabaseInterface.add_postmortem(parent=incident.id, url=postmortem_link)

    EventLogHandler.create(
        event="Postmortem generated",
        incident_id=incident.id,
        incident_slug=incident.slug,
        source="system",
    )

    _announce_postmortem(incident, postmortem_link)

    return postmortem_link


def _sync_confluence_postmortem(incident, postmortem_link: str) -> bool:
    if not _is_confluence_postmortem_link(postmortem_link):
        return False

    page_id = _extract_confluence_page_id(postmortem_link)
    if not page_id:
        logger.error(
            "unable to parse confluence page id from postmortem url", url=postmortem_link
        )
        return False

    from incidentbot.confluence.postmortem import IncidentPostmortem

    participants = IncidentDatabaseInterface.list_participants(incident=incident)
    timeline = EventLogHandler.read(incident_id=incident.id)

    postmortem = IncidentPostmortem(
        incident=incident,
        participants=participants,
        timeline=timeline,
        title=build_postmortem_title(incident),
    )

    return postmortem.sync(page_id=page_id)


def _send_postmortem_message(channel_id: str, postmortem_link: str) -> None:
    """
    Post a postmortem-ready notification to the incident channel and update
    the digest message to surface the postmortem link as a button.
    Called after auto-creating a postmortem on incident resolution.
    """
    incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)
    if not incident:
        return

    try:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=f"A postmortem has been automatically created: {postmortem_link}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":memo: A postmortem has been automatically created.",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Postmortem", "emoji": True},
                            "url": postmortem_link,
                            "style": "primary",
                            "action_id": "view_postmortem",
                        }
                    ],
                },
            ],
        )
    except SlackApiError as error:
        logger.exception("error posting postmortem message", channel_id=channel_id, error=error)

    try:
        slack_web_client.chat_update(
            channel=get_digest_channel_id(),
            ts=incident.digest_message_ts,
            blocks=IncidentChannelDigestNotification.update(
                channel_id=incident.channel_id,
                has_private_channel=incident.has_private_channel,
                incident_components=incident.components,
                incident_description=incident.description,
                incident_impact=incident.impact,
                incident_slug=incident.slug,
                meeting_link=incident.meeting_link,
                severity=incident.severity,
                status=incident.status,
                postmortem_link=postmortem_link,
            ),
            text="The digest message has been updated.",
        )
    except SlackApiError as error:
        logger.exception(
            "error updating digest with postmortem link", channel=incident.channel_name, error=error
        )


async def generate_postmortem(channel_id: str) -> str | None:
    incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)
    if not incident:
        slack_web_client.chat_postMessage(channel=channel_id, text=err_msg)
        return None

    backfill_result = _backfill_pinned_content_from_channel(incident)
    if backfill_result["events_created"] > 0:
        EventLogHandler.create(
            event=(
                f"Backfilled {backfill_result['events_created']} pinned item(s) "
                + "from channel history"
            ),
            incident_id=incident.id,
            incident_slug=incident.slug,
            source="system",
        )

    postmortem_link = _get_or_create_postmortem_link(incident)
    if not postmortem_link:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text="Unable to generate a postmortem. Check configuration and logs.",
        )
        return None

    try:
        slack_web_client.chat_update(
            channel=get_digest_channel_id(),
            ts=incident.digest_message_ts,
            blocks=IncidentChannelDigestNotification.update(
                channel_id=incident.channel_id,
                has_private_channel=incident.has_private_channel,
                incident_components=incident.components,
                incident_description=incident.description,
                incident_impact=incident.impact,
                incident_slug=incident.slug,
                meeting_link=incident.meeting_link,
                severity=incident.severity,
                status=incident.status,
                postmortem_link=postmortem_link,
            ),
            text="The digest message has been updated.",
        )
    except SlackApiError as error:
        logger.exception(
            "error sending postmortem update to digest", channel=incident.channel_name, error=error
        )

    return postmortem_link


async def sync_postmortem(channel_id: str) -> bool:
    incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)
    if not incident:
        slack_web_client.chat_postMessage(channel=channel_id, text=err_msg)
        return False

    postmortem_link = _get_existing_postmortem_link(incident.id)
    if not postmortem_link:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text="No postmortem exists yet. Generate one first.",
        )
        return False

    if not (
        settings.integrations
        and settings.integrations.atlassian
        and settings.integrations.atlassian.confluence
        and settings.integrations.atlassian.confluence.enabled
    ):
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text="Confluence integration is not enabled for sync.",
        )
        return False

    if not _is_confluence_postmortem_link(postmortem_link):
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text="Pinned-content sync is only supported for Confluence postmortems.",
        )
        return False

    backfill_result = _backfill_pinned_content_from_channel(incident)
    if backfill_result["events_created"] > 0:
        EventLogHandler.create(
            event=(
                f"Backfilled {backfill_result['events_created']} pinned item(s) "
                + "from channel history"
            ),
            incident_id=incident.id,
            incident_slug=incident.slug,
            source="system",
        )

    synced = _sync_confluence_postmortem(incident=incident, postmortem_link=postmortem_link)
    if not synced:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text="Unable to synchronize pinned content to the postmortem.",
        )
        return False

    EventLogHandler.create(
        event="Synchronized pinned content to postmortem",
        incident_id=incident.id,
        incident_slug=incident.slug,
        source="system",
    )

    sync_message = "Pinned content has been synchronized to the postmortem."
    if backfill_result["events_created"] > 0:
        sync_message += (
            f" Backfilled {backfill_result['events_created']} "
            + "pinned item(s) from channel history first."
        )

    slack_web_client.chat_postMessage(channel=channel_id, text=sync_message)
    return True


"""
Functions for handling inbound actions
"""


async def archive_incident_channel(
    channel_id: str,
):
    """
    Archives the channel passed in based on its channel_id

    Parameters:
        channel_id (str): Incident channel_id
    """

    incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)

    if incident:
        try:
            logger.info("archiving channel", channel=incident.channel_name)
            result = slack_web_client.conversations_archive(
                channel=incident.channel_id
            )
            logger.debug(result)
        except SlackApiError as error:
            logger.exception("error archiving channel", channel=incident.channel_name, error=error)
        finally:
            # Write event log
            EventLogHandler.create(
                event="The incident channel was archived",
                incident_id=incident.id,
                incident_slug=incident.slug,
                source="system",
            )
    else:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=err_msg,
        )


async def export_chat_logs(channel_id: str, user: str):
    """
    Fetches channel history, formats it, and returns it to the channel

    Parameters:
        channel_id (str): Incident channel_id
        user (str): The user who exported the logs
    """

    incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)

    if incident:
        # Retrieve channel history and post as text attachment
        history = get_formatted_channel_history(
            channel_id=incident.channel_id,
            channel_name=incident.channel_name,
        )
        try:
            logger.info("sending chat transcript", channel=incident.channel_name)
            result = slack_web_client.files_upload_v2(
                channel=incident.channel_id,
                content=history,
                filename=f"{incident.channel_name} Chat Transcript.txt",
                initial_comment="As requested, here is the chat transcript. Remember"
                + " - while this is useful, it will likely need cultivation before "
                + "being added to a postmortem.",
                title=f"{incident.channel_name} Chat Transcript",
            )
            logger.debug("file upload result", result=result)
        except SlackApiError as error:
            logger.exception(
                "error sending message and attachment", channel=incident.channel_name, error=error
            )
        finally:
            # Write event log
            EventLogHandler.create(
                event=f"Incident channel text log was exported by {user}",
                incident_id=incident.id,
                incident_slug=incident.slug,
                source="system",
            )
    else:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=err_msg,
        )


async def join_incident_as_role(
    channel_id: str,
    role: str,
    user: User,
):
    """
    Parameters:
        channel_id (str): Incident channel_id
        role (str): The role being claimed
        user (incidentbot.models.slack.User): User object from the Slack response
    """

    incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)

    # Verify the role is valid
    try:
        role_definition = settings.roles.get(role)
    except Exception:
        logger.exception("role is not valid", role=role)
        return

    if incident:
        role_normalized = role.replace("_", " ").title()

        # Check whether or not the user has already claimed the role
        assigned = IncidentDatabaseInterface.check_role_assigned_to_user(
            incident=incident, role=role, user=user
        )
        if assigned:
            try:
                slack_web_client.chat_postEphemeral(
                    channel=channel_id,
                    user=user.id,
                    text=f"You have already joined this incident as *{role_normalized}*.",
                )

                return
            except SlackApiError as error:
                logger.exception(
                    "error sending message back to user via slash command invocation", error=error
                )

        # Send update notification message to incident channel
        try:
            result = slack_web_client.chat_postMessage(
                **IncidentUpdate.role(
                    action="joined",
                    channel=incident.channel_id,
                    role=role_normalized,
                    user=user.id,
                ),
                text=f"<@{user}> has joined this incident as *{role_normalized}*.",
            )
            logger.debug("role update result", result=result)
        except SlackApiError as error:
            logger.exception(
                "error sending role update to incident channel", error=error
            )

        # Provide the user with information regarding the role
        try:
            slack_web_client.chat_postEphemeral(
                channel=channel_id,
                user=user.id,
                text=f"You have joined this incident as {role_normalized}. {settings.roles.get(role).description}",
            )
        except SlackApiError as error:
            logger.exception(
                "error sending message back to user via slash command invocation", error=error
            )

        # Update topic if lead role
        if role_definition.is_lead:
            try:
                current_topic = _get_channel_topic(incident.channel_id)
                slack_web_client.conversations_setTopic(
                    channel=incident.channel_id,
                    topic=f"{current_topic[0]} | {current_topic[1]} | {role_normalized}: <@{user.id}>",
                )
            except SlackApiError as error:
                logger.exception("error updating channel topic", error=error)

        # Create record
        IncidentDatabaseInterface.associate_role(
            incident=incident,
            is_lead=role_definition.is_lead,
            role=role,
            user=user,
        )

        # Write event log
        EventLogHandler.create(
            event=f"{user.name} joined the incident as {role_normalized}",
            incident_id=incident.id,
            incident_slug=incident.slug,
            source="system",
        )

        # Refresh the live roles panel
        _refresh_roles_panel(channel_id)
    else:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=err_msg,
        )


async def leave_incident_as_role(
    channel_id: str,
    role: str,
    user: User,
):
    """
    Parameters:
        channel_id (str): Incident channel_id
        role (str): The role being forfeited
        user (incidentbot.models.slack.User): User object from the Slack response
    """

    incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)

    # Verify the role is valid
    try:
        role_definition = settings.roles.get(role)
    except Exception:
        logger.exception("role is not valid", role=role)
        return

    if incident:
        role_normalized = role.replace("_", " ").title()

        # Check whether or not the user has claimed the role
        assigned = IncidentDatabaseInterface.check_role_assigned_to_user(
            incident=incident, role=role, user=user
        )
        if assigned:
            pass
        else:
            logger.error("user is not assigned that role")
            return

        # Send update notification message to incident channel
        try:
            result = slack_web_client.chat_postMessage(
                **IncidentUpdate.role(
                    action="left",
                    channel=incident.channel_id,
                    role=role_normalized,
                    user=user.id,
                ),
                text=f"<@{user}> is no longer *{role_normalized}* for this incident.",
            )
            logger.debug("role update result", result=result)
        except SlackApiError as error:
            logger.exception(
                "error sending role update to incident channel", error=error
            )

        # Notify the user
        try:
            slack_web_client.chat_postEphemeral(
                channel=channel_id,
                user=user.id,
                text=f"You are no longer {role_normalized}.",
            )
        except SlackApiError as error:
            logger.exception(
                "error sending message back to user via slash command invocation", error=error
            )

        # Update topic if lead role
        if role_definition.is_lead:
            try:
                current_topic = _get_channel_topic(incident.channel_id)
                slack_web_client.conversations_setTopic(
                    channel=incident.channel_id,
                    topic=f"{current_topic[0]} | {current_topic[1]}",
                )
            except SlackApiError as error:
                logger.exception("error updating channel topic", error=error)

        # Delete record
        IncidentDatabaseInterface.remove_role(
            incident=incident,
            role=role,
            user=user,
        )

        # Write event log
        EventLogHandler.create(
            event=f"{user.name} left the incident as {role_normalized}",
            incident_id=incident.id,
            incident_slug=incident.slug,
            source="system",
        )

        # Refresh the live roles panel
        _refresh_roles_panel(channel_id)
    else:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=err_msg,
        )


async def set_description(channel_id: str, description: str, user: str = None):
    """
    Parameters:
        channel_id (str): Incident channel_id
        description (str): The description value
    """

    incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)

    if incident:
        # Update digest message
        try:
            slack_web_client.chat_update(
                channel=get_digest_channel_id(),
                ts=incident.digest_message_ts,
                blocks=IncidentChannelDigestNotification.update(
                    channel_id=incident.channel_id,
                    has_private_channel=incident.has_private_channel,
                    incident_components=incident.components,
                    incident_description=description,
                    incident_impact=incident.impact,
                    incident_slug=incident.slug,
                    meeting_link=incident.meeting_link,
                    severity=incident.severity,
                    status=incident.status,
                ),
                text="Digest message has been updated.",
            )
        except SlackApiError as error:
            logger.exception(
                "error during description update for incident channel", channel=incident.channel_name, error=error
            )
            return

        # Update boilerplate message
        result = slack_web_client.conversations_history(
            channel=incident.channel_id,
            inclusive=True,
            oldest=incident.boilerplate_message_ts,
            limit=1,
        )
        blocks = result["messages"][0]["blocks"]
        description_block_index = gen.find_index_in_list(
            blocks, "block_id", "digest_channel_description"
        )
        if description_block_index == -1:
            raise IndexNotFoundError(
                "Could not find index for block_id severity"
            )

        blocks[description_block_index]["text"]["text"] = description

        slack_web_client.chat_update(
            channel=incident.channel_id,
            ts=incident.boilerplate_message_ts,
            blocks=blocks,
            text="This incident's description has been updated.",
        )

        # Notify channel
        notification_suffix = (
            f"{description} by {user}" if user else f"{description}"
        )
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=f"The description of this incident has been updated to {notification_suffix}.",
        )

        # If that all worked, change the channel name
        new_channel_name = format_channel_name(
            id=incident.id,
            description=description,
            use_date_prefix=settings.options.channel_name_use_date_prefix,
        )
        try:
            slack_web_client.conversations_rename(
                channel=channel_id, name=new_channel_name
            )
        except SlackApiError as error:
            logger.exception(
                "error renaming channel (rename it manually)", channel=incident.channel_name, error=error
            )

        # Update database record
        try:
            IncidentDatabaseInterface.update_col(
                channel_id=incident.channel_id,
                col_name="channel_name",
                value=new_channel_name,
            )
            IncidentDatabaseInterface.update_col(
                channel_id=incident.channel_id,
                col_name="description",
                value=description,
            )
        except Exception as error:
            logger.exception("error updating entry in database", error=error)

        # Write event log
        EventLogHandler.create(
            event=f"The incident description was updated to {notification_suffix}",
            incident_id=incident.id,
            incident_slug=incident.slug,
            source="system",
        )

        logger.info(
            "updated incident description", channel=incident.channel_name
        )
    else:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=err_msg,
        )


async def set_severity(channel_id: str, severity: str, user: User | str):
    """
    Parameters:
        channel_id (str): Incident channel_id
        severity (str): The severity value
        user (incidentbot.models.slack.User | str): User object from the Slack response, or api
    """

    incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)

    if incident:
        if user != "api" and incident.severity == severity:
                try:
                    slack_web_client.chat_postEphemeral(
                        channel=channel_id,
                        user=user.id,
                        text=f"The severity for this incident is already {severity.upper()}.",
                    )

                    return
                except SlackApiError as error:
                    logger.exception(
                        "error sending message back to user via slash command invocation", error=error
                    )

        # Update gitlab ticket severity
        if (
            settings.integrations
            and settings.integrations.gitlab
            and settings.integrations.gitlab.enabled
            and settings.integrations.gitlab.severity_mapping
        ):
            from incidentbot.gitlab.api import GitLabApi

            gitlab = GitLabApi()
            gitlab.update_issue_severity(
                incident_name=incident.channel_name, incident_severity=severity
            )
            logger.info(
                "updated gitlab issue severity", channel=incident.channel_name, severity=severity
            )

        # Update digest message
        try:
            slack_web_client.chat_update(
                channel=get_digest_channel_id(),
                ts=incident.digest_message_ts,
                blocks=IncidentChannelDigestNotification.update(
                    channel_id=incident.channel_id,
                    has_private_channel=incident.has_private_channel,
                    incident_components=incident.components,
                    incident_description=incident.description,
                    incident_impact=incident.impact,
                    incident_slug=incident.slug,
                    meeting_link=incident.meeting_link,
                    severity=severity,
                    status=incident.status,
                ),
                text="Digest message has been updated.",
            )
        except SlackApiError as error:
            logger.exception(
                "error sending severity update to incident channel", channel=incident.channel_name, error=error
            )

        # Channel notification
        try:
            result = slack_web_client.chat_postMessage(
                **IncidentUpdate.severity(
                    channel=incident.channel_id, severity=severity
                ),
                text=f"The incident severity has been changed to {severity}.",
            )
            logger.debug("severity update result", result=result)
        except SlackApiError as error:
            logger.exception(
                "error sending severity update to incident channel", channel=incident.channel_name, error=error
            )

        try:
            current_topic = _get_channel_topic(incident.channel_id)
            new_topic = f"Severity: {severity.upper()} | {current_topic[1]}"
            if len(current_topic) == 3:
                new_topic += f" | {current_topic[2]}"
            slack_web_client.conversations_setTopic(
                channel=incident.channel_id,
                topic=new_topic,
            )
        except SlackApiError as error:
            logger.exception("error updating channel topic", error=error)

        # Log
        logger.info(
            "updated incident severity", channel=incident.channel_name, severity=severity
        )

        # Update incident record with new severity
        try:
            IncidentDatabaseInterface.update_col(
                channel_id=incident.channel_id,
                col_name="severity",
                value=severity,
            )
        except Exception as error:
            logger.exception("error updating entry in database", error=error)

        # Write event log
        EventLogHandler.create(
            event=f"The incident severity was changed to {severity.upper()}",
            incident_id=incident.id,
            incident_slug=incident.slug,
            source="system",
        )

        run_automations("on_severity_change", incident)
    else:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=err_msg,
        )


async def set_status(
    channel_id: str,
    status: str,
    user: User | str,
):
    """
    Parameters:
        channel_id (str): Incident channel_id
        status (str): The status value
        user (incidentbot.models.slack.User | str): User object from the Slack response, or api
    """

    incident = IncidentDatabaseInterface.get_one(channel_id=channel_id)

    if incident:
        if user != "api" and incident.status == status:
                try:
                    slack_web_client.chat_postEphemeral(
                        channel=channel_id,
                        user=user.id,
                        text=f"The status for this incident is already {status.title()}.",
                    )

                    return
                except SlackApiError as error:
                    logger.exception(
                        "error sending message back to user via slash command invocation", error=error
                    )

        if incident.status == status:
            # Nothing changed, so there is nothing to announce either.
            return

        # The postmortem, the ticket sync, the database write, the event log,
        # the automations and the reminder jobs. Everything a status change does
        # on every platform.
        incident, postmortem_link = apply_status_change(incident, status)

        if postmortem_link:
            _send_postmortem_message(incident.channel_id, postmortem_link)

        # Update digest message
        try:
            slack_web_client.chat_update(
                channel=get_digest_channel_id(),
                ts=incident.digest_message_ts,
                blocks=IncidentChannelDigestNotification.update(
                    channel_id=incident.channel_id,
                    has_private_channel=incident.has_private_channel,
                    incident_components=incident.components,
                    incident_description=incident.description,
                    incident_impact=incident.impact,
                    incident_slug=incident.slug,
                    meeting_link=incident.meeting_link,
                    severity=incident.severity,
                    status=status,
                    postmortem_link=postmortem_link,
                ),
                text="The digest message has been updated.",
            )
        except SlackApiError as error:
            logger.exception(
                "error sending status update to incident channel", channel=incident.channel_name, error=error
            )

        try:
            current_topic = _get_channel_topic(incident.channel_id)
            new_topic = f"{current_topic[0]} | Status: {status.title()}"
            if len(current_topic) == 3:
                new_topic += f" | {current_topic[2]}"
            slack_web_client.conversations_setTopic(
                channel=incident.channel_id,
                topic=new_topic,
            )
        except SlackApiError as error:
            logger.exception("error updating channel topic", error=error)

        # Channel notification
        try:
            result = slack_web_client.chat_postMessage(
                **IncidentUpdate.status(
                    channel=incident.channel_id, status=status
                ),
                text=f"The incident status has been changed to {status}.",
            )
            logger.debug("status update result", result=result)
        except SlackApiError as error:
            logger.exception(
                "error sending status update to incident channel", channel=incident.channel_name, error=error
            )

        if is_final(status):
            # Resolution message
            try:
                result = slack_web_client.chat_postMessage(
                    **BlockBuilder.resolution_message(
                        channel=incident.channel_id,
                        postmortem_link=postmortem_link,
                        sync_pinned_content_enabled=_is_confluence_postmortem_link(
                            postmortem_link
                        ),
                    ),
                    text="The incident has been resolved.",
                )
                logger.debug("resolution update result", result=result)
            except SlackApiError as error:
                logger.exception(
                    "error sending resolution update to incident channel", channel=incident.channel_name, error=error
                )
    else:
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=err_msg,
        )
