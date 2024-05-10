import asyncio
import re
from datetime import datetime
from typing import Dict

import config
import slack_sdk.errors
from bot.audit import log
from bot.exc import ConfigurationError
from bot.models.incident import (
    db_update_incident_created_at_col,
    db_update_incident_sp_ts_col,
    db_write_incident,
)
from bot.models.pager import read_pager_auto_page_targets
from bot.shared import tools
from bot.slack.client import (
    all_workspace_groups,
    slack_web_client,
    slack_workspace_id,
)
from bot.statuspage.slack import return_new_statuspage_incident_message
from bot.templates.incident.channel_boilerplate import (
    IncidentChannelBoilerplateMessage,
)
from bot.templates.incident.digest_notification import (
    IncidentChannelDigestNotification,
)
from bot.zoom.meeting import ZoomMeeting
from cerberus import Validator
from iblog import logger

# How many total characters are allowed in a Slack channel name?
# Limit the channel name to 76 to take this into account
channel_name_length_cap = 80
# How many characters does the incident prefix take up?
channel_name_prefix_length = len("inc-20211116-")
# How long can the provided description be?
incident_description_max_length = (
    channel_name_length_cap - channel_name_prefix_length
)

if not config.is_test_environment:
    from bot.slack.client import invite_user_to_channel


class RequestParameters:
    def __init__(
        self,
        channel: str,
        incident_description: str,
        severity: str,
        user: str = "",
        created_from_web: bool = False,
        is_security_incident: bool = False,
        private_channel: bool = False,
        message_reacted_to_content: str = "",
        original_message_timestamp: str = "",
    ):
        self.channel = channel
        self.incident_description = incident_description
        self.user = user
        self.severity = severity
        self.created_from_web = created_from_web
        self.is_security_incident = is_security_incident
        self.private_channel = private_channel
        self.message_reacted_to_content = message_reacted_to_content
        self.original_message_timestamp = original_message_timestamp

        if self.is_security_incident:
            self.private_channel = True

        self.as_dict = {
            "channel": self.channel,
            "incident_description": self.incident_description,
            "user": self.user,
            "severity": self.severity,
            "created_from_web": self.created_from_web,
            "is_security_incident": self.is_security_incident,
            "private_channel": self.private_channel,
            "message_reacted_to_content": self.message_reacted_to_content,
            "original_message_timestamp": self.original_message_timestamp,
        }

        self.validate()

    def validate(self):
        """Given a request supplied as dict[str, any], validate its
        fields.

        Returns bool indicating whether or not the service passes validation
        """
        schema = {
            "channel": {
                "required": True,
                "type": "string",
                "empty": False,
            },
            "incident_description": {
                "required": True,
                "type": "string",
                "empty": False,
            },
            "user": {
                "required": False,
                "type": "string",
            },
            "severity": {
                "required": True,
                "type": "string",
                "allowed": [
                    key for key, _ in config.active.severities.items()
                ],
                "empty": False,
            },
            "created_from_web": {
                "required": True,
                "type": "boolean",
                "empty": False,
            },
            "is_security_incident": {
                "required": True,
                "type": "boolean",
                "empty": False,
            },
            "private_channel": {
                "required": True,
                "type": "boolean",
                "empty": False,
            },
            "message_reacted_to_content": {
                "required": False,
                "type": "string",
            },
            "original_message_timestamp": {
                "required": False,
                "type": "string",
            },
        }
        v = Validator(schema)
        if not v.validate(self.as_dict, schema):
            raise ConfigurationError(
                f"Request parameters has errors: {v.errors}"
            )


