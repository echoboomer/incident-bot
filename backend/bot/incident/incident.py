import config
import datetime
import logging
import slack_sdk.errors

from bot.audit import log
from bot.external import epi
from bot.shared import tools
from bot.statuspage import slack as spslack, handler as sp_handler
from threading import Thread
from typing import Dict

logger = logging.getLogger(__name__)

# How many total characters are allowed in a Slack channel?
channel_name_length_cap = 80
# How many characters does the incident prefix take up?
channel_name_prefix_length = len("inc-20211116-")
# How long can the provided description be?
channel_description_max_length = channel_name_length_cap - channel_name_prefix_length
# Which external providers are supported? Ones not in this list will error.
enabled_providers = [
    "auth0",
    "github",
    "heroku",
]

if config.test_environment == "false":
    from bot.slack.client import invite_user_to_channel


class Incident:
    """Instantiates an incident"""

    def __init__(self, request_data: Dict[str, str]):
        self.d = request_data
        self.log()

    def log(self):
        request_log = {
            "user": self.d["user"],
            "channel": self.d["channel"],
            "channel_description": self.d["channel_description"],
        }
        logger.info(
            f"Request received from Slack to start a new incident: {request_log}"
        )

    def return_channel_name(self) -> str:
        # Replace any spaces with dashes
        channel_description = self.d["channel_description"].replace(" ", "-").lower()
        now = datetime.datetime.now()
        return f"inc-{now.year}{now.month}{now.day}{now.hour}{now.minute}-{channel_description}"


"""
Core Functionality
"""


def create_incident(
    request_parameters: Dict[str, str],
    internal: bool = False,
) -> str:
    """
    Create an incident
    """
    from bot.db import db
    from bot.slack import client

    """
    Return formatted incident channel name
    Typically inc-datefmt-topic
    """
    channel_description = request_parameters["channel_description"]
    channel = request_parameters["channel"]
    user = request_parameters["user"]
    if channel_description != "":
        if len(channel_description) < channel_description_max_length:
            incident = Incident(
                request_data={
                    "channel_description": channel_description,
                    "channel": channel,
                    "user": user,
                }
            )
            fmt_channel_name = incident.return_channel_name()
            """
            Create incident channel
            """
            try:
                # Call the conversations.create method using the WebClient
                # conversations_create requires the channels:manage bot scope
                channel = client.slack_web_client.conversations_create(
                    # The name of the conversation
                    name=fmt_channel_name
                )
                # Log the result which includes information like the ID of the conversation
                logger.debug(f"\n{channel}\n")
                logger.info(f"Creating incident channel: {fmt_channel_name}")
            except slack_sdk.errors.SlackApiError as error:
                logger.error(f"Error creating incident channel: {error}")
            # Used by subsequent actions.
            createdChannelDetails = {
                "id": channel["channel"]["id"],
                "name": channel["channel"]["name"],
            }
            """
            Notify incidents digest channel (#incidents)
            """
            digest_message_content = build_digest_notification(createdChannelDetails)
            try:
                digest_message = client.slack_web_client.chat_postMessage(
                    **digest_message_content,
                    text="",
                )
                logger.debug(f"\n{digest_message}\n")
            except slack_sdk.errors.SlackApiError as error:
                logger.error(
                    f"Error sending message to incident digest channel: {error}"
                )
            logger.info(f"Sending message to digest channel for: {fmt_channel_name}")
            """
            Set incident channel topic
            """
            topic_boilerplate = config.incident_channel_topic
            try:
                topic = client.slack_web_client.conversations_setTopic(
                    channel=channel["channel"]["id"],
                    topic=topic_boilerplate,
                )
                logger.debug(f"\n{topic}\n")
            except slack_sdk.errors.SlackApiError as error:
                logger.error(f"Error setting incident channel topic: {error}")
            """
            Send boilerplate info to incident channel
            """
            bp_message_content = build_incident_channel_boilerplate(
                createdChannelDetails
            )
            try:
                bp_message = client.slack_web_client.chat_postMessage(
                    **bp_message_content,
                    text="",
                )
                logger.debug(f"\n{bp_message}\n")
            except slack_sdk.errors.SlackApiError as error:
                logger.error(f"Error sending message to incident channel: {error}")
            # Pin the boilerplate message to the channel for quick access.
            client.slack_web_client.pins_add(
                channel=createdChannelDetails["id"],
                timestamp=bp_message["ts"],
            )
            """
            Write incident entry to database
            """
            logger.info(f"Writing incident entry to database for {fmt_channel_name}...")
            try:
                db.db_write_incident(
                    fmt_channel_name,
                    channel["channel"]["id"],
                    channel["channel"]["name"],
                    "investigating",
                    "sev4",
                    bp_message["ts"],
                    digest_message["ts"],
                )
            except Exception as error:
                logger.fatal(f"Error writing entry to database: {error}")
            # Tag the incident with initial creation timestamp in human readable format
            try:
                db.db_update_incident_created_at_col(
                    incident_id=fmt_channel_name,
                    created_at=tools.fetch_timestamp(),
                )
            except Exception as error:
                logger.fatal(
                    f"Error updating incident entry with creation timestamp: {error}"
                )
            # Handle optionals in a thread to avoid breaking the 3000ms limit for Slack slash commands
            thr = Thread(
                target=handle_incident_optional_features,
                args=[request_parameters, createdChannelDetails, internal],
            )
            thr.start()
            # Invite the user who opened the channel to the channel.
            invite_user_to_channel(createdChannelDetails["id"], user)
            # Return for view method
            temp_channel_id = createdChannelDetails["id"]

            # Write audit log
            log.write(
                incident_id=createdChannelDetails["name"],
                event="Incident created.",
                user=user,
            )
            return f"I've created the incident channel: <#{temp_channel_id}>"
        else:
            return f"Total channel length cannot exceed 80 characters. Please use a short description less than {channel_description_max_length} characters. You used {len(channel_description)}."
    else:
        return "Please provide a description for the channel."


