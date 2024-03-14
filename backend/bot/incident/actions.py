from bot.incident.incident import Incident
import config
import slack_sdk.errors

from bot.audit import log
from bot.exc import IndexNotFoundError, PostmortemException
from bot.incident.action_parameters import (
    ActionParametersSlack,
    ActionParametersWeb,
)
from bot.models.incident import (
    db_read_incident,
    db_update_incident_postmortem_col,
    db_update_incident_role,
    db_update_incident_status_col,
    db_update_incident_severity_col,
    db_update_incident_updated_at_col,
)
from bot.models.pg import Incident as IncidentModel
from bot.scheduler import scheduler
from bot.shared import tools
from bot.slack.client import (
    get_digest_channel_id,
    get_formatted_channel_history,
    get_message_content,
    invite_user_to_channel,
    slack_web_client,
)
from bot.slack.incident_logging import read as read_incident_pinned_items
from bot.templates.incident.digest_notification import (
    IncidentChannelDigestNotification,
)
from bot.templates.incident.resolution_message import IncidentResolutionMessage
from bot.templates.incident.updates import IncidentUpdate
from bot.templates.incident.user_dm import IncidentUserNotification
from datetime import datetime
from iblog import logger
from typing import Any, Dict


"""
Functions for handling inbound actions
"""


async def archive_incident_channel(
    action_parameters: type[ActionParametersSlack],
):
    """When an incoming action is incident.archive_incident_channel, this method
    archives the target channel.

    Keyword arguments:
    action_parameters -- type[ActionParametersSlack] containing Slack actions data
    """
    incident_data = db_read_incident(
        channel_id=action_parameters.channel_details.get("id")
    )
    try:
        logger.info(f"Archiving {incident_data.channel_name}.")
        result = slack_web_client.conversations_archive(
            channel=incident_data.channel_id
        )
        logger.debug(f"\n{result}\n")
    except slack_sdk.errors.SlackApiError as error:
        logger.error(f"Error archiving {incident_data.channel_name}: {error}")
    finally:
        # Write audit log
        log.write(
            incident_id=incident_data.channel_name,
            event="Channel archived.",
        )