class Incident:
    """Instantiates an incident"""

    def __init__(self, request_parameters: RequestParameters):
        self.request_parameters = request_parameters
        # Log transaction
        self.log()
        # Set instance variables
        self.incident_description = (
            self.request_parameters.incident_description
        )
        self.channel_name = self.__format_channel_name()
        if not config.is_test_environment:
            self.channel = self.__create_incident_channel()
            self.channel_details = self.channel.get("channel")
            self.created_channel_details = {
                "incident_description": self.request_parameters.incident_description,
                "id": self.channel_details.get("id"),
                "name": self.channel_details.get("name"),
                "is_security_incident": self.request_parameters.is_security_incident,
                "private_channel": self.request_parameters.private_channel,
            }
            self.conference_bridge = self.__generate_conference_link()
        else:
            self.channel_details = {}
            self.created_channel_details = {
                "name": self.channel_details.get("name"),
                "is_security_incident": False,
                "private_channel": False,
            }
            self.conference_bridge = "mock"

    def log(self):
        request_log = {
            "user": self.request_parameters.user,
            "channel": self.request_parameters.channel,
            "incident_description": self.request_parameters.incident_description,
        }
        logger.info(
            f"Request received from Slack to start a new incident: {request_log}"
        )

    def __create_incident_channel(self):
        """
        Create incident channel in Slack for an incident
        """
        try:
            # Call the conversations.create method using the WebClient
            # conversations_create requires the channels:manage bot scope
            channel = slack_web_client.conversations_create(
                # The name of the conversation
                name=self.channel_name,
                is_private=self.request_parameters.private_channel,
            )
            # Log the result which includes information like the ID of the conversation
            logger.debug(f"\n{channel}\n")
            logger.info(f"Creating incident channel: {self.channel_name}")
        except slack_sdk.errors.SlackApiError as error:
            logger.error(f"Error creating incident channel: {error}")
        return channel

    def __format_channel_name(self) -> str:
        # Remove any special characters (allow only alphanumeric)
        formatted_channel_name_suffix = re.sub(
            "[^A-Za-z0-9\s]",
            "",
            self.incident_description,
        )
        # Replace any spaces with dashes
        formatted_channel_name_suffix = formatted_channel_name_suffix.replace(
            " ", "-"
        ).lower()

        datefmt = self.__format_date()
        prefix = config.default_incident_channel_name_prefix

        if config.active.options.get("channel_naming"):
            if config.active.options.get("channel_naming").get(
                "channel_name_prefix"
            ):
                prefix = config.active.options.get("channel_naming").get(
                    "channel_name_prefix"
                )

        return f"{prefix}-{datefmt}-{formatted_channel_name_suffix}"

    def __format_date(self) -> str:
        # Allowed statements for date format
        default_time_format = "%Y%m%d%H%M"
        default_timestamp = datetime.now().strftime(default_time_format)

        if config.active.options.get("channel_naming"):
            if config.active.options.get("channel_naming").get(
                "time_format_in_channel_name"
            ):
                f = config.active.options.get("channel_naming").get(
                    "time_format_in_channel_name"
                )
                if not tools.validate_date_format_string(f):
                    logger.warning(
                        "Error setting format for timestamp in incident channel: {} is not valid so the default of {} will be used.".format(
                            f,
                            default_time_format,
                        )
                    )
                    return default_timestamp
                else:
                    return datetime.strftime(datetime.now(), f)
        else:
            return default_timestamp

    def __generate_conference_link(self) -> str:
        if (
            "zoom" in config.active.integrations
            and config.active.integrations.get("zoom").get(
                "auto_create_meeting", False
            )
        ):
            return ZoomMeeting().url
        else:
            return config.active.options.get("conference_bridge_link")


"""
Core Functionality
"""


