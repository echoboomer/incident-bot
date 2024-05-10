import asyncio
import config
import requests
import slack_sdk

from bot.exc import ConfigurationError
from bot.incident import actions as inc_actions, incident
from bot.incident.action_parameters import ActionParametersSlack
from bot.models.incident import (
    db_read_incident,
    db_read_recent_incidents,
    db_update_incident_status_col,
)
from bot.models.pager import read_pager_auto_page_targets
from bot.scheduler import scheduler
from bot.shared import tools
from bot.slack.client import (
    get_slack_user,
    slack_web_client,
    slack_workspace_id,
)
from bot.slack.helpers import DigestMessageTracking
from bot.slack.incident_logging import write as write_content
from bot.slack.messages import (
    help_menu,
    incident_list_message,
    job_list_message,
)
from iblog import logger
from slack_bolt import App
from slack_sdk.errors import SlackApiError
from typing import Any, Dict


## The xoxb oauth token for the bot is called here to provide bot privileges.
app = App(token=config.slack_bot_token)


@app.error
def custom_error_handler(error, body, logger):
    logger.exception(f"Error: {error}")
    logger.debug(f"Request body: {body}")


from . import modals

tracking = DigestMessageTracking()


@app.event("message")
def handle_message_events(body, logger):
    # This generates errors if absent. I don't know why.
    pass


"""
Handle Mentions
"""