async def assign_role(
    action_parameters: type[ActionParametersSlack] = ActionParametersSlack,
    web_data: type[ActionParametersWeb] = ActionParametersWeb,
    request_origin: str = "slack",
):
    """When an incoming action is incident.assign_role, this method
    assigns the role to the user provided in the input

    Keyword arguments:
    action_parameters(type[ActionParametersSlack]) containing Slack actions data
    web_data(Dict) - if executing from "web", this data must be passed
    request_origin(str) - can either be "slack" or "web"
    """
    match request_origin:
        case "slack":
            try:
                incident_data = db_read_incident(
                    channel_id=action_parameters.channel_details.get("id")
                )
                # Target incident channel
                target_channel = incident_data.channel_id
                channel_name = incident_data.channel_name
                user_id = action_parameters.actions.get("selected_user")
                action_value = "_".join(
                    action_parameters.actions.get("block_id").split("_")[1:3]
                )
                # Find the index of the block that contains info on
                # the role we want to update and format it with the new user later
                blocks = action_parameters.message_details.get("blocks")
                index = tools.find_index_in_list(
                    blocks, "block_id", f"role_{action_value}"
                )
                if index == -1:
                    raise IndexNotFoundError(
                        f"Could not find index for block_id role_{action_value}"
                    )
                temp_new_role_name = action_value.replace("_", " ")
                target_role = action_value
                ts = action_parameters.message_details.get("ts")
            except Exception as error:
                logger.error(
                    f"Error processing incident user update from Slack: {error}"
                )
        case "web":
            try:
                incident_data = db_read_incident(
                    channel_id=web_data.channel_id
                )
                # Target incident channel
                target_channel = incident_data.channel_id
                channel_name = incident_data.channel_name
                user_id = web_data.user
                # Find the index of the block that contains info on
                # the role we want to update and format it with the new user later
                blocks = get_message_content(
                    conversation_id=web_data.channel_id,
                    ts=web_data.bp_message_ts,
                ).get("blocks")
                index = tools.find_index_in_list(
                    blocks, "block_id", f"role_{web_data.role}"
                )
                if index == -1:
                    raise IndexNotFoundError(
                        f"Could not find index for block_id role_{web_data.role}"
                    )
                temp_new_role_name = web_data.role.replace("_", " ")
                target_role = web_data.role
                ts = web_data.bp_message_ts
            except Exception as error:
                logger.error(
                    f"Error processing incident user update from web: {error}"
                )

    new_role_name = temp_new_role_name.title()
    blocks[index]["text"]["text"] = f"*{new_role_name}*:\n <@{user_id}>"
    # Convert user ID to user name to use later.
    user_name = next(
        (
            u["name"]
            for u in slack_web_client.users_list()["members"]
            if u["id"] == user_id
        ),
        None,
    )

    try:
        # Update the message
        slack_web_client.chat_update(
            channel=target_channel,
            ts=ts,
            blocks=blocks,
            text=f"{user_id} is now {new_role_name}",
        )
    except Exception as error:
        logger.error(
            f"Error updating channel message during user update: {error}"
        )

    # Send update notification message to incident channel
    try:
        result = slack_web_client.chat_postMessage(
            **IncidentUpdate.role(
                channel=target_channel, role=new_role_name, user=user_id
            ),
            text=f"{user_id} is now {new_role_name}",
        )

        logger.debug(f"\n{result}\n")
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error sending role update to the incident channel: {error}"
        )

    # Let the user know they've been assigned the role and what to do
    try:
        result = slack_web_client.chat_postMessage(
            **IncidentUserNotification.create(
                user=user_id, role=target_role, channel=target_channel
            ),
            text=f"You have been assigned {new_role_name} for incident <#{target_channel}>",
        )
        logger.debug(f"\n{result}\n")
    except slack_sdk.errors.SlackApiError as error:
        logger.error(f"Error sending role description to user: {error}")
    logger.info(f"{user_name} was assigned {target_role} in {channel_name}")

    # Since the user was assigned the role, they should be auto invited.
    invite_user_to_channel(target_channel, user_id)

    # Update the row to indicate who owns the role.
    db_update_incident_role(
        channel_id=target_channel, role=target_role, user=user_name
    )

    # Write audit log
    log.write(
        incident_id=channel_name,
        event=f"User {user_name} was assigned role {target_role}.",
    )
    # Finally, updated the updated_at column
    db_update_incident_updated_at_col(
        channel_id=target_channel,
        updated_at=tools.fetch_timestamp(),
    )


async def claim_role(action_parameters: type[ActionParametersSlack]):
    """When an incoming action is incident.claim_role, this method
    assigns the role to the user that hit the claim button

    Keyword arguments:
    action_parameters -- type[ActionParametersSlack] containing Slack actions data
    """
    incident_data = db_read_incident(
        channel_id=action_parameters.channel_details["id"]
    )
    action_value = action_parameters.actions["value"]
    # Find the index of the block that contains info on
    # the role we want to update
    blocks = action_parameters.message_details["blocks"]
    index = tools.find_index_in_list(
        blocks, "block_id", f"role_{action_value}"
    )
    if index == -1:
        raise IndexNotFoundError(
            f"Could not find index for block_id role_{action_value}"
        )
    # Replace the "_none_" value in the given block
    temp_new_role_name = action_value.replace("_", " ")
    new_role_name = temp_new_role_name.title()
    user = action_parameters.user_details["name"]
    blocks[index]["text"]["text"] = f"*{new_role_name}*:\n <@{user}>"
    # Update the message
    slack_web_client.chat_update(
        channel=incident_data.channel_id,
        ts=action_parameters.message_details["ts"],
        blocks=blocks,
    )
    # Send update notification message to incident channel
    try:
        result = slack_web_client.chat_postMessage(
            **IncidentUpdate.role(
                channel=incident_data.channel_id, role=new_role_name, user=user
            ),
            text=f"You have claimed {new_role_name} for incident <#{incident_data.channel_id}>",
        )
        logger.debug(f"\n{result}\n")
    except slack_sdk.errors.SlackApiError as error:
        logger.error(f"Error sending role update to incident channel: {error}")
    # Let the user know they've been assigned the role and what to do
    try:
        result = slack_web_client.chat_postMessage(
            **IncidentUserNotification.create(
                user=action_parameters.user_details["id"],
                role=action_value,
                channel=incident_data.channel_id,
            ),
            text=f"You have been assigned the role {action_value} for incident {incident_data.channel_name}.",
        )
        logger.debug(f"\n{result}\n")
    except slack_sdk.errors.SlackApiError as error:
        logger.error(f"Error sending role description to user: {error}")
    logger.info(
        f"{user} has claimed {action_value} in {incident_data.channel_name}"
    )
    # Update the row to indicate who owns the role.
    db_update_incident_role(
        channel_id=incident_data.channel_id, role=action_value, user=user
    )

    # Write audit log
    log.write(
        incident_id=incident_data.channel_id,
        event=f"User {user} claimed role {action_value}.",
    )
    # Finally, updated the updated_at column
    db_update_incident_updated_at_col(
        channel_id=incident_data.channel_id,
        updated_at=tools.fetch_timestamp(),
    )


