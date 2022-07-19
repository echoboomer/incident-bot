import config
import datetime
import json
import logging

from bot.db import db
from bot.shared import tools
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from typing import Dict

logger = logging.getLogger(__name__)

# Initialize Slack clients
slack_web_client = WebClient(token=config.slack_bot_token)

"""
Reusable variables
"""
all_workspace_groups = slack_web_client.usergroups_list()
bot_user_id = slack_web_client.auth_test()["user_id"]
bot_user_name = slack_web_client.auth_test()["user"]


def get_channel_history(channel_id: str) -> str:
    """Return the history of a Slack channel as a json string object

    Keyword arguments:
    channel_id -- The ID of the Slack channel to retrieve history from
    """
    history_dict = slack_web_client.conversations_history(channel=channel_id)[
        "messages"
    ]
    history_dict_reversed = []
    for item in reversed(history_dict):
        history_dict_reversed.append(item)
    return json.dumps(history_dict_reversed)


def get_formatted_channel_history(channel_id: str, channel_name: str) -> str:
    """Return the history of a Slack channel as a formatted string

    Keyword arguments:
    channel_id -- The ID of the Slack channel to retrieve history from
    channel_name -- The name of the Slack channel to retrieve history from
    """
    users = slack_web_client.users_list()["members"]
    replaced_messages_string = replace_user_ids(get_channel_history(channel_id), users)
    formatted_channel_history = str()
    formatted_channel_history += f"Slack channel history for incident {channel_name}\n"
    for message in replaced_messages_string:
        user = message["user"]
        text = message["text"]
        timestamp = datetime.datetime.fromtimestamp(int(message["ts"].split(".")[0]))
        prefix = f"* {timestamp}"
        if "has joined the channel" in text:
            formatted_channel_history += f"{prefix} {user} joined the channel\n"
        elif "set the channel topic" in text:
            formatted_channel_history += f"{prefix} {user} {text}\n"
        elif "This content can't be displayed." in text:
            pass
        else:
            formatted_channel_history += f"{prefix} {user}: {text}\n"
    return formatted_channel_history


def get_message_content(conversation_id: str, ts: str):
    """
    Given a Slack conversation and a message timestamp,
    return information abou a message.
    """
    try:
        result = slack_web_client.conversations_history(
            channel=conversation_id, inclusive=True, oldest=ts, limit=1
        )
        return result["messages"][0]
    except SlackApiError as error:
        logger.error(f"Error retrieving Slack message: {error}")


def invite_user_to_channel(channel_id: str, user: str):
    """
    Invites a user to a Slack channel
    Checks if they're in it first
    """
    try:
        if (
            not user
            in slack_web_client.conversations_members(channel=channel_id)["members"]
        ):
            invite = slack_web_client.conversations_invite(
                channel=channel_id,
                users=user,
            )
            logger.debug(f"\n{invite}\n")
        logger.info("User already in channel. Skipping invite.")
    except SlackApiError as error:
        logger.error(f"Error when inviting user {user}: {error}")


def replace_user_ids(json_string: str, user_list: Dict[str, str]) -> str:
    """Replace a user's ID with their name and return a json string object"""
    for user in user_list:
        real_name = user["profile"]["real_name"]
        user_id = user["id"]
        json_string = json_string.replace(user_id, real_name)
    return json.loads(json_string)


def return_slack_channel_info() -> Dict[str, str]:
    """Return a list of Slack channels"""
    try:
        return slack_web_client.conversations_list(exclude_archived=True, limit=500)[
            "channels"
        ]
    except Exception as error:
        logger.error(f"Error getting channel list from Slack workspace: {error}")


def store_slack_user_list():
    """
    Retrieves list of users from Slack organization and stores them using a clean format
    to be retrieved locally to avoid querying the Slack API every time this data
    is desired
    """
    try:
        users_array = []
        for user in slack_web_client.users_list()["members"]:
            users_array.append(
                {
                    "name": user["name"],
                    "real_name": user["profile"]["real_name"],
                    "id": user["id"],
                }
            )
        jdata = sorted(users_array, key=lambda d: d["name"])
        # Delete if exists
        if db.Session.query(db.OperationalData).filter_by(id="slack_users").all():
            existing = (
                db.Session.query(db.OperationalData).filter_by(id="slack_users").one()
            )
            db.Session.delete(existing)
            db.Session.commit()
        # Store
        row = db.OperationalData(
            id="slack_users",
            json_data=jdata,
            updated_at=tools.fetch_timestamp(),
        )
        db.Session.add(row)
        db.Session.commit()
    except Exception as error:
        logger.error(f"Opdata row create failed for slack_users: {error}")
        db.Session.rollback()
    finally:
        db.Session.close()