@app.event("app_mention")
def handle_mention(body, say, logger):
    message = body.get("event").get("text").split(" ")
    user = body["event"]["user"]
    logger.debug(body)

    if len(message) == 1:
        # This is just a user mention and the bot shouldn't really do anything.
        return

    match message[1]:
        case "help":
            say(blocks=help_menu(), text="")
        case "diag":
            startup_message = config.startup_message(
                workspace=slack_workspace_id, wrap=True
            )
            say(channel=user, text=startup_message)
        case "edit":
            if len(message) > 2:
                match message[2]:
                    case "incident":
                        if len(message) > 3:
                            inc = message[3]
                            try:
                                incd = db_read_incident(
                                    incident_id=inc,
                                    return_json=True,
                                )
                            except Exception:
                                say(f"Incident *{inc}* does not exist.")

                                return

                            if len(message) > 4:
                                match message[4]:
                                    case "set-status":
                                        if len(message) > 5:
                                            st = message[5]
                                            if st in config.active.statuses:
                                                if incd.get("status") == st:
                                                    say(
                                                        f"*{inc}* is already `{st}`."
                                                    )

                                                    return
                                                try:
                                                    db_update_incident_status_col(
                                                        st,
                                                        incident_id=incd.get(
                                                            "incident_id"
                                                        ),
                                                    )
                                                except Exception as error:
                                                    say(
                                                        f"Error updating *{inc}*: {error}"
                                                    )

                                                    return

                                                say(
                                                    f"*{inc}* status updated to `{st}`."
                                                )
                                            else:
                                                say(
                                                    f"`{st}` is not a valid status. Try: `{config.active.statuses}`"
                                                )
                                        else:
                                            say(
                                                f"The command `edit incident <incident-id> set-status` requires at least one argument."
                                            )
                                    case _:
                                        say(
                                            f"The command `edit incident <incident-id>` does not have a subcommand `{message[4]}`."
                                        )
                            else:
                                say(
                                    f"The command `edit incident <incident-id>` requires at least one argument."
                                )
                        else:
                            say(
                                f"The command `edit incident` requires at least one argument."
                            )
                    case _:
                        say(
                            f"The command `edit` does not have a subcommand `{message[2]}`."
                        )
            else:
                say(f"The command `edit` requires at least one argument.")
        case "lsoi":
            database_data = db_read_recent_incidents(
                limit=config.show_most_recent_incidents_app_home_limit
            )
            resp = incident_list_message(database_data, all=False)
            say(blocks=resp, text="")
        case "pager":
            if "pagerduty" in config.active.integrations:
                from bot.pagerduty import api as pd_api

                pd_oncall_data = pd_api.find_who_is_on_call()
                if pd_oncall_data == {}:
                    say(
                        text="Hmm... I'm unable to get that information from PagerDuty - when I looked for schedules, I couldn't find any. Check my logs for additional information."
                    )
                else:
                    # Header
                    say(
                        blocks=[
                            {
                                "type": "header",
                                "text": {
                                    "type": "plain_text",
                                    "text": ":pager: Who is on call right now?",
                                },
                            },
                            {"type": "divider"},
                        ]
                    )

                    # Iterate over schedules
                    if pd_oncall_data is not {}:
                        # Get length of returned objects
                        # If returned objects is greater than 5, paginate over them 5 at a time and include 5 in each message
                        # Send a separate message for each grouping of 5 to avoid block limits from the Slack API
                        for page in tools.paginate_dictionary(
                            pd_oncall_data.items(),
                            config.slack_items_pagination_per_page,
                        ):
                            base_block = []

                            for key, value in page:
                                options = []
                                for item in value:
                                    if item.get("slack_user_id") != []:
                                        user_mention = item.get(
                                            "slack_user_id"
                                        )[0]
                                    else:
                                        user_mention = item.get("user")
                                    options.append(
                                        {
                                            "text": {
                                                "type": "plain_text",
                                                "text": "{} {}".format(
                                                    item.get(
                                                        "escalation_level"
                                                    ),
                                                    item.get("user"),
                                                ),
                                            },
                                            "value": user_mention,
                                        },
                                    )
                                base_block.append(
                                    {
                                        "type": "section",
                                        "block_id": "ping_oncall_{}".format(
                                            tools.random_string_generator()
                                        ),
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": f"*{key}*",
                                        },
                                        "accessory": {
                                            "type": "overflow",
                                            "options": options,
                                            "action_id": "incident.add_on_call_to_channel",
                                        },
                                    }
                                )
                            say(blocks=base_block, text="")
                    else:
                        say(
                            text="There are no results from PagerDuty to display."
                        )

                    # Footer
                    say(
                        blocks=[
                            {
                                "type": "context",
                                "elements": [
                                    {
                                        "type": "image",
                                        "image_url": pd_api.image_url,
                                        "alt_text": "pagerduty",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"This information is sourced from PagerDuty and is accurate as of {tools.fetch_timestamp()}.",
                                    },
                                ],
                            }
                        ]
                    )
            elif config.active.integrations.get(
                "atlassian"
            ) and config.active.integrations.get("atlassian").get("opsgenie"):
                from bot.opsgenie import api as og_api

                sess = og_api.OpsgenieAPI()
                og_oncall_data = sess.list_rotations()

                if og_oncall_data:
                    # Header
                    say(
                        blocks=[
                            {
                                "type": "header",
                                "text": {
                                    "type": "plain_text",
                                    "text": ":pager: Who is on call right now?",
                                },
                            },
                            {"type": "divider"},
                        ]
                    )

                    base_block = []

                    # Iterate over schedules
                    for item in og_oncall_data:
                        options = []
                        for user in item.get("participants"):
                            options.append(
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": user.get("username"),
                                    },
                                    "value": user.get("username"),
                                },
                            )
                        base_block.append(
                            {
                                "type": "section",
                                "block_id": "ping_oncall_{}".format(
                                    tools.random_string_generator()
                                ),
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"*{item.get('name')}*",
                                },
                                "accessory": {
                                    "type": "overflow",
                                    "options": options,
                                    "action_id": "incident.add_on_call_to_channel",
                                },
                            }
                        )
                    say(blocks=base_block, text="")
                else:
                    say(
                        text="No data regarding schedule rotations was returned from Opsgnie."
                    )

                # Footer
                say(
                    blocks=[
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "image",
                                    "image_url": og_api.image_url,
                                    "alt_text": "opsgenie",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": f"This information is sourced from Opsgenie and is accurate as of {tools.fetch_timestamp()}.",
                                },
                            ],
                        }
                    ]
                )
            else:
                say(
                    text="No upstream platform configurations are present. I cannot provide information as a result."
                )
        case "scheduler":
            match message[2]:
                case "list":
                    jobs = scheduler.process.list_jobs()
                    resp = job_list_message(jobs)
                    say(blocks=resp, text="")
                case "delete":
                    if len(message) < 4:
                        say(text="Please provide the ID of a job to delete.")
                    else:
                        job_title = message[3]
                        delete_job = scheduler.process.delete_job(job_title)
                        if delete_job != None:
                            say(
                                f"Could not delete the job {job_title}: {delete_job}"
                            )
                        else:
                            say(f"Deleted job: *{job_title}*")
                case _:
                    say(
                        f"The command `scheduler` does not have a subcommand `{message[2]}`"
                    )
        case "ping":
            say(text="pong")
        case "version":
            say(text=f"I am currently running version: {config.__version__}")
        case _:
            resp = " ".join(message[1:])
            say(text=f"Sorry, I don't know the command `{resp}` yet.")


