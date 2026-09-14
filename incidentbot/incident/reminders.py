from incidentbot.configuration.settings import settings
from incidentbot.incident.conditions import evaluate
from incidentbot.logging import logger
from incidentbot.models.incident import IncidentDatabaseInterface
from incidentbot.platform import get_adapter
from incidentbot.scheduler.core import process as TaskScheduler


def _job_id(slug: str, reminder_id: str) -> str:
    return f"{slug}_{reminder_id}"


def _delete_jobs_for(channel_id: str, reminder_id: str) -> None:
    """Remove the jobs firing for this channel and reminder.

    Looked up by args, not by id: an incident that is gone from the database
    cannot be addressed by its slug any more.
    """
    try:
        for job in TaskScheduler.list_jobs():
            if list(job.args or []) == [channel_id, reminder_id]:
                TaskScheduler.delete_job(job_to_delete=job.id)
    except Exception as error:
        logger.exception(
            "error removing orphaned reminder job",
            channel_id=channel_id,
            reminder=reminder_id,
            error=error,
        )


def run_reminder(channel_id: str, reminder_id: str) -> None:
    """Generic APScheduler job function for all configured reminders."""
    # Local import: incident.status imports cancel_reminder_jobs from here.
    from incidentbot.incident.status import is_final

    reminder = next((r for r in settings.reminders if r.id == reminder_id), None)
    if not reminder or not reminder.enabled:
        return

    record = IncidentDatabaseInterface.get_one(channel_id=channel_id)

    # A job for a resolved incident deletes itself. Without this, one incident
    # resolved outside the Slack handler kept a job posting into a room the bot
    # had already left, every interval, until the next restart.
    if record and is_final(record.status):
        _delete_jobs_for(channel_id, reminder_id)
        return

    # No record is not proof the incident is gone: get_one logs and returns None
    # for a connection blip too, and the jobs live in memory only, so deleting
    # here would silence an open incident for good. Skip this tick instead.
    if not record:
        return

    if not evaluate(reminder.conditions, record):
        return

    try:
        get_adapter().post_reminder(channel_id, reminder, record.slug)
    except Exception as error:
        logger.exception("error sending reminder message", reminder=reminder_id, error=error)
        return

    if reminder.once:
        try:
            job = TaskScheduler.get_job(job_id=_job_id(record.slug, reminder_id))
            if job:
                TaskScheduler.delete_job(job.id)
        except Exception as error:
            logger.exception("error removing once-only reminder job", reminder=reminder_id, error=error)


def register_reminder_jobs(record) -> None:
    """Register APScheduler interval jobs for all enabled reminders."""
    for reminder in settings.reminders:
        if not reminder.enabled:
            continue
        try:
            TaskScheduler.scheduler.add_job(
                id=_job_id(record.slug, reminder.id),
                func=run_reminder,
                args=[record.channel_id, reminder.id],
                trigger="interval",
                name=_job_id(record.slug, reminder.id),
                minutes=reminder.interval_minutes,
                replace_existing=True,
            )
        except Exception as error:
            logger.exception("error registering reminder job", reminder=reminder.id, error=error)


def cancel_reminder_jobs(slug: str) -> None:
    """Remove all reminder jobs for an incident (called on final status)."""
    for reminder in settings.reminders:
        job_id = _job_id(slug, reminder.id)
        try:
            job = TaskScheduler.get_job(job_id=job_id)
            if job:
                TaskScheduler.delete_job(job_to_delete=job.id)
        except Exception as error:
            logger.exception("error removing reminder job", reminder=reminder.id, error=error)


def handle_snooze(channel_id: str, reminder_id: str, minutes: int, ts: str) -> None:
    """Reschedule a reminder job and acknowledge in channel."""
    # ponytail: Slack-only — driven by a Block Kit button, and only called from
    # slack/handler.py. Route through the adapter if Matrix ever grows an equivalent.
    from incidentbot.slack.client import slack_web_client

    record = IncidentDatabaseInterface.get_one(channel_id=channel_id)
    if not record:
        return

    job_id = _job_id(record.slug, reminder_id)
    try:
        job = TaskScheduler.get_job(job_id=job_id)
        if job:
            TaskScheduler.reschedule_job(job_id=job.id, new_minutes=minutes)
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=f":white_check_mark: Got it. I'll remind the channel again in *{minutes} minutes*.",
        )
        slack_web_client.chat_delete(channel=channel_id, ts=ts)
    except Exception as error:
        logger.exception("error snoozing reminder", reminder=reminder_id, error=error)


def handle_dismiss(channel_id: str, reminder_id: str, ts: str) -> None:
    """Permanently cancel a reminder job and acknowledge in channel."""
    # ponytail: Slack-only, see handle_snooze.
    from incidentbot.slack.client import slack_web_client

    record = IncidentDatabaseInterface.get_one(channel_id=channel_id)
    if not record:
        return

    job_id = _job_id(record.slug, reminder_id)
    try:
        job = TaskScheduler.get_job(job_id=job_id)
        if job:
            TaskScheduler.delete_job(job_to_delete=job.id)
        slack_web_client.chat_postMessage(
            channel=channel_id,
            text=":white_check_mark: Got it. I won't send any more reminders for this incident.",
        )
        slack_web_client.chat_delete(channel=channel_id, ts=ts)
    except Exception as error:
        logger.exception("error dismissing reminder", reminder=reminder_id, error=error)