async def export_chat_logs(action_parameters: type[ActionParametersSlack]):
    """When an incoming action is incident.export_chat_logs, this method
    fetches channel history, formats it, and returns it to the channel

    Keyword arguments:
    action_parameters -- type[ActionParametersSlack] containing Slack actions data
    """
    incident_data = db_read_incident(
        channel_id=action_parameters.channel_details["id"]
    )
    # Retrieve channel history and post as text attachment
    history = get_formatted_channel_history(
        channel_id=incident_data.channel_id,
        channel_name=incident_data.channel_name,
    )
    try:
        logger.info(
            f"Sending chat transcript to {incident_data.channel_name}."
        )
        result = slack_web_client.files_upload_v2(
            channels=incident_data.channel_id,
            content=history,
            filename=f"{incident_data.channel_name} Chat Transcript",
            filetype="txt",
            initial_comment="As requested, here is the chat transcript. Remember"
            + " - while this is useful, it will likely need cultivation before "
            + "being added to a postmortem.",
            title=f"{incident_data.channel_name} Chat Transcript",
        )
        logger.debug(f"\n{result}\n")
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error sending message and attachment to {incident_data.channel_name}: {error}"
        )
    finally:
        # Write audit log
        log.write(
            incident_id=incident_data.channel_name,
            event=f"Incident chat log was exported by {action_parameters.user_details}.",
        )