"""
Incident Management Actions
"""


def parse_action(body) -> Dict[str, Any]:
    return ActionParametersSlack(
        payload={
            "actions": body["actions"],
            "channel": body["channel"],
            "message": body["message"],
            "state": body["state"],
            "user": body["user"],
        }
    )


@app.action("incident.export_chat_logs")
def handle_incident_export_chat_logs(ack, body):
    logger.debug(body)
    ack()
    asyncio.run(
        inc_actions.export_chat_logs(action_parameters=parse_action(body))
    )


@app.action("incident.add_on_call_to_channel")
def handle_incident_add_on_call(ack, body, say):
    logger.debug(body)
    ack()
    user = body["user"]["id"]
    say(
        channel=user,
        text="Hi! If you want to page someone, use my shortcut 'Incident Bot Pager' instead!",
    )


@app.action("incident.archive_incident_channel")
def handle_incident_archive_incident_channel(ack, body):
    logger.debug(body)
    ack()
    asyncio.run(
        inc_actions.archive_incident_channel(
            action_parameters=parse_action(body)
        )
    )


@app.action("incident.assign_role")
def handle_incident_assign_role(ack, body):
    logger.debug(body)
    ack()
    asyncio.run(inc_actions.assign_role(action_parameters=parse_action(body)))


@app.action("incident.claim_role")
def handle_incident_claim_role(ack, body):
    logger.debug(body)
    ack()
    asyncio.run(inc_actions.claim_role(action_parameters=parse_action(body)))


@app.action("incident.set_status")
def handle_incident_set_status(ack, body):
    logger.debug(body)
    ack()
    asyncio.run(inc_actions.set_status(action_parameters=parse_action(body)))


@app.action("incident.set_severity")
def handle_incident_set_severity(ack, body):
    logger.debug(body)
    ack()
    asyncio.run(inc_actions.set_severity(action_parameters=parse_action(body)))


"""
Reactions
"""