def create_incident(
    request_parameters: RequestParameters,
    internal: bool = False,
) -> str:
    """
    Create an incident
    """
    incident_description = request_parameters.incident_description
    user = request_parameters.user
    severity = request_parameters.severity
    if incident_description != "":
        if len(incident_description) < incident_description_max_length:
            incident = Incident(request_parameters)
            created_channel_details = incident.created_channel_details
            """
            Notify incidents digest channel
            """
            try:
                digest_message = slack_web_client.chat_postMessage(
                    **IncidentChannelDigestNotification.create(
                        incident_channel_details=created_channel_details,
                        conference_bridge=incident.conference_bridge,
                        severity=severity,
                    ),
                    text="New Incident",
                )
                logger.debug(f"\n{digest_message}\n")
            except slack_sdk.errors.SlackApiError as error:
                logger.error(
                    f"Error sending message to incident digest channel: {error}"
                )
            logger.info(
                "Sending message to digest channel for: {}".format(
                    created_channel_details["name"]
                )
            )
            """
            Set incident channel topic
            """
            topic_boilerplate = (
                incident.conference_bridge
                if config.active.options.get("channel_topic").get(
                    "set_to_meeting_link"
                )
                else config.active.options.get("channel_topic").get("default")
            )
            try:
                topic = slack_web_client.conversations_setTopic(
                    channel=created_channel_details["id"],
                    topic=topic_boilerplate,
                )
                logger.debug(f"\n{topic}\n")
            except slack_sdk.errors.SlackApiError as error:
                logger.error(f"Error setting incident channel topic: {error}")
            """
            Send boilerplate info to incident channel
            """
            try:
                bp_message = slack_web_client.chat_postMessage(
                    **IncidentChannelBoilerplateMessage.create(
                        incident_channel_details=created_channel_details,
                        severity=severity,
                    ),
                    text="Details",
                )
                logger.debug(f"\n{bp_message}\n")
            except slack_sdk.errors.SlackApiError as error:
                logger.error(
                    f"Error sending message to incident channel: {error}"
                )
            # Pin the boilerplate message to the channel for quick access.
            slack_web_client.pins_add(
                channel=created_channel_details["id"],
                timestamp=bp_message["ts"],
            )
            """
            Post conference link in the channel upon creation
            """
            try:
                conference_bridge_message = slack_web_client.chat_postMessage(
                    channel=created_channel_details["id"],
                    text=f":busts_in_silhouette: Please join the conference here: {incident.conference_bridge}",
                    blocks=[
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": ":busts_in_silhouette: Please join the conference here.",
                            },
                        },
                        {"type": "divider"},
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": incident.conference_bridge,
                            },
                        },
                    ],
                )
                slack_web_client.pins_add(
                    channel=created_channel_details["id"],
                    timestamp=conference_bridge_message["message"]["ts"],
                )
            except slack_sdk.errors.SlackApiError as error:
                logger.error(
                    f"Error sending conference bridge link to channel: {error}"
                )
            """
            Write incident entry to database
            """
            logger.info(
                "Writing incident entry to database for {}...".format(
                    created_channel_details["name"]
                )
            )
            try:
                db_write_incident(
                    incident_id=created_channel_details["name"],
                    channel_id=created_channel_details["id"],
                    channel_name=created_channel_details["name"],
                    status="investigating",
                    severity=severity,
                    bp_message_ts=bp_message["ts"],
                    dig_message_ts=digest_message["ts"],
                    is_security_incident=created_channel_details[
                        "is_security_incident"
                    ],
                    channel_description=created_channel_details[
                        "incident_description"
                    ],
                    conference_bridge=incident.conference_bridge,
                )
            except Exception as error:
                logger.fatal(f"Error writing entry to database: {error}")
            # Tag the incident with initial creation timestamp in human readable format
            try:
                db_update_incident_created_at_col(
                    incident_id=created_channel_details["name"],
                    created_at=tools.fetch_timestamp(),
                )
            except Exception as error:
                logger.fatal(
                    f"Error updating incident entry with creation timestamp: {error}"
                )

            asyncio.run(
                handle_incident_optional_features(
                    request_parameters, created_channel_details, internal
                )
            )

            # Invite the user who opened the channel to the channel.
            invite_user_to_channel(created_channel_details["id"], user)
            # Return for view method
            temp_channel_id = created_channel_details["id"]

            # Write audit log
            log.write(
                incident_id=created_channel_details["name"],
                event="Incident created.",
                user=user,
            )
            return f"I've created the incident channel: <#{temp_channel_id}>"
        else:
            return f"Total channel length cannot exceed 80 characters. Please use a short description less than {incident_description_max_length} characters. You used {len(incident_description)}."
    else:
        return "Please provide a description for the channel."