async def set_status(
    action_parameters: type[ActionParametersSlack] = ActionParametersSlack,
):
    """When an incoming action is incident.set_status, this method
    updates the status of the incident

    Keyword arguments:
    action_parameters(type[ActionParametersSlack]) containing Slack actions data
    """
    incident_data = db_read_incident(
        channel_id=action_parameters.channel_details["id"]
    )

    action_value = action_parameters.actions["selected_option"]["value"]
    user = action_parameters.user_details["id"]

    # Write audit log
    log.write(
        incident_id=incident_data.incident_id,
        event=f"Status was changed to {action_value}.",
    )

    # If set to resolved, send additional information.
    if action_value == "resolved":
        message_blocks = action_parameters.message_details["blocks"]
        # Extract names of required roles
        incident_commander = extract_role_owner(
            message_blocks, "role_incident_commander"
        )
        # Error out if incident commander hasn't been claimed
        for role, person in {
            "incident commander": incident_commander,
        }.items():
            if person == "_none_":
                try:
                    result = slack_web_client.chat_postMessage(
                        channel=incident_data.channel_id,
                        text=f":red_circle: <@{user}> Before this incident can"
                        + f" be marked as resolved, the *{role}* role must be "
                        + "assigned. Please assign it and try again.",
                    )
                except slack_sdk.errors.SlackApiError as error:
                    logger.error(
                        f"Error sending note to {incident_data.incident_id} regarding missing role claim: {error}"
                    )
                return

        # We want real user names to tag in the postmortem doc
        actual_user_names = []
        for person in [incident_commander]:
            if person != "_none_":
                fmt = person.replace("<", "").replace(">", "").replace("@", "")
                # Get real name of user to be used to generate postmortem
                actual_user_names.append(
                    slack_web_client.users_info(user=fmt)["user"]["profile"][
                        "real_name"
                    ]
                )
            else:
                actual_user_names.append("Unassigned")

        postmortem_link = None
        # Generate postmortem template and create postmortem if enabled
        # Get normalized description as postmortem title
        if "atlassian" in config.active.integrations:
            if (
                config.active.integrations.get("atlassian")
                .get("confluence")
                .get("auto_create_postmortem")
            ):
                postmortem_link = await create_post_mortem_block(
                    incident_data
                )
        # Send message to incident channel
        try:
            result = slack_web_client.chat_postMessage(
                **IncidentResolutionMessage.create(
                    channel=incident_data.channel_id
                ),
                text="The incident has been resolved.",
            )
            logger.debug(f"\n{result}\n")
        except slack_sdk.errors.SlackApiError as error:
            logger.error(
                f"Error sending resolution update to incident channel {incident_data.channel_name}: {error}"
            )

        # Log
        logger.info(f"Sent resolution info to {incident_data.channel_name}.")

        # If PagerDuty incident(s) exist, attempt to resolve them
        if "pagerduty" in config.active.integrations:
            from bot.pagerduty.api import resolve

            if incident_data.pagerduty_incidents is not None:
                for inc in incident_data.pagerduty_incidents:
                    resolve(pd_incident_id=inc)

    # Also updates digest message
    try:
        slack_web_client.chat_update(
            channel=get_digest_channel_id(),
            ts=incident_data.dig_message_ts,
            blocks=IncidentChannelDigestNotification.update(
                incident_id=incident_data.channel_name,
                incident_description=incident_data.channel_description,
                is_security_incident=incident_data.is_security_incident,
                status=action_value,
                severity=incident_data.severity,
                conference_bridge=incident_data.conference_bridge,
                postmortem_link=(
                    postmortem_link
                    if action_value == "resolved"
                    and ("atlassian" in config.active.integrations)
                    and (
                        config.active.integrations.get("atlassian")
                        .get("confluence")
                        .get("auto_create_postmortem")
                    )
                    else None
                ),
            ),
            text="",
        )
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error sending status update to incident channel {incident_data.channel_name}: {error}"
        )

    # Change placeholder for select to match current status in boilerplate message
    result = slack_web_client.conversations_history(
        channel=incident_data.channel_id,
        inclusive=True,
        oldest=incident_data.bp_message_ts,
        limit=1,
    )
    blocks = result["messages"][0]["blocks"]
    status_block_index = tools.find_index_in_list(blocks, "block_id", "status")
    if status_block_index == -1:
        raise IndexNotFoundError("Could not find index for block_id status")
    blocks[status_block_index]["accessory"]["initial_option"] = {
        "text": {
            "type": "plain_text",
            "text": action_value.title(),
            "emoji": True,
        },
        "value": action_value,
    }
    slack_web_client.chat_update(
        channel=incident_data.channel_id,
        ts=action_parameters.message_details["ts"],
        blocks=blocks,
    )

    # Update incident record with the status
    logger.info(
        f"Updating incident record in database with new status for {incident_data.channel_name}"
    )
    try:
        db_update_incident_status_col(
            channel_id=incident_data.channel_id,
            status=action_value,
        )
    except Exception as error:
        logger.fatal(f"Error updating entry in database: {error}")

    # See if there's a scheduled reminder job for the incident and delete it if so
    if action_value == "resolved":
        for job in scheduler.process.list_jobs():
            job_title = f"{incident_data.channel_name}_updates_reminder"
            if job.id == job_title:
                try:
                    scheduler.process.delete_job(job_title)
                    logger.info(f"Deleted job: {job_title}")
                    # Write audit log
                    log.write(
                        incident_id=incident_data.channel_name,
                        event="Deleted scheduled reminder for incident updates.",
                    )
                except Exception as error:
                    logger.error(
                        f"Could not delete the job {job_title}: {error}"
                    )

    # If the incident is resolved, disable status select
    if action_value == "resolved":
        result = slack_web_client.conversations_history(
            channel=incident_data.channel_id,
            inclusive=True,
            oldest=incident_data.bp_message_ts,
            limit=1,
        )
        blocks = result["messages"][0]["blocks"]
        status_block_index = tools.find_index_in_list(
            blocks, "block_id", "status"
        )
        if status_block_index == -1:
            raise IndexNotFoundError(
                "Could not find index for block_id status"
            )
        blocks[status_block_index]["accessory"]["confirm"] = {
            "title": {
                "type": "plain_text",
                "text": "This incident is already resolved.",
            },
            "text": {
                "type": "mrkdwn",
                "text": "Since this incident has already been resolved, it "
                + "shouldn't be reopened. A new incident should be started instead.",
            },
            "confirm": {"type": "plain_text", "text": "Reopen Anyway"},
            "deny": {"type": "plain_text", "text": "Go Back"},
            "style": "danger",
        }
        slack_web_client.chat_update(
            channel=incident_data.channel_id,
            ts=action_parameters.message_details["ts"],
            blocks=blocks,
        )
    # Log
    logger.info(
        f"Updated incident status for {incident_data.channel_name} to {action_value}."
    )
    try:
        result = slack_web_client.chat_postMessage(
            **IncidentUpdate.status(
                channel=incident_data.channel_id, status=action_value
            ),
            text=f"The incident status has been changed to {action_value}.",
        )
        logger.debug(f"\n{result}\n")
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error sending status update to incident channel {incident_data.channel_name}: {error}"
        )

    # Update jira ticket status last
    if (
        config.active.integrations.get("atlassian", {})
        .get("jira", {})
        .get("status_mapping", [])
    ):
        from bot.jira.api import JiraApi

        jira = JiraApi()
        jira.update_issue_status(
            incident_status=action_value,
            incident_name=incident_data.channel_name,
        )

    # Finally, updated the updated_at column
    db_update_incident_updated_at_col(
        channel_id=incident_data.channel_id,
        updated_at=tools.fetch_timestamp(),
    )