@app.event("reaction_added")
def reaction_added(event, say):
    reacji = event.get("reaction")
    channel_id = event.get("item").get("channel")
    ts = event.get("item").get("ts")

    # Automatically create incident based on reaction with specific reacji if enabled
    if config.active.options.get("create_from_reaction"):
        if reacji == config.active.options.get("create_from_reaction"):
            # Retrieve the content of the message that was reacted to
            try:
                result = slack_web_client.conversations_history(
                    channel=channel_id, inclusive=True, oldest=ts, limit=1
                )
                message = result["messages"][0]
                message_reacted_to_content = message["text"]
            except Exception as error:
                logger.error(
                    f"Error when trying to retrieve a message: {error}"
                )

            # Create request parameters object
            try:
                request_parameters = incident.RequestParameters(
                    channel=channel_id,
                    incident_description=f"auto-{tools.random_suffix}",
                    user=event.get("user"),
                    severity="sev4",
                    message_reacted_to_content=message_reacted_to_content,
                    original_message_timestamp=ts,
                    is_security_incident=False,
                    private_channel=False,
                )
            except ConfigurationError as error:
                logger.error(error)

            # Create an incident based on the message using the internal path
            try:
                incident.create_incident(
                    internal=True, request_parameters=request_parameters
                )
            except Exception as error:
                logger.error(
                    f"Error when trying to create an incident: {error}"
                )
    # Pinned content for incidents
    if reacji == "pushpin":
        channel_info = slack_web_client.conversations_info(channel=channel_id)

        prefix = config.default_incident_channel_name_prefix
        if config.active.options.get("channel_naming"):
            if config.active.options.get("channel_naming").get(
                "channel_name_prefix"
            ):
                prefix = config.active.options.get("channel_naming").get(
                    "channel_name_prefix"
                )

        if f"{prefix}-" in channel_info["channel"]["name"]:
            # Retrieve the content of the message that was reacted to
            try:
                result = slack_web_client.conversations_history(
                    channel=channel_id, inclusive=True, oldest=ts, limit=1
                )
                message = result["messages"][0]
                if "files" in message:
                    for file in message["files"]:
                        if "image" in file["mimetype"]:
                            if not file["public_url_shared"]:
                                # Make the attachment public temporarily
                                try:
                                    slack_web_client.files_sharedPublicURL(
                                        file=file["id"],
                                        token=config.slack_user_token,
                                    )
                                except SlackApiError as error:
                                    logger.error(
                                        f"Error preparing pinned file for copy: {error}"
                                    )
                            # Copy the attachment into the database
                            pub_secret = file["permalink_public"].split("-")[3]
                            res = requests.get(
                                file["url_private"],
                                headers={
                                    "Authorization": f"Bearer {config.slack_bot_token}"
                                },
                                params={"pub_secret": pub_secret},
                            )
                            write_content(
                                incident_id=channel_info["channel"]["name"],
                                title=file["name"],
                                img=res.content,
                                mimetype=file["mimetype"],
                                ts=tools.fetch_timestamp(short=True),
                                user=get_slack_user(user_id=message["user"]["real_name"]),
                            )
                            # Revoke public access
                            try:
                                slack_web_client.files_revokePublicURL(
                                    file=file["id"],
                                    token=config.slack_user_token,
                                )
                            except SlackApiError as error:
                                logger.error(
                                    f"Error preparing pinned file for copy during public url revoke: {error}"
                                )
                        else:
                            say(
                                channel=channel_id,
                                text=f":wave: Hey there! It looks like that's not an image. I can currently only attach images.",
                            )
                try:
                    slack_web_client.reactions_add(
                        channel=channel_id,
                        name="white_check_mark",
                        timestamp=ts,
                    )
                except Exception as error:
                    if "already_reacted" in str(error):
                        reason = (
                            "It looks like I've already pinned that content."
                        )
                    else:
                        reason = f"Something went wrong: {error}"
                    say(
                        channel=channel_id,
                        text=f":wave: Hey there! I was unable to pin that message. {reason}",
                    )
                else:
                    write_content(
                        incident_id=channel_info["channel"]["name"],
                        content=message["text"],
                        ts=tools.fetch_timestamp(short=True),
                        user=get_slack_user(user_id=message["user"]["real_name"]),
                    )
            except Exception as error:
                logger.error(
                    f"Error when trying to retrieve a message: {error}"
                )


"""
Statuspage
"""


@app.action("statuspage.components_select")
def handle_static_action(ack, body):
    logger.debug(body)
    ack()


@app.action("statuspage.components_status_select")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("statuspage.impact_select")
def handle_static_action(ack, body):
    logger.debug(body)
    ack()


@app.action("statuspage.open_statuspage")
def handle_static_action(ack, body):
    logger.debug(body)
    ack()


@app.action("statuspage.update_status")
def handle_static_action(ack, body):
    logger.debug(body)
    ack()


@app.action("statuspage.view_incident")
def handle_static_action(ack, body):
    logger.debug(body)
    ack()


"""
Jira
"""


@app.action("jira.description_input")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("jira.priority_select")
def handle_static_action(ack, body):
    logger.debug(body)
    ack()


@app.action("jira.summary_input")
def handle_static_action(ack, body):
    logger.debug(body)
    ack()


@app.action("jira.type_select")
def handle_static_action(ack, body):
    logger.debug(body)
    ack()


@app.action("jira.view_issue")
def handle_static_action(ack, body):
    logger.debug(body)
    ack()