def handle_incident_optional_features(
    request_parameters: Dict[str, str],
    createdChannelDetails: Dict[str, str],
    internal: bool = False,
):
    """
    For new incidents, handle optional features
    """
    from bot.db import db
    from bot.slack import client

    channel_id = createdChannelDetails["id"]
    channel_name = createdChannelDetails["name"]

    """
    Invite required participants (optional)
    """
    if config.incident_auto_group_invite_enabled == "true":
        all_groups = client.all_workspace_groups["usergroups"]
        group_to_invite = config.incident_auto_group_invite_group_name
        if len(all_groups) == 0:
            logger.error(
                f"Error when inviting mandatory users: looked for group {group_to_invite} but did not find it."
            )
        else:
            try:
                required_participants_group = [
                    g for g in all_groups if g["handle"] == group_to_invite
                ][0]["id"]
                required_participants_group_members = (
                    client.slack_web_client.usergroups_users_list(
                        usergroup=required_participants_group,
                    )
                )["users"]
            except Exception as error:
                logger.error(
                    f"Error when formatting automatic invitees group name: {error}"
                )
            try:
                invite = client.slack_web_client.conversations_invite(
                    channel=channel_id,
                    users=",".join(required_participants_group_members),
                )
                logger.debug(f"\n{invite}\n")
                # Write audit log
                log.write(
                    incident_id=createdChannelDetails["name"],
                    event=f"Group {required_participants_group} invited to the incident channel automatically.",
                )
            except slack_sdk.errors.SlackApiError as error:
                logger.error(f"Error when inviting mandatory users: {error}")

    """
    External provider statuses (optional)
    """
    if config.incident_external_providers_enabled == "true":
        providers = str.split(str.lower(config.incident_external_providers_list), ",")
        for p in providers:
            ext_incidents = epi.ExternalProviderIncidents(
                provider=p,
                days_back=5,
                slack_channel=channel_id,
            )
            if p not in enabled_providers:
                logger.error(
                    f"Error sending external provider message to incident channel: {p} is not a valid provider - options are {enabled_providers}"
                )
            else:
                try:
                    pu_message = client.slack_web_client.chat_postMessage(
                        **ext_incidents.slack_message(),
                        text="",
                    )
                    logger.debug(f"\n{pu_message}\n")
                except slack_sdk.errors.SlackApiError as error:
                    logger.error(
                        f"Error sending external provider message to incident channel: {error}"
                    )

    """
    Post prompt for creating Statuspage incident
    """
    if config.statuspage_integration_enabled == "true":
        sp_components = sp_handler.StatuspageComponents()
        sp_components_list = sp_components.list_of_names()
        sp_starter_message_content = spslack.return_new_incident_message(
            channel_id, sp_components_list
        )
        try:
            sp_starter_message = client.slack_web_client.chat_postMessage(
                **sp_starter_message_content,
                text="",
            )
        except slack_sdk.errors.SlackApiError as error:
            logger.error(
                f"Error sending Statuspage prompt to the incident channel {channel_name}: {error}"
            )
        logger.info(f"Sending Statuspage prompt to {channel_name}.")
        # Update incident record with the Statuspage starter message timestamp
        logger.info(
            "Updating incident record in database with Statuspage message timestamp."
        )
        try:
            db.db_update_incident_sp_ts_col(
                channel_name,
                sp_starter_message["ts"],
            )
        except Exception as error:
            logger.fatal(f"Error writing entry to database: {error}")

    """
    If this is an internal incident, parse additional values
    """
    if internal and config.incident_auto_create_from_react_enabled == "true":
        original_channel = request_parameters["channel"]
        original_message_timestamp = request_parameters["original_message_timestamp"]
        formatted_timestamp = str.replace(original_message_timestamp, ".", "")
        link_to_message = f"https://{config.slack_workspace_id}.slack.com/archives/{original_channel}/p{formatted_timestamp}"
        try:
            client.slack_web_client.chat_postMessage(
                channel=channel_id,
                text="",
                blocks=[
                    {"type": "divider"},
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": ":warning: This incident was created via a reaction to a message.",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Here is a link to the original message: <{link_to_message}>",
                        },
                    },
                ],
            )
        except slack_sdk.errors.SlackApiError as error:
            logger.error(
                f"Error sending additional information to the incident channel {channel_name}: {error}"
            )
        logger.info(f"Sending additional information to {channel_name}.")
        # Message the channel where the react request came from to inform
        # regarding incident channel creation
        try:
            client.slack_web_client.chat_postMessage(
                channel=original_channel,
                text="",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"I've created the incident channel as requested: <#{channel_id}>",
                        },
                    },
                ],
            )
        except slack_sdk.errors.SlackApiError as error:
            logger.error(
                f"Error when trying to let {channel_name} know about an auto created incident: {error}"
            )


