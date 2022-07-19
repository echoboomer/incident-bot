import config

from typing import Dict, List

sp_logo_url = "https://i.imgur.com/v4xmF6u.png"


def return_new_incident_message(
    channel_id: str, components: List[str]
) -> Dict[str, str]:
    """Posts a message in the incident channel prompting for the creation of a Statuspage incident

    Args:
        channel_id: the channel to post the message to
        info: Dict[str, str] as returned by the StatuspageIncident class info method
    """
    formatted_components = []
    for c in components:
        formatted_components.append(
            {
                "text": {
                    "type": "plain_text",
                    "text": c,
                },
                "value": c,
            }
        )
    return {
        "channel": channel_id,
        "blocks": [
            {"type": "divider"},
            {
                "type": "image",
                "image_url": sp_logo_url,
                "alt_text": "statuspage",
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This incident has just been created. Please use the fields below to start a corresponding incident on Statuspage.\n\nThe Statuspage incident will start in *investigating* mode just like our internal incidents. Each time our internal incident is updated, the Statuspage incident will also be updated.",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Please enter a brief description that will appear as the incident description in the Statuspage incident. Then select impacted components and confirm. Once confirmed, the incident will be opened.",
                },
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "statuspage_name_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "statuspage.name_input",
                    "min_length": 1,
                },
                "label": {
                    "type": "plain_text",
                    "text": "Name for the incident",
                    "emoji": True,
                },
            },
            {
                "type": "input",
                "block_id": "statuspage_body_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "statuspage.body_input",
                    "min_length": 1,
                },
                "label": {
                    "type": "plain_text",
                    "text": "Message describing the incident",
                    "emoji": True,
                },
            },
            {
                "block_id": "statuspage_impact_select",
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Impact:*"},
                "accessory": {
                    "type": "static_select",
                    "action_id": "statuspage.impact_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select an impact...",
                        "emoji": True,
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Minor",
                                "emoji": True,
                            },
                            "value": "minor",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Major",
                                "emoji": True,
                            },
                            "value": "major",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Critical",
                                "emoji": True,
                            },
                            "value": "critical",
                        },
                    ],
                },
            },
            {
                "block_id": "statuspage_components_status",
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Components Impact:*"},
                "accessory": {
                    "type": "static_select",
                    "action_id": "statuspage.components_status_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select status of components...",
                        "emoji": True,
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Degraded Performance",
                                "emoji": True,
                            },
                            "value": "degraded_performance",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Partial Outage",
                                "emoji": True,
                            },
                            "value": "partial_outage",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Major Outage",
                                "emoji": True,
                            },
                            "value": "major_outage",
                        },
                    ],
                },
            },
            {
                "type": "section",
                "block_id": "statuspage_components_select",
                "text": {"type": "mrkdwn", "text": "Select impacted components"},
                "accessory": {
                    "action_id": "statuspage.components_select",
                    "type": "multi_static_select",
                    "placeholder": {"type": "plain_text", "text": "Select components"},
                    "options": formatted_components,
                },
            },
            {
                "type": "actions",
                "block_id": "statuspage_starter_button",
                "elements": [
                    {
                        "type": "button",
                        "style": "primary",
                        "text": {"type": "plain_text", "text": "Open Statuspage"},
                        "url": config.statuspage_url,
                    },
                ],
            },
        ],
    }


