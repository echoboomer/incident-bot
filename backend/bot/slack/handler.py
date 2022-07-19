import config
import logging
import pyjokes

from slack_bolt import App
from typing import Any, Dict
from .messages import (
    incident_list_message,
    job_list_message,
    pd_on_call_message,
    sp_incident_list_message,
)
from .client import slack_web_client
from .messages import help_menu
from bot.db import db
from bot.incident import actions as inc_actions, action_parameters, incident
from bot.scheduler import scheduler
from bot.shared import tools
from bot.statuspage import actions as sp_actions, handler as sp_handler


logger = logging.getLogger(__name__)

## The xoxb oauth token for the bot is called here to provide bot privileges.
app = App(token=config.slack_bot_token)


@app.error
def custom_error_handler(error, body, logger):
    logger.exception(f"Error: {error}")
    logger.debug(f"Request body: {body}")


from . import modals


"""
Handle Mentions
"""


@app.event("app_mention")
def handle_mention(body, say, logger):
    message = body["event"]["text"].split(" ")
    channel = body["event"]["channel"]
    user = body["event"]["user"]
    logger.debug(body)

    if "help" in message:
        say(blocks=help_menu(), text="")
    elif "new" in message:
        request_parameters = {
            "channel": channel,
            "channel_description": " ".join(message[2:]),
            "user": user,
            "created_from_web": False,
        }
        resp = incident.create_incident(request_parameters)
        say(f"<@{user}> {resp}")
    elif "diag" in message:
        startup_message = config.startup_message(wrap=True)
        say(channel=user, text=startup_message)
    elif "lsoi" in message:
        database_data = db.db_read_all_incidents()
        resp = incident_list_message(database_data, all=False)
        say(blocks=resp, text="")
    elif "lsai" in message:
        database_data = db.db_read_all_incidents()
        resp = incident_list_message(database_data, all=True)
        say(blocks=resp, text="")
    elif "ls-sp-inc" in " ".join(message):
        if config.statuspage_integration_enabled == "true":
            sp_objects = sp_handler.StatuspageObjects()
            sp_incidents = sp_objects.open_incidents
            resp = sp_incident_list_message(sp_incidents)
            say(blocks=resp, text="")
        else:
            say(
                text=f"The Statuspage integration is not enabled. I cannot provide information from Statuspage as a result.",
            )
    elif "pager" in message:
        if config.pagerduty_features_enabled == "true":
            from bot.pagerduty import api as pd_api

            pd_oncall_data = pd_api.find_who_is_on_call()
            resp = pd_on_call_message(data=pd_oncall_data)
            say(blocks=resp, text="")
        else:
            say(
                text=f"The PAgerDuty integration is not enabled. I cannot provide information from PagerDuty as a result.",
            )
    elif "scheduler" in message:
        if message[2] == "list":
            jobs = scheduler.process.list_jobs()
            resp = job_list_message(jobs)
            say(blocks=resp, text="")
        elif message[2] == "delete":
            if len(message) < 4:
                say(text="Please provide the ID of a job to delete.")
            else:
                job_title = message[3]
                delete_job = scheduler.process.delete_job(job_title)
                if delete_job != None:
                    say(f"Could not delete the job {job_title}: {delete_job}")
                else:
                    say(f"Deleted job: *{job_title}*")
    elif "tell me a joke" in " ".join(message):
        say(text=pyjokes.get_joke())
    elif "ping" in message:
        say(text="pong")
    elif "version" in message:
        say(text=f"I am currently running version: {config.__version__}")
    elif len(message) == 1:
        # This is just a user mention and the bot shouldn't really do anything.
        pass
    else:
        resp = " ".join(message[1:])
        say(text=f"Sorry, I don't know the command *{resp}* yet.")


"""
Incident Management Actions
"""


def parse_action(body) -> Dict[str, Any]:
    return action_parameters.ActionParameters(
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
    inc_actions.export_chat_logs(action_parameters=parse_action(body))


@app.action("incident.add_on_call_to_channel")
def handle_incident_add_on_call(ack, body, say):
    logger.debug(body)
    ack()
    user = body["user"]["id"]
    say(
        channel=user,
        text="Hi! If you want to page someone, use my shortcut 'Incident Bot Pager' instead!",
    )


@app.action("incident.assign_role")
def handle_incident_assign_role(ack, body):
    logger.debug(body)
    ack()
    inc_actions.assign_role(action_parameters=parse_action(body))


@app.action("incident.claim_role")
def handle_incident_claim_role(ack, body):
    logger.debug(body)
    ack()
    inc_actions.claim_role(action_parameters=parse_action(body))


@app.action("incident.reload_status_message")
def handle_incident_reload_status_message(ack, body):
    logger.debug(body)
    ack()
    inc_actions.reload_status_message(action_parameters=parse_action(body))


@app.action("incident.set_incident_status")
def handle_incident_set_incident_statuse(ack, body):
    logger.debug(body)
    ack()
    inc_actions.set_incident_status(action_parameters=parse_action(body))


@app.action("incident.set_severity")
def handle_incident_set_severity(ack, body):
    logger.debug(body)
    ack()
    inc_actions.set_severity(action_parameters=parse_action(body))


"""
Statuspage Actions
"""


@app.action("statuspage.components_select")
def handle_incident_components_select(ack, body):
    logger.debug(body)
    ack()
    sp_actions.components_select(action_parameters=parse_action(body))


@app.action("statuspage.components_status_select")
def handle_some_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("statuspage.impact_select")
def handle_incident_components_select(ack, body):
    logger.debug(body)
    ack()


@app.action("statuspage.update_status")
def handle_incident_update_status(ack, body):
    logger.debug(body)
    ack()
    sp_actions.update_status(action_parameters=parse_action(body))


"""
Reactions
"""


@app.event("reaction_added")
def reaction_added(event):
    # Automatically create incident based on reaction with specific emoji
    if config.incident_auto_create_from_react_enabled == "true":
        emoji = event["reaction"]
        channel = event["item"]["channel"]
        ts = event["item"]["ts"]
        # Only act if the emoji is the one we care about
        if emoji == config.incident_auto_create_from_react_emoji_name:
            # Retrieve the content of the message that was reacted to
            try:
                result = slack_web_client.conversations_history(
                    channel=channel, inclusive=True, oldest=ts, limit=1
                )
                message = result["messages"][0]
                message_reacted_to_content = message["text"]
            except Exception as error:
                logger.error(f"Error when trying to retrieve a message: {error}")
            request_parameters = {
                "channel": channel,
                "channel_description": f"auto-{tools.random_suffix}",
                "descriptor": f"auto-{tools.random_suffix}",
                "user": "internal_auto_create",
                "message_reacted_to_content": message_reacted_to_content,
                "original_message_timestamp": ts,
            }
            # Create an incident based on the message using the internal path
            try:
                incident.create_incident(
                    internal=True, request_parameters=request_parameters
                )
            except Exception as error:
                logger.error(f"Error when trying to create an incident: {error}")


"""
Logs for request handling various other requests
"""


@app.event("message")
def handle_message_events(body, logger):
    logger.debug(body)


@app.action("incident.incident_postmortem_link")
def handle_some_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("incident.incident_guide_link")
def handle_some_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("incident.join_incident_channel")
def handle_some_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("external.reload")
def handle_some_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("external.view_status_page")
def handle_some_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("incident_update_modal_select_incident")
def handle_some_action(ack, body, logger):
    logger.debug(body)
    ack()


@app.action("open_rca")
def handle_some_action(ack, body, logger):
    logger.debug(body)
    ack()