"""
Messaging Helpers
"""


def build_digest_notification(createdChannelDetails: Dict[str, str]) -> Dict[str, str]:
    """Formats the notification that will be
    sent to the digest channel

    Args:
        createdChannelDetails: dict[str, str]
        Expects: id, name

    Returns dict[str, str] containing the formatted message
    to be sent to Slack
    """
    variables = {
        "channel_id_var_placeholder": config.incidents_digest_channel,
        "channel_name_var_placeholder": createdChannelDetails["name"],
        "slack_workspace_id_var_placeholder": config.slack_workspace_id,
        "incident_guide_link_var_placeholder": config.incident_guide_link,
        "incident_postmortems_link_var_placeholder": config.incident_postmortems_link,
    }
    return tools.render_json(
        f"{config.templates_directory}incident_digest_notification.json", variables
    )


def build_incident_channel_boilerplate(
    createdChannelDetails: Dict[str, str]
) -> Dict[str, str]:
    """Formats the boilerplate messaging that will
    be added to all newly created incident channels.
    """
    variables = {
        "channel_id_var_placeholder": createdChannelDetails["id"],
        "incident_guide_link_var_placeholder": config.incident_guide_link,
        "incident_postmortems_link_var_placeholder": config.incident_postmortems_link,
    }
    return tools.render_json(
        f"{config.templates_directory}incident_channel_boilerplate.json", variables
    )


def build_post_resolution_message(channel: str, status: str) -> Dict[str, str]:
    """Formats the notification that will be
    sent when the incident is resolved

    Args:
        channel: str
        status: str

    Returns dict[str, str] containing the formatted message
    to be sent to Slack
    """
    variables = {
        "channel_id_var_placeholder": channel,
        "incident_guide_link_var_placeholder": config.incident_guide_link,
        "incident_postmortems_link_var_placeholder": config.incident_postmortems_link,
    }
    return tools.render_json(
        f"{config.templates_directory}incident_resolution_message.json", variables
    )