"""
Logs for request handling various other requests
"""


@app.action("dismiss_message")
def handle_dismiss_message(ack, body):
    logger.debug(body)
    try:
        ack()
        slack_web_client.chat_delete(
            channel=body["channel"]["id"], ts=body["actions"][0]["value"]
        )
    except slack_sdk.errors.SlackApiError as error:
        logger.error(f"Error deleting message: {error}")


@app.action("incident.clicked_conference_link")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()


if config.active.links:
    for l in config.active.links:

        @app.action(
            f"incident.clicked_link_{l.get('title').lower().replace(' ', '_')}"
        )
        def handle_static_action(ack, body, logger):
            logger.debug(body)
            ack()


@app.action("incident.join_incident_channel")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("external.reload")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("external.view_status_page")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("incident_update_modal_select_incident")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("open_postmortem")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("open_incident_modal_set_severity")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("open_incident_modal_set_security_type")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()

    if body.get("actions")[0].get("selected_option").get("value") in (
        "True",
        "true",
        True,
    ):
        try:
            placeholder_severity = [
                sev for sev, _ in config.active.severities.items()
            ][-1]

            base_blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "This will start a new incident channel and you will "
                        + "be invited to it. From there, please use our incident "
                        + "management process to run the incident or coordinate "
                        + "with others to do so.",
                    },
                },
                {
                    "type": "section",
                    "block_id": "is_security_incident",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Is this a security incident?*",
                    },
                    "accessory": {
                        "action_id": "open_incident_modal_set_security_type",
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Yes",
                        },
                        "initial_option": {
                            "text": {
                                "type": "plain_text",
                                "text": "Yes",
                            },
                            "value": "true",
                        },
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "Yes",
                                },
                                "value": "true",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "No",
                                },
                                "value": "false",
                            },
                        ],
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":lock: *Security incident channels will be created as private channels.*",
                    },
                },
                {
                    "type": "input",
                    "block_id": "open_incident_modal_desc",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "open_incident_modal_set_description",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "A brief description of the problem.",
                        },
                    },
                    "label": {"type": "plain_text", "text": "Description"},
                },
                {
                    "block_id": "severity",
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Severity*"},
                    "accessory": {
                        "type": "static_select",
                        "action_id": "open_incident_modal_set_severity",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a severity...",
                            "emoji": True,
                        },
                        "initial_option": {
                            "text": {
                                "type": "plain_text",
                                "text": placeholder_severity.upper(),
                            },
                            "value": placeholder_severity,
                        },
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": sev.upper(),
                                    "emoji": True,
                                },
                                "value": sev,
                            }
                            for sev, _ in config.active.severities.items()
                        ],
                    },
                },
            ]

            """
            If there are teams that will be auto paged, mention that
            """
            if "pagerduty" in config.active.integrations:
                auto_page_targets = read_pager_auto_page_targets()
                if len(auto_page_targets) != 0:
                    base_blocks.extend(
                        [
                            {"type": "divider"},
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": ":point_right: *The following teams will "
                                    + "be automatically paged when this incident is created:*",
                                },
                            },
                        ]
                    )
                    for i in auto_page_targets:
                        for k, v in i.items():
                            base_blocks.extend(
                                [
                                    {
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": f"_{k}_",
                                        },
                                    },
                                ]
                            )

            slack_web_client.views_update(
                # Pass the view_id
                view_id=body["view"]["id"],
                # String that represents view state to protect against race conditions
                hash=body["view"]["hash"],
                # View payload with updated blocks
                view={
                    "type": "modal",
                    "callback_id": "open_incident_modal",
                    "title": {
                        "type": "plain_text",
                        "text": "Start a new incident",
                    },
                    "submit": {"type": "plain_text", "text": "Start"},
                    "blocks": base_blocks,
                },
            )
        except slack_sdk.errors.SlackApiError as error:
            logger.error(f"Error deleting message: {error}")


@app.action("open_incident_modal_set_private")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("view_statuspage_incident")
def handle_static_action(ack, body, logger):
    logger.debug(body)
    ack()
