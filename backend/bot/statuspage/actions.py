import config
import logging
import slack_sdk.errors

from . import slack as spslack, handler
from bot.db import db
from bot.slack import client
from bot.incident import action_parameters

logger = logging.getLogger(__name__)
log_level = config.log_level


def components_select(action_parameters: type[action_parameters.ActionParameters]):
    """When an incoming action is statuspage.components_select, this method
    creates a Statuspage incident and sends an updated message to the channel
    """
    state = action_parameters.state()
    p = action_parameters.parameters()

    channel_id = p["channel_id"]
    channel_name = p["channel_name"]

    # Create a list for the components that were selected in the prompt
    selected_components = []
    # Find the index in the original components map
    for a in action_parameters.actions()["selected_options"]:
        selected_components.append(a["text"]["text"])
    body = state["values"]["statuspage_body_input"]["statuspage.body_input"]["value"]
    impact = state["values"]["statuspage_impact_select"]["statuspage.impact_select"][
        "selected_option"
    ]["value"]
    name = state["values"]["statuspage_name_input"]["statuspage.name_input"]["value"]
    status = state["values"]["statuspage_components_status"][
        "statuspage.components_status_select"
    ]["selected_option"]["value"]
    # Return formatted JSON for components section
    sp_components = handler.StatuspageComponents()
    sp_formatted = sp_components.formatted_components_update(
        selected_components, status
    )
    # Start Statuspage incident
    sp_inc = handler.StatuspageIncident(
        request_data={
            "name": name,
            "status": "investigating",
            "body": body,
            "impact": impact,
            "components": sp_formatted,
        }
    )
    message = spslack.new_statuspage_incident_created_message(channel_id, sp_inc.info)
    try:
        og_result = client.slack_web_client.chat_postMessage(**message, text="")
        logger.debug(f"\n{og_result}\n")
        # Timestamp of original message is needed to delete it later
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error sending Statuspage starter to incident channel {channel_name}: {error}"
        )
    # Delete the original message after the incident is created
    incident_data = db.db_read_incident(incident_id=p["channel_name"])
    sp_initial_message_timestamp = incident_data.sp_message_ts
    try:
        result = client.slack_web_client.chat_delete(
            channel=channel_id,
            ts=sp_initial_message_timestamp,
        )
        logger.debug(f"\n{result}\n")
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error deleting Statuspage starter message from {channel_name}: {error}"
        )
    # Since we don't care about the original message anymore, but we do want
    # to mutate future messages, write to the database with the new message
    # timestamp
    logger.info(
        f"Updating incident record in database to overrwrite sp_ts column for channel {channel_name}..."
    )
    try:
        db.db_update_incident_sp_ts_col(
            incident_id=channel_name,
            ts=og_result["ts"],
        )
    except Exception as error:
        logger.fatal(
            f"Error updating incident record in database to overrwrite sp_ts column for channel {channel_name}: {error}"
        )
    # Write the Statuspage incident ID to the database
    logger.info(
        f"Updating incident record in database to add Statuspage incident id for channel {channel_name}..."
    )
    try:
        db.db_update_incident_sp_id_col(
            incident_id=channel_name,
            sp_incident_id=sp_inc.info["id"],
        )
    except Exception as error:
        logger.fatal(
            f"Error updating incident record in database to add Statuspage incident id for channel {channel_name}: {error}"
        )


def update_status(action_parameters: type[action_parameters.ActionParameters]):
    """When an incoming action is statuspage.update_status, this method
    updates the Statuspage incident and sends a new message to the incident
    channel
    """
    # Base parameters
    state = action_parameters.state()
    p = action_parameters.parameters()
    channel_id = p["channel_id"]
    channel_name = p["channel_name"]
    incident_data = db.db_read_incident(incident_id=p["channel_name"])
    sp_updated_message_timestamp = incident_data.sp_message_ts
    sp_incident_id = incident_data.sp_incident_id

    #
    incoming_status_change = action_parameters.actions()["selected_option"]["value"]

    # Send the update, delete the message, repost the message after each update
    new_body = state["values"]["statuspage_update_message_input"][
        "statuspage.update_message_input"
    ]["value"]

    # If this is the resolution message, set the components back to healthy
    if incoming_status_change == "resolved":
        sp_components = handler.StatuspageComponents()
        sp_components_list = sp_components.list_of_names()
        sp_formatted = sp_components.formatted_components_update(
            sp_components_list, "operational"
        )
        updated_message = handler.update_sp_incident(
            {
                "id": sp_incident_id,
                "body": new_body,
                "status": incoming_status_change,
                "components": sp_formatted,
            }
        )
        slack_message = spslack.statuspage_incident_update_message_resolved(
            channel_id, updated_message
        )
    else:
        updated_message = handler.update_sp_incident(
            {
                "id": sp_incident_id,
                "body": new_body,
                "status": incoming_status_change,
                "components": {},
            }
        )
        slack_message = spslack.statuspage_incident_update_message(
            channel_id, updated_message
        )
    # Delete existing message and repost
    try:
        result = client.slack_web_client.chat_delete(
            channel=channel_id,
            ts=sp_updated_message_timestamp,
        )
        logger.debug(f"\n{result}\n")
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error deleting Statuspage updated message from channel {channel_name}: {error}"
        )
    # Post new message
    try:
        result = client.slack_web_client.chat_postMessage(**slack_message, text="")
        logger.debug(f"\n{result}\n")
        # Timestamp of original message is needed to delete it later
    except slack_sdk.errors.SlackApiError as error:
        logger.error(
            f"Error sending Statuspage starter to incident channel {channel_name}: {error}"
        )
    # Update timestamp in database entry to the newest one
    logger.info(
        f"Updating incident record in database to overrwrite sp_ts column for channel {channel_name}..."
    )
    try:
        db.db_update_incident_sp_ts_col(
            incident_id=channel_name,
            ts=result["ts"],
        )
    except Exception as error:
        logger.fatal(
            f"Error updating incident record in database to overrwrite sp_ts column for channel {channel_name}: {error}"
        )
