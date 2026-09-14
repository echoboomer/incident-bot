"""The platform-neutral half of a status change.

Everything in here happens the same way no matter where the change came from:
Slack, a Matrix command or the widget API. The postmortem, the ticket sync, the
database write, the event log, the automations and the reminder jobs.

Only the chat messages differ per platform, so those stay in the handler that
owns them. Before this module the whole lot lived inside the Slack handler, and
the Matrix paths wrote ``record.status`` and stopped there: the reminder jobs
kept firing for an incident that was already resolved.
"""

import datetime

from incidentbot.configuration.settings import settings
from incidentbot.incident.automations import run as run_automations
from incidentbot.incident.event import EventLogHandler
from incidentbot.incident.reminders import cancel_reminder_jobs
from incidentbot.logging import logger
from incidentbot.models.database import IncidentRecord
from incidentbot.models.incident import IncidentDatabaseInterface


def final_statuses() -> set[str]:
    """The configured statuses that end an incident."""
    statuses = settings.statuses or {}
    return {
        status_name
        for status_name, config in statuses.items()
        if getattr(config, "final", False)
    }


def is_final(status: str) -> bool:
    return status in final_statuses()


def first_final_status(default: str = "resolved") -> str:
    """The status a plain "resolve" lands on: the first final one in config order."""
    for status_name, config in (settings.statuses or {}).items():
        if getattr(config, "final", False):
            return status_name
    return default


def build_postmortem_title(incident: IncidentRecord) -> str:
    return (
        f"{datetime.datetime.today().strftime('%Y-%m-%d')} - "
        f"{incident.slug.upper()} - {incident.description}"
    )


def _postmortem_classes() -> list[type]:
    """Every enabled postmortem integration, in the order they are created.

    Both can be on at once, and an install with both expects both pages.
    """
    integrations = settings.integrations
    if not integrations:
        return []

    classes = []

    confluence = getattr(getattr(integrations, "atlassian", None), "confluence", None)
    if confluence and confluence.enabled and confluence.auto_create_postmortem:
        from incidentbot.confluence.postmortem import IncidentPostmortem as Confluence

        classes.append(Confluence)

    gitlab = getattr(integrations, "gitlab", None)
    if gitlab and gitlab.enabled and gitlab.auto_create_postmortem:
        from incidentbot.gitlab.postmortem import IncidentPostmortem as GitLab

        classes.append(GitLab)

    return classes


def _create_postmortem(incident: IncidentRecord) -> str | None:
    """Create the postmortems for a resolved incident, once.

    Returns the first link, or None when no integration is enabled or a
    postmortem already exists.
    """
    if IncidentDatabaseInterface.get_postmortem(parent=incident.id):
        return None

    first_link = None

    for postmortem_class in _postmortem_classes():
        postmortem_link = postmortem_class(
            incident=incident,
            participants=IncidentDatabaseInterface.list_participants(incident=incident),
            timeline=EventLogHandler.read(incident_id=incident.id),
            title=build_postmortem_title(incident),
        ).create()

        if not postmortem_link:
            continue

        IncidentDatabaseInterface.add_postmortem(
            parent=incident.id, url=postmortem_link
        )
        EventLogHandler.create(
            event="Postmortem generated",
            incident_id=incident.id,
            incident_slug=incident.slug,
            source="system",
        )
        first_link = first_link or postmortem_link

    return first_link


def _resolve_pagerduty_incidents(incident: IncidentRecord) -> None:
    integrations = settings.integrations
    pagerduty = getattr(integrations, "pagerduty", None) if integrations else None
    if not pagerduty or not pagerduty.enabled:
        return

    from incidentbot.pagerduty.api import PagerDutyInterface

    pagerduty_interface = PagerDutyInterface()

    for record in (
        IncidentDatabaseInterface.list_pagerduty_incident_records(id=incident.id) or []
    ):
        try:
            pagerduty_interface.resolve(record.url.split("/")[-1])
        except Exception as error:
            logger.exception(
                "error resolving pagerduty incident", url=record.url, error=error
            )


def _sync_tickets(incident: IncidentRecord, status: str) -> None:
    integrations = settings.integrations
    if not integrations:
        return

    jira = getattr(getattr(integrations, "atlassian", None), "jira", None)
    if jira and jira.enabled and jira.status_mapping:
        from incidentbot.jira.api import JiraApi

        JiraApi().update_issue_status(
            incident_name=incident.channel_name,
            incident_status=status,
        )

    gitlab = getattr(integrations, "gitlab", None)
    if gitlab and gitlab.enabled and gitlab.status_mapping:
        from incidentbot.gitlab.api import GitLabApi

        GitLabApi().update_issue_status(
            incident_name=incident.channel_name, incident_status=status
        )
        logger.info(
            "updated gitlab issue status",
            channel=incident.channel_name,
            status=status,
        )


def apply_status_change(
    incident: IncidentRecord, status: str, user: str | None = None
) -> tuple[IncidentRecord, str | None]:
    """Carry out a status change for `incident`.

    `user` is whoever asked for it, when the platform knows; it lands in the
    event log. Returns the re-read record and the postmortem link, if one was
    created. Every caller must go through this, or the reminder jobs outlive the
    incident.
    """

    # Asking for the status it already has does nothing. Without this, a second
    # resolve (a retry, two responders, a double-clicked button) fires the
    # on_final_status automations again, and whatever they page.
    if incident.status == status:
        logger.info(
            "incident status unchanged, nothing to do",
            channel=incident.channel_name,
            status=status,
        )
        return incident, None

    postmortem_link = None

    # Only the first final status opens a postmortem and resolves the pager. A
    # later one, say archived after resolved, must not do either again.
    if is_final(status) and status == first_final_status():
        postmortem_link = _create_postmortem(incident)
        _resolve_pagerduty_incidents(incident)

    _sync_tickets(incident, status)

    # Deliberately not swallowed: the caller has to fail visibly. Carrying on
    # would cancel the reminders and run the final-status automations for an
    # incident the database still has as open.
    IncidentDatabaseInterface.update_col(
        channel_id=incident.channel_id,
        col_name="status",
        value=status,
    )

    EventLogHandler.create(
        event=f"The incident status was changed to {status}",
        incident_id=incident.id,
        incident_slug=incident.slug,
        source="system",
        user=user,
    )

    logger.info(
        "updated incident status", channel=incident.channel_name, status=status
    )

    # Re-fetch so automations see the committed status value
    updated_incident = (
        IncidentDatabaseInterface.get_one(channel_id=incident.channel_id) or incident
    )
    run_automations("on_status_change", updated_incident)

    if is_final(status):
        cancel_reminder_jobs(incident.slug)
        run_automations("on_final_status", updated_incident)

    return updated_incident, postmortem_link
