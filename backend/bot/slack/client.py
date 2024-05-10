import config
import datetime
import json

from bot.exc import IndexNotFoundError
from bot.models.pg import OperationalData, Session
from bot.shared import tools
from iblog import logger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy import update

from typing import Any, Dict, List

# Initialize Slack clients
slack_web_client = WebClient(token=config.slack_bot_token)

"""
Reusable variables
"""
all_workspace_groups = (
    slack_web_client.usergroups_list()
    if not config.is_test_environment
    else []
)
bot_user_id = (
    slack_web_client.auth_test().get("user_id")
    if not config.is_test_environment
    else "test"
)
bot_user_name = (
    slack_web_client.auth_test().get("user")
    if not config.is_test_environment
    else "test"
)
slack_workspace_id = (
    slack_web_client.auth_test()
    .get("url")
    .replace("https://", "")
    .split(".")[0]
    if not config.is_test_environment
    else "test"
)

# Users to skip invites for
skip_invite_for_users = ["api", "web"]


"""
Conversations
"""


def get_channel_history(channel_id: str) -> str:
    """Return the history of a Slack channel as a json string object

    Keyword arguments:
    channel_id -- The ID of the Slack channel to retrieve history from
    """
    history_dict_list = []

    try:
        res = slack_web_client.conversations_history(
            channel=channel_id, limit=200
        )

        while res:
            history_dict_list += res.get("messages")

            if res.get("has_more"):
                res = slack_web_client.conversations_history(
                    channel=channel_id,
                    limit=200,
                    cursor=res.get("response_metadata").get("next_cursor"),
                )
            else:
                res = None
    except Exception as error:
        logger.error(
            f"Error getting conversations history from channel #{get_channel_name(channel_id=channel_id)}: {error}"
        )

    history_dict_reversed = []

    for item in reversed(history_dict_list):
        history_dict_reversed.append(item)

    return json.dumps(history_dict_reversed)


def get_channel_list() -> Dict[str, str]:
    """Return a list of Slack channels"""
    channels = []

    try:
        res = slack_web_client.conversations_list(
            exclude_archived=True,
            limit=1000,
        )

        while res:
            channels += res.get("channels")

            if res.get("response_metadata").get("next_cursor") != "":
                res = slack_web_client.conversations_list(
                    exclude_archived=True,
                    limit=1000,
                    cursor=res.get("response_metadata").get("next_cursor"),
                )
            else:
                res = None
    except Exception as error:
        logger.error(
            f"Error getting channel list from Slack workspace: {error}"
        )

    logger.info(f"Found {len(channels)} Slack channels")
    return channels


def get_channel_name(channel_id: str) -> str:
    # Get channel name by id
    channels = get_slack_channel_list_db().get("json_data")
    index = tools.find_index_in_list(channels, "id", channel_id)
    if index == -1:
        raise IndexNotFoundError(
            "Could not find index for channel in Slack conversations list"
        )
    return channels[index].get("name")


def get_digest_channel_id() -> str:
    # Get channel id of the incidents digest channel to send updates to
    channels = get_slack_channel_list_db().get("json_data")
    index = tools.find_index_in_list(
        channels, "name", config.active.digest_channel
    )
    if index == -1:
        raise IndexNotFoundError(
            "Could not find index for digest channel in Slack conversations list"
        )
    return channels[index].get("id")


def get_formatted_channel_history(channel_id: str, channel_name: str) -> str:
    """Return the history of a Slack channel as a formatted string

    Keyword arguments:
    channel_id -- The ID of the Slack channel to retrieve history from
    channel_name -- The name of the Slack channel to retrieve history from
    """
    users = slack_web_client.users_list()["members"]
    replaced_messages_string = replace_user_ids(
        get_channel_history(channel_id), users
    )

    formatted_channel_history = str()
    formatted_channel_history += (
        f"Slack channel history for incident {channel_name}\n"
    )

    for message in replaced_messages_string:
        user = message["user"]
        text = message["text"]
        timestamp = datetime.datetime.fromtimestamp(
            int(message["ts"].split(".")[0])
        )
        prefix = f"* {timestamp}"
        if "has joined the channel" in text:
            formatted_channel_history += (
                f"{prefix} {user} joined the channel\n"
            )
        elif "set the channel topic" in text:
            formatted_channel_history += f"{prefix} {user} {text}\n"
        elif "This content can't be displayed." in text:
            pass
        else:
            formatted_channel_history += f"{prefix} {user}: {text}\n"

    return formatted_channel_history


def get_conversation_members(channel_id: str) -> List[str]:
    """
    Retrieves Slack users as members of a channel (conversation)
    """
    members = []

    try:
        res = slack_web_client.conversations_members(
            channel=channel_id, limit=200
        )

        while res:
            members += res.get("members")

            if res.get("response_metadata").get("next_cursor") != "":
                res = slack_web_client.conversations_members(
                    channel=channel_id,
                    cursor=res.get("response_metadata").get("next_cursor"),
                    limit=200,
                )
            else:
                res = None
    except Exception as error:
        logger.error(
            f"Error getting member list from channel #{get_channel_name(channel_id=channel_id)}: {error}"
        )

    return members


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


def get_slack_channel_list_db() -> List[Dict[str, Any]]:
    try:
        return (
            Session.query(OperationalData)
            .filter(OperationalData.id == "slack_channels")
            .one()
            .serialize()
        )
    except Exception as error:
        logger.error(
            f"Error retrieving list of Slack channels from db: {error}"
        )
    finally:
        Session.close()
        Session.remove()