def build_role_update(channel: str, role: str, user: str) -> Dict[str, str]:
    """Formats the notification that will be
    sent when a role is claimed

    Args:
        channel: str
        role: str
        user: str

    Returns dict[str, str] containing the formatted message
    to be sent to Slack
    """
    variables = {
        "channel_id_var_placeholder": channel,
        "user_var_placeholder": user,
        "role_var_placeholder": role,
    }
    return tools.render_json(
        f"{config.templates_directory}incident_role_update.json", variables
    )


def build_severity_update(channel: str, severity: str) -> Dict[str, str]:
    """Formats the notification that will be
    sent when severity changes

    Args:
        channel: str
        severity: str

    Returns dict[str, str] containing the formatted message
    to be sent to Slack
    """
    severity_descriptions = tools.read_json_from_file(
        f"{config.templates_directory}severity_levels.json"
    )
    variables = {
        "channel_id_var_placeholder": channel,
        "severity_var_placeholder": severity.upper(),
        "severity_description_var_placeholder": severity_descriptions[severity],
    }
    return tools.render_json(
        f"{config.templates_directory}incident_severity_update.json", variables
    )


def build_status_update(channel: str, status: str) -> Dict[str, str]:
    """Formats the notification that will be
    sent when status changes

    Args:
        channel: str
        status: str

    Returns dict[str, str] containing the formatted message
    to be sent to Slack
    """
    variables = {
        "channel_id_var_placeholder": channel,
        "status_var_placeholder": status.title(),
    }
    return tools.render_json(
        f"{config.templates_directory}incident_status_update.json", variables
    )


def build_updated_digest_message(
    incident_id: str, status: str, severity: str
) -> Dict[str, list]:
    """Returns the blocks required for the initial incidents
    digest message with edits so we can update it when the status
    changes
    """
    if status == "resolved":
        header = ":white_check_mark: Resolved Incident :white_check_mark:"
        message = "This incident has been resolved. You can still check out the archived channel for context."
    else:
        header = ":bangbang: Ongoing Incident :bangbang:"
        message = "This incident is in progress. Current status is listed here. Join the channel for more information."

    variables = {
        "header_var_placeholder": header,
        "incident_id_var_placeholder": incident_id,
        "status_var_placeholder": status.title(),
        "severity_var_placeholder": severity.upper(),
        "message_var_placeholder": message,
        "slack_workspace_id_var_placeholder": config.slack_workspace_id,
        "incident_guide_link_var_placeholder": config.incident_guide_link,
        "incident_postmortems_link_var_placeholder": config.incident_postmortems_link,
    }
    return tools.render_json(
        f"{config.templates_directory}incident_digest_notification_update.json",
        variables,
    )


def build_user_role_notification(channel_id: str, role: str, user: str):
    """Returns the blocks required for messaging a user w/r/t
    details about their role when they are assigned a role
    during an incident
    """
    role_descriptions = tools.read_json_from_file(
        f"{config.templates_directory}role_definitions.json"
    )
    variables = {
        "channel_name_var_placeholder": channel_id,
        "role_description_var_placeholder": role_descriptions[role],
        "role_var_placeholder": role.replace("_", " ").title(),
        "user_var_placeholder": user,
    }
    return tools.render_json(
        f"{config.templates_directory}incident_user_role_dm.json", variables
    )


def build_public_status_update(
    incident_id: str,
    impacted_resources: str,
    message: str,
    timestamp: str = tools.fetch_timestamp(),
):
    """Returns the blocks required for a public status update for a
    given incident
    """
    header = ":warning: Incident Update"

    variables = {
        "header_var_placeholder": header,
        "timestamp_var_placeholder": timestamp,
        "incident_id_var_placeholder": incident_id,
        "impacted_resources_var_placeholder": impacted_resources,
        "message_var_placeholder": message,
    }
    return tools.render_json(
        f"{config.templates_directory}incident_public_status_update.json",
        variables,
    )