async def handle_incident_optional_features(
    request_parameters: RequestParameters,
    created_channel_details: Dict[str, str],
    internal: bool = False,
):
    """
    For new incidents, handle optional features
    """
    channel_id = created_channel_details["id"]
    channel_name = created_channel_details["name"]

    """
    Invite required participants (optional)
    """
    if "auto_invite_groups" in config.active.options:
        for gr in config.active.options.get("auto_invite_groups"):
            all_groups = all_workspace_groups.get("usergroups")
            if len(all_groups) == 0:
                logger.error(
                    f"Error when inviting mandatory users: looked for group {gr} but did not find it."
                )
            else:
                try:
                    required_participants_group = [
                        g for g in all_groups if g["handle"] == gr
                    ][0]["id"]
                    required_participants_group_members = (
                        slack_web_client.usergroups_users_list(
                            usergroup=required_participants_group,
                        )
                    )["users"]
                except Exception as error:
                    logger.error(
                        f"Error when formatting automatic invitees group name: {error}"
                    )
                try:
                    invite = slack_web_client.conversations_invite(
                        channel=channel_id,
                        users=",".join(required_participants_group_members),
                    )
                    logger.debug(f"\n{invite}\n")
                    # Write audit log
                    log.write(
                        incident_id=created_channel_details["name"],
                        event=f"Group {gr} invited to the incident channel automatically.",
                    )
                except slack_sdk.errors.SlackApiError as error:
                    logger.error(f"Error when inviting auto users: {error}")

    """
    Post prompt for creating Statuspage incident if enabled
    """
    if "statuspage" in config.active.integrations:
        sp_starter_message_content = return_new_statuspage_incident_message(
            channel_id
        )
        try:
            sp_starter_message = slack_web_client.chat_postMessage(
                **sp_starter_message_content,
                text="",
            )
            slack_web_client.pins_add(
                channel=channel_id,
                timestamp=sp_starter_message["ts"],
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
            db_update_incident_sp_ts_col(
                incident_id=channel_name,
                ts=sp_starter_message["ts"],
            )
        except Exception as error:
            logger.fatal(f"Error writing entry to database: {error}")

    """
    If this is an internal incident, parse additional values
    """
    if internal and config.active.options.get("create_from_reaction"):
        original_channel = request_parameters.channel
        original_message_timestamp = (
            request_parameters.original_message_timestamp
        )
        formatted_timestamp = str.replace(original_message_timestamp, ".", "")
        link_to_message = f"https://{slack_workspace_id}.slack.com/archives/{original_channel}/p{formatted_timestamp}"
        try:
            slack_web_client.chat_postMessage(
                channel=channel_id,
                text=f":warning: This incident was created via a reaction to a message. Here is a link to the original message: <{link_to_message}>",
                blocks=[
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
                            "text": f"Here is a link to the original message: <{link_to_message}>\nThe reaction was added by <@{request_parameters.user}>.",
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
            slack_web_client.chat_postMessage(
                channel=original_channel,
                text=f"I've created the incident channel as requested: <#{channel_id}>",
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
    Page groups that are required to be automatically paged (optional)
    """
    if "pagerduty" in config.active.integrations:
        from bot.pagerduty import api as pd_api

        auto_page_targets = read_pager_auto_page_targets()
        if len(auto_page_targets) != 0:
            for i in auto_page_targets:
                for k, v in i.items():
                    logger.info(f"Paging {k}...")
                    # Write audit log
                    log.write(
                        incident_id=created_channel_details["name"],
                        event=f"Created PagerDuty incident for team {k}.",
                    )
                    pd_api.page(
                        ep_name=v,
                        priority="low",
                        channel_name=created_channel_details["name"],
                        channel_id=created_channel_details["id"],
                        paging_user="auto",
                    )
    """
    Provide additional information if this is a security incidents (optional)
    """
    if request_parameters.is_security_incident:
        original_channel = request_parameters.channel
        original_message_timestamp = (
            request_parameters.original_message_timestamp
        )
        formatted_timestamp = str.replace(original_message_timestamp, ".", "")
        link_to_message = f"https://{slack_workspace_id}.slack.com/archives/{original_channel}/p{formatted_timestamp}"
        try:
            slack_web_client.chat_postMessage(
                channel=channel_id,
                text=f":warning: This incident was created via a reaction to a message. Here is a link to the original message: <{link_to_message}>",
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": ":warning: This incident was flagged as a security incident.",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "The channel is private. If you wish to add others, you must invite them.",
                        },
                    },
                ],
            )
        except slack_sdk.errors.SlackApiError as error:
            logger.error(
                f"Error sending additional information to the incident channel {channel_name}: {error}"
            )

    """
    If a Jira incident should be created automatically, create it
    """
    if (
        "atlassian" in config.active.integrations
        and "jira" in config.active.integrations.get("atlassian")
    ):
        if (
            config.active.integrations.get("atlassian")
            .get("jira")
            .get("auto_create_incident")
        ):
            from bot.jira.issue import JiraIssue

            try:
                issue_obj = JiraIssue(
                    incident_id=channel_name,
                    description=channel_name,
                    issue_type=config.active.integrations.get("atlassian")
                    .get("jira")
                    .get("auto_create_incident_type"),
                    summary=created_channel_details["incident_description"],
                )
                resp = issue_obj.new()
                if resp is not None:
                    from bot.models.incident import db_update_jira_issues_col

                    issue_link = "{}/browse/{}".format(
                        config.atlassian_api_url, resp.get("key")
                    )
                    db_update_jira_issues_col(
                        channel_id=channel_id,
                        issue_link=issue_link,
                    )

                    from bot.slack.messages import new_jira_message

                    try:
                        resp = slack_web_client.chat_postMessage(
                            channel=channel_id,
                            blocks=new_jira_message(
                                key=resp.get("key"),
                                summary=created_channel_details[
                                    "incident_description"
                                ],
                                type=config.active.integrations.get(
                                    "atlassian"
                                )
                                .get("jira")
                                .get("auto_create_incident_type"),
                                link=issue_link,
                            ),
                            text="A Jira issue has been created for this incident: {}".format(
                                resp.get("self")
                            ),
                        )
                        slack_web_client.pins_add(
                            channel=channel_id,
                            timestamp=resp["ts"],
                        )
                    except Exception as error:
                        logger.error(
                            f"Error sending Jira issue message for {channel_name}: {error}"
                        )
            except Exception as error:
                logger.error(
                    f"Error creating Jira incident for {channel_name}: {error}"
                )