def invite_user_to_channel(channel_id: str, user: str):
    """
    Invites a user to a Slack channel
    Checks if they're in it first
    """
    try:
        if (
            not user in get_conversation_members(channel_id)
            and user not in skip_invite_for_users
        ):
            invite = slack_web_client.conversations_invite(
                channel=channel_id,
                users=user,
            )
            logger.debug(f"\n{invite}\n")
        logger.info(
            f"User already in channel or is one of {skip_invite_for_users}. Skipping invite."
        )
    except SlackApiError as error:
        logger.error(f"Error when inviting user {user}: {error}")


def store_slack_channel_list_db():
    """
    Retrieves information about Slack channels for a workspace and stores
    it in the database
    """
    try:
        record_name = "slack_channels"

        # Create the row if it doesn't exist
        if not Session.query(OperationalData).filter_by(id=record_name).all():
            try:
                row = OperationalData(id=record_name)
                Session.add(row)
                Session.commit()
            except Exception as error:
                logger.error(
                    f"Opdata row create failed for {record_name}: {error}"
                )
        Session.execute(
            update(OperationalData)
            .where(OperationalData.id == record_name)
            .values(
                json_data=get_channel_list(),
                updated_at=tools.fetch_timestamp(),
            )
        )
        Session.commit()
        logger.info("Stored current Slack channels in database...")
    except Exception as error:
        logger.error(f"Opdata row edit failed for {record_name}: {error}")
        Session.rollback()
    finally:
        Session.close()


"""
Users
"""


def check_bot_user_in_digest_channel():
    """
    Adds bot user to digest channel if not already present
    """
    digest_channel_id = get_digest_channel_id()
    if (
        bot_user_id
        not in slack_web_client.conversations_members(
            channel=digest_channel_id
        )["members"]
    ):
        try:
            slack_web_client.conversations_join(channel=digest_channel_id)
            logger.info(
                f"Added bot user to digest channel #{get_channel_name(channel_id=digest_channel_id)}"
            )
        except SlackApiError as error:
            logger.error(
                f"Error auto joining bot user to digest channel: {error}"
            )
    else:
        logger.info(
            f"Bot user is already present in digest channel #{get_channel_name(channel_id=digest_channel_id)}"
        )


def check_user_in_group(user_id: str, group_name: str) -> bool:
    """Provided a user ID and a group name, return a bool indicating
    whether or not the user is in the group.
    """
    all_groups = all_workspace_groups.get("usergroups")
    try:
        target_group = [g for g in all_groups if g["handle"] == group_name]
        if len(target_group) == 0:
            logger.error(f"Couldn't find group {group_name}")
            return False
        target_group_members = slack_web_client.usergroups_users_list(
            usergroup=target_group[0].get("id"),
        ).get("users")
        if user_id in target_group_members:
            return True
        return False
    except Exception as error:
        logger.error(
            f"Error looking for user {user_id} in group {group_name}: {error}"
        )


def get_slack_user(user_id: str) -> dict | None:
    """
    Get a single user from a user ID

    This is done against the local database so it won't work unless the job to store
    slack user data has been run
    """
    ulist = Session.query(OperationalData).filter_by(id="slack_users").one()
    for obj in ulist.json_data:
        if user_id in obj.values():
            return obj
    return None


def get_slack_users() -> List[Dict[str, Any]]:
    """
    Retrieves Slack users from a workspace using pagination
    """
    users = []

    try:
        res = slack_web_client.users_list()

        while res:
            users += res.get("members")

            if res.get("response_metadata").get("next_cursor") != "":
                res = slack_web_client.users_list(
                    cursor=res.get("response_metadata").get("next_cursor")
                )
            else:
                res = None
    except Exception as error:
        logger.error(f"Error getting user list from Slack workspace: {error}")

    users_array = [
        {
            "name": user["name"],
            "real_name": user["profile"]["real_name"],
            "email": user['profile'].get("email"), # this requires user:read.email scope
            "id": user["id"],
        }
        for user in users
    ]

    jdata = sorted(users_array, key=lambda d: d["name"])

    logger.info(f"Found {len(users_array)} Slack users")

    return jdata


def replace_user_ids(json_string: str, user_list: Dict[str, str]) -> str:
    """Replace a user's ID with their name and return a json string object"""
    for user in user_list:
        real_name = user["profile"]["real_name"]
        user_id = user["id"]
        json_string = json_string.replace(user_id, real_name)

    return json.loads(json_string)


def store_slack_user_list_db():
    """
    Retrieves list of users from Slack organization and stores them using a clean format
    to be retrieved locally to avoid querying the Slack API every time this data
    is desired
    """
    try:
        # Delete if exists
        if Session.query(OperationalData).filter_by(id="slack_users").all():
            existing = (
                Session.query(OperationalData)
                .filter_by(id="slack_users")
                .one()
            )
            Session.delete(existing)
            Session.commit()

        # Store
        row = OperationalData(
            id="slack_users",
            json_data=get_slack_users(),
            updated_at=tools.fetch_timestamp(),
        )

        Session.add(row)
        Session.commit()
        logger.info("Stored current Slack users in database...")
    except Exception as error:
        logger.error(f"Opdata row create failed for slack_users: {error}")
        Session.rollback()
    finally:
        Session.close()