def new_statuspage_incident_created_message(
    channel_id: str, info: Dict[str, str]
) -> Dict[str, str]:
    """When a Statuspage incident is created, this is the followup message posted to the channel

    Args:
        channel_id: the channel to post the message to
        info: Dict[str, str] as returned by the StatuspageIncident class info method
    """
    # Format info section
    sp_incident_title = info["name"]
    sp_incident_status = info["status"]
    sp_url = info["shortlink"]

    # updates = []
    # if info["incident_updates"] != {}:
    #    for u in info["incident_updates"]:
    #        body = u["body"]
    #        status = u["status"]
    #        updated_at = u["updated_at"]
    #        updates.append(
    #            {
    #                "type": "plain_text",
    #                "elements": [
    #                    {
    #                        "type": "mrkdwn",
    #                        "text": f"*Body*: {body}\n*Status*: {status}\n*Time of Update*: {updated_at}\n",
    #                    }
    #                ],
    #            },
    #        )
    return {
        "channel": channel_id,
        "blocks": [
            {"type": "divider"},
            {
                "type": "image",
                "image_url": sp_logo_url,
                "alt_text": "statuspage",
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Statuspage incident has been created.",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Title*: {sp_incident_title}\n*Status*: {sp_incident_status.title()}\n",
                },
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "statuspage_update_message_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "statuspage.update_message_input",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Message to include with this update",
                    "emoji": True,
                },
            },
            {
                "block_id": "statuspage_incident_status_management",
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Update Status:*"},
                "accessory": {
                    "type": "static_select",
                    "action_id": "statuspage.update_status",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Investigating",
                        "emoji": True,
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Identified",
                                "emoji": True,
                            },
                            "value": "identified",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Monitoring",
                                "emoji": True,
                            },
                            "value": "monitoring",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Resolved",
                                "emoji": True,
                            },
                            "value": "resolved",
                        },
                    ],
                },
            },
            {"type": "divider"},
            {
                "type": "actions",
                "block_id": "statuspage_starter_button",
                "elements": [
                    {
                        "type": "button",
                        "style": "primary",
                        "text": {"type": "plain_text", "text": "View Incident"},
                        "url": sp_url,
                    },
                ],
            },
        ],
    }


def statuspage_incident_update_message(
    channel_id: str, info: Dict[str, str]
) -> Dict[str, str]:
    """Posts a message to the incident channel whenever a Statuspage incident is updated

    Args:
        channel_id: the channel to post the message to
        info: Dict[str, str] as returned by the StatuspageIncident class info method
    """
    # Format info section
    sp_incident_title = info["name"]
    sp_incident_status = info["status"]
    sp_url = info["shortlink"]
    return {
        "channel": channel_id,
        "blocks": [
            {"type": "divider"},
            {
                "type": "image",
                "image_url": sp_logo_url,
                "alt_text": "statuspage",
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Statuspage incident has been updated.",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Title*: {sp_incident_title}\n*Status*: {sp_incident_status.title()}\n",
                },
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "statuspage_update_message_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "statuspage.update_message_input",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Message to include with this update",
                    "emoji": True,
                },
            },
            {
                "block_id": "statuspage_incident_status_management",
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Update Status:*"},
                "accessory": {
                    "type": "static_select",
                    "action_id": "statuspage.update_status",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Investigating",
                        "emoji": True,
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Identified",
                                "emoji": True,
                            },
                            "value": "identified",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Monitoring",
                                "emoji": True,
                            },
                            "value": "monitoring",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Resolved",
                                "emoji": True,
                            },
                            "value": "resolved",
                        },
                    ],
                },
            },
            {"type": "divider"},
            {
                "type": "actions",
                "block_id": "statuspage_starter_button",
                "elements": [
                    {
                        "type": "button",
                        "style": "primary",
                        "text": {"type": "plain_text", "text": "View Incident"},
                        "url": sp_url,
                    },
                ],
            },
        ],
    }


def statuspage_incident_update_message_resolved(
    channel_id: str, info: Dict[str, str]
) -> Dict[str, str]:
    """Resolution specific message

    Args:
        channel_id: the channel to post the message to
        info: Dict[str, str] as returned by the StatuspageIncident class info method
    """
    # Format info section
    sp_incident_title = info["name"]
    sp_incident_status = info["status"]
    sp_url = info["shortlink"]
    return {
        "channel": channel_id,
        "blocks": [
            {"type": "divider"},
            {
                "type": "image",
                "image_url": sp_logo_url,
                "alt_text": "statuspage",
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Statuspage incident has been resolved.",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Title*: {sp_incident_title}\n*Status*: {sp_incident_status.title()}\n",
                },
            },
            {"type": "divider"},
            {
                "type": "actions",
                "block_id": "statuspage_starter_button",
                "elements": [
                    {
                        "type": "button",
                        "style": "primary",
                        "text": {"type": "plain_text", "text": "View Incident"},
                        "url": sp_url,
                    },
                ],
            },
        ],
    }