async def create_post_mortem_block(
    incident_data: IncidentModel,
) -> str | None:
    """Generates a postmortem template and creates the postmortem"""
    from bot.confluence.postmortem import IncidentPostmortem

    # Format postmortem message to incident channel
    postmortem_boilerplate_message_blocks = [
        {"type": "divider"},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":white_check_mark: Incident Postmortem",
            },
        },
    ]


    try:
        postmortem = IncidentPostmortem(
            incident_id=incident_data.incident_id,
            incident_created_at=incident_data.created_at,
            incident_description=incident_data.channel_description,
            severity=incident_data.severity,
            severity_definition=config.active.severities[
                incident_data.severity
            ],
            channel_id=incident_data.channel_id,
            channel_name=incident_data.channel_name,
            pinned_items=read_incident_pinned_items(
                incident_id=incident_data.incident_id
            ),
            timeline=log.read(incident_id=incident_data.incident_id),
            roles=incident_data.roles,
        )
        postmortem_link = postmortem.create()

        db_update_incident_postmortem_col(
            channel_id=incident_data.channel_id,
            postmortem=postmortem_link,
        )
        # Write audit log
        log.write(
            incident_id=incident_data.incident_id,
            event=f"Postmortem was automatically created: {postmortem_link}",
        )
        postmortem_boilerplate_message_blocks.extend(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*I have created a base postmortem document that"
                        " you can build on. You can open it using the button below.*",
                    },
                },
                {
                    "block_id": "buttons",
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "View Postmortem In Confluence",
                            },
                            "style": "primary",
                            "url": postmortem_link,
                            "action_id": "open_postmortem",
                        },
                    ],
                },
                {"type": "divider"},
            ]
        )
    except PostmortemException as error:
        return None

    # Send postmortem message to incident channel
    try:
        blocks = postmortem_boilerplate_message_blocks
        result = slack_web_client.chat_postMessage(
            channel=incident_data.channel_id,
            blocks=blocks,
            text="",
        )
        logger.debug(f"\n{result}\n")

        # Pin the postmortem message to the channel for quick access.
        slack_web_client.pins_add(
            channel=incident_data.channel_id,
            timestamp=result.get("ts"),
        )
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error sending postmortem update to incident channel: {error}"
        )
    return postmortem_link


