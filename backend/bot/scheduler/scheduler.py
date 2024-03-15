import zoneinfo
import config
import datetime
import slack_sdk

from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from bot.models.incident import db_read_incident, db_read_open_incidents
from bot.shared import tools
from bot.slack.client import (
    get_digest_channel_id,
    slack_web_client,
    store_slack_channel_list_db,
    store_slack_user_list_db,
)
from iblog import logger
from typing import List


application_timezone = config.active.options.get("timezone")
jobstores = {"default": SQLAlchemyJobStore(url=config.database_url)}


class TaskScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone=zoneinfo.ZoneInfo(application_timezone),
        )

    def list_jobs(self) -> List[Job]:
        return self.scheduler.get_jobs()

    def remove_jobs(self):
        jobs = self.list_jobs()
        num_jobs = len(jobs)
        logger.info(f"Removing {num_jobs} jobs from the scheduler.")
        self.scheduler.remove_all_jobs()

    def delete_job(self, job_to_delete: str):
        try:
            self.scheduler.remove_job(job_id=job_to_delete)
            return None
        except Exception as error:
            logger.error(f"Unable to delete job {job_to_delete}: {error}")
            return error

    def start(self):
        logger.info("Starting task scheduler...")
        try:
            self.scheduler.start()
        except Exception as error:
            logger.error(f"Error starting task scheduler: {error}")


process = TaskScheduler()


def add_incident_scheduled_reminder(
    channel_name: str, channel_id: str, severity: str, rate: int
):
    """
    Adds a ~25 minute scheduled reminder for sev1/sev2 incidents that will
    determine when the last update was sent out and remind the channel if it was
    not within the last half hour
    """
    logger.info(f"Creating scheduled reminder job for {channel_name}.")
    process.scheduler.add_job(
        id=f"{channel_name}_updates_reminder",
        func=scheduled_reminder_message,
        args=[channel_name, channel_id, severity, rate],
        trigger="interval",
        name=f"Check every {rate} minutes whether {channel_name} has had updates sent out",
        minutes=rate,
        replace_existing=True,
    )


def scheduled_reminder_message(
    channel_name: str, channel_id: str, severity: str, rate: int
):
    """
    Formatting for the message sent for scheduled reminders for ongoing incidents
    """
    incident = db_read_incident(incident_id=channel_name)
    last_update_sent = incident.last_update_sent
    # Max time, in minutes, since last update was sent out before reminding the channel
    max_age = 25
    if last_update_sent == None:
        created_at = datetime.datetime.strptime(
            incident.created_at, tools.timestamp_fmt
        )
        now = datetime.datetime.now()
        time_open = now - created_at
        been_30_minutes = datetime.timedelta(minutes=1) < time_open
        if been_30_minutes:
            try:
                result = slack_web_client.chat_postMessage(
                    channel=channel_id,
                    blocks=[
                        {
                            "block_id": "update_help_message",
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"<!channel> :wave: It has been {rate} minutes "
                                + "since this incident was opened and no updates "
                                + "have been sent out regarding this incident. "
                                + f"Since this is a *{severity.upper()}* incident, "
                                + "updates must be provided every half hour. "
                                + "Please use the 'provide incident update' shortcut. "
                                + "If you're unsure how to do that, simply search "
                                + "for 'provide incident update' in the search bar "
                                + "at the top of your Slack window. "
                                + "For additional information about my features, "
                                + "check out my app's home page. "
                                + f"I'll remind this channel every {rate} minutes to "
                                + "either send out an initial update or provide a new one.",
                            },
                        },
                        {"type": "divider"},
                        {
                            "type": "actions",
                            "block_id": "update_help_message_buttons",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Send Out Update",
                                        "emoji": True,
                                    },
                                    "value": "show_update_modal",
                                    "action_id": "open_incident_general_update_modal",
                                    "style": "primary",
                                },
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Dismiss",
                                        "emoji": True,
                                    },
                                    "value": "placeholder",
                                    "action_id": "dismiss_message",
                                },
                            ],
                        },
                    ],
                )
                # Retrieve the sent message
                sent_message = slack_web_client.conversations_history(
                    channel=channel_id,
                    inclusive=True,
                    oldest=result["message"]["ts"],
                    limit=1,
                )
                # Update the sent message with its own timestamp
                existing_blocks = sent_message["messages"][0]["blocks"]
                existing_blocks[2]["elements"][1]["value"] = result["message"][
                    "ts"
                ]
                try:
                    slack_web_client.chat_update(
                        channel=channel_id,
                        ts=result["message"]["ts"],
                        blocks=existing_blocks,
                        text="",
                    )
                except slack_sdk.errors.SlackApiError as error:
                    logger.error(f"Error updating message: {error}")
            except slack_sdk.errors.SlackApiError as error:
                logger.error(
                    f"Error sending scheduled reminder about incident {channel_name}: {error}"
                )
    else:
        last_update_sent_ts = datetime.datetime.strptime(
            last_update_sent, tools.timestamp_fmt
        )
        now = datetime.datetime.now()
        time_since_last_update = now - last_update_sent_ts
        expired = datetime.timedelta(minutes=max_age) < time_since_last_update
        if expired:
            try:
                slack_web_client.chat_postMessage(
                    channel=channel_id,
                    text="<!channel> :wave: It has been approximately "
                    + f"{max_age} minutes since the last update was sent out "
                    + f"regarding this incident. Since this is a *{severity.upper()}*"
                    + " incident, updates must be provided every half hour. "
                    + "Please use the 'provide incident update' shortcut. "
                    + "If you're unsure how to do that, simply search for "
                    + "'provide incident update' in the search bar at the top "
                    + "of your Slack window. For additional information about "
                    + "my features, check out my app's home page. I'll remind "
                    + "again in 30 minutes. Once this incident is resolved, "
                    + "this reminder will disappear.",
                )
            except Exception as error:
                logger.error(
                    f"Error sending scheduled reminder about incident {channel_name}: {error}"
                )


