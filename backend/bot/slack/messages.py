import logging

from apscheduler.job import Job
from bot.shared import tools
from typing import Dict, List
from .client import bot_user_name, bot_user_id

logger = logging.getLogger(__name__)


def help_menu(include_header: bool = True) -> List:
    """
    Returns the formatted help menu for the bot
    """
    blocks = []
    if include_header:
        blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":robot_face: {bot_user_name} Help",
                },
            },
        )
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"To use any of these commands, simply mention me and then provide the command listed below. For example: `<@{bot_user_id}> lsai`",
            },
        }
    )
    commands = {
        "help": "This command that explains help options.",
        "new <description>": "Start a new incident.",
        "lsai": "List *all* incidents regardless of status.",
        "lsoi": "List only incidents that are still *open* - as in non-resolved.",
        "ls-sp-inc": "List *open* Statuspage incidents.",
        "pager": "Return information from PagerDuty regarding who is currently on call. You may optionally page them.",
        "ping": "Ping the bot to check and see if it's alive and responding.",
        "scheduler list": "List any jobs tasked to the scheduler.",
        "scheduler delete <job_id>": "Delete a job using the ID returned by scheduler list.",
        "version": "Have the bot respond with current application version.",
    }
    txt = ""
    for key, value in commands.items():
        txt += f"- `{key}`: {value}\n"
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": txt.strip()},
        },
    )
    return blocks


def incident_list_message(incidents: List, all: bool = False) -> List[Dict[str, str]]:
    """Return a message containing details on incidents

    Keyword arguments:
    incidents -- List[Tuple] containing incident information
    all -- Bool indicating whether or not all incidents should be returned regardless of status
    """
    base_block = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":open_file_folder: Open Incidents"},
        },
        {"type": "divider"},
    ]
    formatted_incidents = []
    none_found_block = [
        {"type": "divider"},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":open_file_folder: No Open Incidents",
            },
        },
        {"type": "divider"},
    ]
    # Check to see if there are any incidents
    if len(incidents) == 0:
        return none_found_block
    else:
        for inc in incidents:
            if all == True:
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
                        ],
                    }
                )
                formatted_incidents.append({"type": "divider"})
            elif all == False:
                if inc.status != "resolved":
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
                            ],
                        }
                    )
                    formatted_incidents.append({"type": "divider"})
    if len(formatted_incidents) == 0:
        return none_found_block
    else:
        for inc in formatted_incidents:
            base_block.append(inc)

    return base_block


def job_list_message(jobs: List[Job]) -> Dict[str, str]:
    """Return a message containing details on scheduled jobs

    Keyword arguments:
    channel_id -- String containing the ID of the Slack channel to send the message to
    jobs -- List[Job] containing the list of jobs returned from the APScheduler API
    """
    base_block = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":timer_clock: Scheduled Jobs"},
        },
        {"type": "divider"},
    ]
    formatted_jobs = []
    none_found_block = [
        {"type": "divider"},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":timer_clock: No Scheduled Jobs",
            },
        },
        {"type": "divider"},
    ]
    # Check to see if there are any scheduled jobs
    if len(jobs) == 0:
        return none_found_block
    else:
        for job in jobs:
            formatted_jobs.append(
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Name:* {job.name}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*ID:* {job.id}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Next Run:* {job.next_run_time}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Function:* {job.func}",
                        },
                    ],
                }
            )
            formatted_jobs.append({"type": "divider"})
    if len(formatted_jobs) == 0:
        return none_found_block
    else:
        for job in formatted_jobs:
            base_block.append(job)
        return base_block


def pd_on_call_message(data: Dict) -> List:
    """Return a message containing details on on-call participants

    Keyword arguments:
    data -- Dictionary containing information about who is currently on call
    """
    base_block = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":pager: Who is on call right now?"},
        },
        {"type": "divider"},
    ]
    if data is not {}:
        for key, value in data.items():
            options = []
            for v in value:
                if v["slack_user_id"] != []:
                    user_mention = v["slack_user_id"][0]
                else:
                    user_mention = v["user"]
                options.append(
                    {
                        "text": {
                            "type": "plain_text",
                            "text": "{} {}".format(v["escalation_level"], v["user"]),
                        },
                        "value": user_mention,
                    },
                )
            base_block.append(
                {
                    "type": "section",
                    "block_id": "ping_oncall_{}".format(
                        [v["escalation_policy_id"] for v in value][0]
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
        base_block.append({"type": "divider"})
        base_block.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "image",
                        "image_url": "https://i.imgur.com/IVvdFCV.png",
                        "alt_text": "pagerduty",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"This information is sourced from PagerDuty and is accurate as of {tools.fetch_timestamp()}.",
                    },
                ],
            }
        )
    else:
        base_block.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "I was unable to find any information about who is on call right now. An error was logged: ",
                },
            }
        ),
    return base_block


def sp_incident_list_message(incidents: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Return a message containing details on Statuspage incidents

    Keyword arguments:
    incidents -- List[Dict[str, str]] containing Statuspage incident information
    """
    base_block = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":open_file_folder: Open Statuspage Incidents",
            },
        },
        {"type": "divider"},
    ]
    formatted_incidents = []
    none_found_block = [
        {"type": "divider"},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":open_file_folder: No Open Statuspage Incidents",
            },
        },
        {"type": "divider"},
    ]
    # Check to see if there are any incidents
    if len(incidents) == 0:
        return none_found_block
    else:
        for inc in incidents:
            name = inc["name"]
            status = inc["status"]
            impact = inc["impact"]
            created_at = inc["created_at"]
            updated_at = inc["updated_at"]
            shortlink = inc["shortlink"]
            if inc["status"] != "resolved":
                formatted_incidents.append(
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Name:* {name}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Status* {status}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Impact:* {impact}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Created:* {created_at}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Last Updated:* {updated_at}",
                            },
                        ],
                    }
                )
                formatted_incidents.append(
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Open In Statuspage",
                                },
                                "url": shortlink,
                            },
                        ],
                    },
                )
                formatted_incidents.append({"type": "divider"})
    if len(formatted_incidents) == 0:
        return none_found_block
    else:
        for inc in formatted_incidents:
            base_block.append(inc)

    return base_block
