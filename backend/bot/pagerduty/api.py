import config
import logging

from bot.db import db
from bot.shared import tools
from bot.slack.client import slack_web_client
from collections import defaultdict
from pdpyras import APISession, PDClientError
from typing import Dict

logger = logging.getLogger(__name__)

session = APISession(
    config.pagerduty_api_token, default_from=config.pagerduty_api_username
)

"""
PagerDuty
"""


def find_who_is_on_call() -> Dict:
    """
    Given a PagerDuty instance, loop through oncall schedules and return info
    on each one identifying who to contact when run

    This is stored in the database and will only refresh when this function is
    called to avoid API abuse
    """
    on_call = defaultdict(list)
    slack_users = {
        user["real_name"]: user["id"]
        for user in slack_web_client.users_list()["members"]
        if user.__contains__("real_name")
    }
    for oc in session.iter_all("oncalls"):
        if oc["start"] != None and oc["end"] != None:
            on_call[oc["escalation_policy"]["summary"]].append(
                {
                    "escalation_level": oc["escalation_level"],
                    "escalation_policy": oc["escalation_policy"]["summary"],
                    "escalation_policy_id": oc["escalation_policy"]["id"],
                    "schedule_summary": oc["schedule"]["summary"],
                    "user": oc["user"]["summary"],
                    "start": oc["start"],
                    "end": oc["end"],
                    "slack_user_id": [
                        val
                        for key, val in slack_users.items()
                        if oc["user"]["summary"] in key
                    ],
                }
            )
    # Sort values by name, sort dict by escalation_level
    result = {}
    for i, j in sorted(dict(on_call).items()):
        result[i] = sorted(j, key=lambda d: d["escalation_level"])
    return result


def store_on_call_data():
    """
    Parses information from PagerDuty regarding on-call information and stores it
    in the database
    """
    record_name = "pagerduty_oc_data"
    try:
        # Create the row if it doesn't exist
        if not db.Session.query(db.OperationalData).filter_by(id=record_name).all():
            try:
                row = db.OperationalData(id=record_name)
                db.Session.add(row)
                db.Session.commit()
            except Exception as error:
                logger.error(f"Opdata row create failed for {record_name}: {error}")
        db.Session.execute(
            db.update(db.OperationalData)
            .where(db.OperationalData.id == record_name)
            .values(
                json_data=find_who_is_on_call(),
                updated_at=tools.fetch_timestamp(),
            )
        )
        db.Session.commit()
    except Exception as error:
        logger.error(f"Opdata row edit failed for {record_name}: {error}")
        db.Session.rollback()
    finally:
        db.Session.close()


def find_escalation_policy_id(ep_name: str) -> str:
    """
    Determine which service is associated with an escalation policy
    """
    eps = session.iter_all("escalation_policies")
    # .find wasn't working for this, no idea why.
    for ep in eps:
        if ep["name"] == ep_name:
            return ep["id"]


def find_service_for_escalation_policy(ep_name: str) -> str:
    """
    Determine which service is associated with an escalation policy
    """
    eps = session.iter_all("escalation_policies")
    # .find wasn't working for this, no idea why.
    for ep in eps:
        if ep["name"] == ep_name:
            return ep["services"][0]["id"]


def page_on_call(
    ep_name: str,
    priority: str,
    channel_name: str,
    channel_id: str,
    paging_user: str,
):
    """
    Page via an escalation policy when triggred from Slack.

    This can be added back to the call when the following error is resolved.
    {
        "error": {
            "message": "Required abilities are unavailable",
            "code": 2014,
            "errors": [
                "The coordinated_responding account ability is required to access conference bridge details."
            ],
            "missing_abilities": "coordinated_responding",
        }
    }
    """
    service_id = find_service_for_escalation_policy(ep_name=ep_name)
    ep_id = find_escalation_policy_id(ep_name=ep_name)
    pd_inc = {
        "incident": {
            "type": "incident",
            "title": f"Slack incident {channel_name} has been started and a page has been issued for assistance.",
            "service": {"id": service_id, "type": "service_reference"},
            "urgency": priority,
            "incident_key": channel_name,
            "body": {
                "type": "incident_body",
                "details": f"An incident has been declared in Slack and this team has been paged as a result. You were paged by {paging_user}. Link: https://{config.slack_workspace_id}.slack.com/archives/{channel_id}",
            },
            "escalation_policy": {"id": ep_id, "type": "escalation_policy_reference"},
        }
    }
    try:
        response = session.post("/incidents", json=pd_inc)
        logger.info(response)
        if not response.ok:
            logger.error(
                "Error creating PagerDuty incident: {}".format(response.json())
            )
    except PDClientError as error:
        logger.error(f"Error creating PagerDuty incident: {error}")