"""
Job Definitions
"""


def scrape_for_aging_incidents():
    """
    Checks for incidents older than x days old and sends a reminder message to the
    incidents channel to check on them
    """
    # Max age, in days, of a channel before it's considered stale
    max_age = 7
    # Base block to build message on
    base_block = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":wave: Hi there! The following incidents have been "
                + f"open for {max_age} days. Lets double check them and make "
                "sure their statuses are up to date. :hourglass_flowing_sand:",
            },
        },
        {"type": "divider"},
    ]
    # Find open incidents and append them to a list to add to the message if they're older
    # than the max age
    open_incidents = db_read_open_incidents()

    # Exclude statuses if provided
    if config.active.jobs is not None:
        if "scrape_for_aging_incidents" in config.active.jobs:
            ignored_statuses = config.active.jobs.get(
                "scrape_for_aging_incidents"
            ).get("ignore_statuses")
            if ignored_statuses is not None or ignored_statuses is not []:
                open_incidents = [
                    i
                    for i in open_incidents
                    if i.status not in ignored_statuses
                ]

    formatted_incidents = []
    for inc in open_incidents:
        created_at = datetime.datetime.strptime(
            inc.created_at, tools.timestamp_fmt
        )
        now = datetime.datetime.now()
        time_open = now - created_at
        old = datetime.timedelta(days=max_age) < time_open
        if old:
            logger.info(
                f"{inc.channel_id} is older than {max_age} days and will be "
                + "added to the weekly reminder"
            )
            formatted_incidents.append(
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Incident Name:* <#{inc.channel_id}>",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Current Severity:* {inc.severity.upper()}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Creation Time:* {inc.created_at}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Current Status:* {inc.status.title()}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Time Open:* {time_open}",
                        },
                    ],
                }
            )
            formatted_incidents.append({"type": "divider"})
    if len(formatted_incidents) > 0:
        for inc in formatted_incidents:
            base_block.append(inc)
        try:
            slack_web_client.chat_postMessage(
                channel=get_digest_channel_id(), blocks=base_block
            )
        except Exception as error:
            logger.error(error)
    else:
        logger.info(
            f"Checked for incidents older than {max_age} days and did not find"
            + " any. No alert will be sent."
        )


if (
    config.active.jobs is not None
    and "scrape_for_aging_incidents" in config.active.jobs
    and config.active.jobs.get("scrape_for_aging_incidents").get("enabled")
) or (config.active.jobs is None):
    process.scheduler.add_job(
        id="scrape_for_aging_incidents",
        func=scrape_for_aging_incidents,
        trigger="interval",
        name="Look for stale incidents and inform the digest channel",
        days=2,
        replace_existing=True,
    )


def update_slack_channel_list():
    """
    Uses Slack API to fetch the list of current channels
    """
    try:
        store_slack_channel_list_db()
    except Exception as error:
        logger.error(
            f"Error updating Slack channel list information in scheduled job: {error}"
        )


process.scheduler.add_job(
    id="update_slack_channel_list",
    func=update_slack_channel_list,
    trigger="interval",
    name="Update local copy of Slack channels",
    minutes=15,
    replace_existing=True,
)


def update_slack_user_list():
    """
    Uses Slack API to fetch the list of current users
    """
    try:
        store_slack_user_list_db()
    except Exception as error:
        logger.error(
            f"Error updating Slack user list information in scheduled job: {error}"
        )


process.scheduler.add_job(
    id="update_slack_user_list",
    func=update_slack_user_list,
    trigger="interval",
    name="Update local copy of Slack users",
    minutes=15,
    replace_existing=True,
)

if config.active.integrations.get(
    "atlassian"
) and config.active.integrations.get("atlassian").get("opsgenie"):
    from bot.opsgenie.api import OpsgenieAPI

    def update_opsgenie_oc_data():
        """
        Uses Opsgenie API to fetch information about on-call schedules
        """
        try:
            api = OpsgenieAPI()
            api.store_on_call_data()
        except Exception as error:
            logger.error(
                f"Error updating Opsgenie on-call information in scheduled job: {error}"
            )

    process.scheduler.add_job(
        id="update_opsgenie_oc_data",
        func=update_opsgenie_oc_data,
        trigger="interval",
        name="Update Opsgenie on-call information",
        minutes=30,
        replace_existing=True,
    )


if "pagerduty" in config.active.integrations:
    from bot.pagerduty.api import store_on_call_data

    def update_pagerduty_oc_data():
        """
        Uses PagerDuty API to fetch information about on-call schedules
        """
        try:
            store_on_call_data()
        except Exception as error:
            logger.error(
                f"Error updating PagerDuty on-call information in scheduled job: {error}"
            )

    process.scheduler.add_job(
        id="update_pagerduty_oc_data",
        func=update_pagerduty_oc_data,
        trigger="interval",
        name="Update PagerDuty on-call information",
        minutes=30,
        replace_existing=True,
    )