async def set_severity(
    action_parameters: type[ActionParametersSlack] = None,
):
    """When an incoming action is incident.set_severity, this method
    updates the severity of the incident

    Keyword arguments:
    action_parameters(type[ActionParametersSlack]) - contains Slack actions data
    """
    incident_data = db_read_incident(
        channel_id=action_parameters.channel_details["id"]
    )
    action_value = action_parameters.actions["selected_option"]["value"]

    # Also updates digest message
    try:
        slack_web_client.chat_update(
            channel=get_digest_channel_id(),
            ts=incident_data.dig_message_ts,
            blocks=IncidentChannelDigestNotification.update(
                incident_id=incident_data.channel_name,
                incident_description=incident_data.channel_description,
                is_security_incident=incident_data.is_security_incident,
                status=incident_data.status,
                severity=action_value,
                conference_bridge=incident_data.conference_bridge,
            ),
        )
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error sending severity update to incident channel {incident_data.channel_name}: {error}"
        )

    # Change placeholder for select to match current status in boilerplate message
    result = slack_web_client.conversations_history(
        channel=incident_data.channel_id,
        inclusive=True,
        oldest=incident_data.bp_message_ts,
        limit=1,
    )
    blocks = result["messages"][0]["blocks"]
    sev_blocks_index = tools.find_index_in_list(blocks, "block_id", "severity")
    if sev_blocks_index == -1:
        raise IndexNotFoundError("Could not find index for block_id severity")
    blocks[sev_blocks_index]["accessory"]["initial_option"] = {
        "text": {
            "type": "plain_text",
            "text": action_value.upper(),
            "emoji": True,
        },
        "value": action_value,
    }
    slack_web_client.chat_update(
        channel=incident_data.channel_id,
        ts=action_parameters.message_details["ts"],
        blocks=blocks,
    )

    # Update incident record with the severity
    logger.info(
        f"Updating incident record in database with new severity for {incident_data.channel_name}"
    )
    try:
        db_update_incident_severity_col(
            channel_id=incident_data.channel_id,
            severity=action_value,
        )
    except Exception as error:
        logger.fatal(f"Error updating entry in database: {error}")

    # If SEV1/2, we need to start a timer to remind the channel about sending status updates
    if config.active.incident_reminders:
        if action_value in config.active.incident_reminders.get(
            "qualifying_severities"
        ):
            logger.info(f"Adding job because action was {action_value}")
            scheduler.add_incident_scheduled_reminder(
                channel_name=incident_data.channel_name,
                channel_id=incident_data.channel_id,
                severity=action_value,
                rate=config.active.incident_reminders.get("rate"),
            )
            # Write audit log
            log.write(
                incident_id=incident_data.channel_name,
                event=f"Scheduled reminder job created.",
            )

    # Final notification
    try:
        result = slack_web_client.chat_postMessage(
            **IncidentUpdate.severity(
                channel=incident_data.channel_id, severity=action_value
            ),
            text=f"The incident severity has been changed to {action_value}.",
        )
        logger.debug(f"\n{result}\n")
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error sending severity update to incident channel {incident_data.channel_name}: {error}"
        )
    # Log
    logger.info(
        f"Updated incident severity for {incident_data.channel_name} to {action_value}."
    )
    # Finally, updated the updated_at column
    db_update_incident_updated_at_col(
        channel_id=incident_data.channel_id,
        updated_at=tools.fetch_timestamp(),
    )
    # Write audit log
    log.write(
        incident_id=incident_data.channel_name,
        event=f"Severity set to {action_value.upper()}.",
    )


"""
Utility Functions
"""


def extract_role_owner(message_blocks: Dict[Any, Any], block_id: str) -> str:
    """
    Takes message blocks and a block_id and returns information specific
    to one of the role blocks
    """
    index = tools.find_index_in_list(message_blocks, "block_id", block_id)
    if index == -1:
        raise IndexNotFoundError(
            f"Could not find index for block_id {block_id}"
        )
    return (
        message_blocks[index]["text"]["text"].split("\n")[1].replace(" ", "")
    )
