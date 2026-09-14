from html import escape
from incidentbot.configuration.settings import settings
from incidentbot.incident.status import (
    apply_status_change,
    final_statuses,
    first_final_status,
)
from incidentbot.logging import logger
from incidentbot.matrix.messages import MatrixMessages
from incidentbot.models.database import (
    IncidentParticipant,
    IncidentRecord,
    engine,
)
from incidentbot.models.incident import IncidentDatabaseInterface
from incidentbot.platform import get_adapter
from sqlmodel import Session, select


COMMAND_PREFIX = "!incident"


def parse(body: str) -> tuple[str, list[str]] | None:
    """Parse a message body into (subcommand, args). Returns None if not a bot command."""
    stripped = body.strip()
    if not stripped.startswith(COMMAND_PREFIX):
        return None
    parts = stripped[len(COMMAND_PREFIX) :].strip().split()
    if not parts:
        return ("help", [])
    return (parts[0].lower(), parts[1:])


async def handle_help(room_id: str, client, digest_room_id: str = "") -> None:
    plain, html = MatrixMessages.help(digest_room_id)
    await client.send_text_async(room_id, plain, html)


async def handle_status(room_id: str, client) -> None:
    with Session(engine) as session:
        # From config, not a hardcoded pair: an install with its own final
        # status was listing closed incidents as open.
        incidents = session.exec(
            select(IncidentRecord).where(
                ~IncidentRecord.status.in_(sorted(final_statuses()) or ["resolved"])
            )
        ).all()

    if not incidents:
        await client.send_text_async(room_id, "No active incidents.")
        return

    lines_plain = ["Active incidents:"]
    lines_html = ["<b>Active incidents:</b><ul>"]
    for inc in incidents:
        room_link = f"https://matrix.to/#/{inc.channel_id}"
        lines_plain.append(
            f"  {inc.slug} | {inc.severity.upper()} | {inc.status.title()} — {inc.description}"
        )
        lines_html.append(
            f'<li><a href="{escape(room_link)}">{escape(inc.slug)}</a> '
            f"| {escape(inc.severity.upper())} | {escape(inc.status.title())} "
            f"— {escape(inc.description)}</li>"
        )
    lines_html.append("</ul>")
    await client.send_text_async(room_id, "\n".join(lines_plain), "".join(lines_html))


async def handle_join(room_id: str, args: list[str], sender: str, client) -> None:
    if len(args) < 2:
        await client.send_text_async(
            room_id, "Usage: !incident join <incident_id> <role>"
        )
        return

    incident_id_str, role = args[0], " ".join(args[1:])
    try:
        incident_id = int(incident_id_str)
    except ValueError:
        await client.send_text_async(room_id, f"Invalid incident ID: {incident_id_str}")
        return

    with Session(engine) as session:
        record = session.get(IncidentRecord, incident_id)
        if not record:
            await client.send_text_async(room_id, f"Incident {incident_id} not found.")
            return
        roles = record.roles_all or []
        matched = [r for r in roles if role.lower() in r.lower()]
        if not matched:
            await client.send_text_async(
                room_id,
                f"Unknown role '{role}'. Available: {', '.join(roles)}",
            )
            return
        assigned_role = matched[0]
        role_config = settings.roles.get(assigned_role)
        existing = session.exec(
            select(IncidentParticipant).where(
                IncidentParticipant.parent == record.id,
                IncidentParticipant.role == assigned_role,
                IncidentParticipant.user_id == sender,
            )
        ).first()
        if existing:
            await client.send_text_async(
                room_id,
                f"You have already joined {record.slug} as {assigned_role.replace('_', ' ').title()}.",
            )
            return

        display_name = await client.get_display_name_async(sender)
        participant = IncidentParticipant(
            is_lead=role_config.is_lead if role_config else False,
            parent=record.id,
            role=assigned_role,
            user_id=sender,
            user_name=display_name,
        )
        session.add(participant)
        session.commit()
        session.refresh(record)
        incident_channel_id = record.channel_id
        incident_severity = record.severity
        incident_status = record.status
        incident_slug = record.slug
        is_private = record.has_private_channel

    if is_private:
        await client.invite_user_async(incident_channel_id, sender)

    if role_config and role_config.is_lead:
        logger.info(
            "updating topic for incident room", room_id=incident_channel_id, role=assigned_role
        )
        await client.set_room_topic_async(
            incident_channel_id,
            f"Severity: {incident_severity.upper()} | "
            f"Status: {incident_status.title()} | "
            f"{assigned_role.replace('_', ' ').title()}: {display_name}",
        )
    else:
        logger.debug(
            "skipping topic update", role_config=role_config, is_lead=getattr(role_config, "is_lead", None)
        )

    await client.send_text_async(
        room_id,
        f"{display_name} joined {incident_slug} as {assigned_role.replace('_', ' ').title()}.",
    )


async def handle_severity(room_id: str, args: list[str], client) -> None:
    if len(args) < 2:
        await client.send_text_async(
            room_id, "Usage: !incident severity <incident_id> <severity>"
        )
        return

    incident_id_str, new_severity = args[0], args[1].lower()
    try:
        incident_id = int(incident_id_str)
    except ValueError:
        await client.send_text_async(room_id, f"Invalid incident ID: {incident_id_str}")
        return

    with Session(engine) as session:
        record = session.get(IncidentRecord, incident_id)
        if not record:
            await client.send_text_async(room_id, f"Incident {incident_id} not found.")
            return
        valid = list(record.severities or [])
        if new_severity not in valid:
            await client.send_text_async(
                room_id,
                f"Invalid severity '{new_severity}'. Valid: {', '.join(valid)}",
            )
            return
        record.severity = new_severity
        session.add(record)
        session.commit()

    lead_participant = None
    with Session(engine) as session:
        lead_participant = session.exec(
            select(IncidentParticipant).where(
                IncidentParticipant.parent == record.id,
                IncidentParticipant.is_lead == True,  # noqa: E712
            )
        ).first()
    topic = f"Severity: {record.severity.upper()} | Status: {record.status.title()}"
    if lead_participant:
        topic += (
            f" | {lead_participant.role.replace('_', ' ').title()}: "
            f"{lead_participant.user_name}"
        )
    get_adapter().set_room_topic(room_id=record.channel_id, topic=topic)

    await client.send_text_async(
        room_id,
        f"Severity for {record.slug} updated to {new_severity.upper()}.",
    )


async def handle_resolve(room_id: str, args: list[str], client) -> None:
    if not args:
        await client.send_text_async(room_id, "Usage: !incident resolve <incident_id>")
        return

    try:
        incident_id = int(args[0])
    except ValueError:
        await client.send_text_async(room_id, f"Invalid incident ID: {args[0]}")
        return

    record = IncidentDatabaseInterface.get_one(id=incident_id)
    if not record:
        await client.send_text_async(room_id, f"Incident {incident_id} not found.")
        return

    final_status = first_final_status()

    # Not a plain status write: this also cancels the reminder jobs, syncs the
    # ticket and runs the on_final_status automations. Writing record.status
    # here instead left the reminders firing for a resolved incident.
    record, postmortem_link = apply_status_change(record, final_status)

    lead_participant = None
    with Session(engine) as session:
        lead_participant = session.exec(
            select(IncidentParticipant).where(
                IncidentParticipant.parent == record.id,
                IncidentParticipant.is_lead == True,  # noqa: E712
            )
        ).first()
    topic = f"Severity: {record.severity.upper()} | Status: {record.status.title()}"
    if lead_participant:
        topic += (
            f" | {lead_participant.role.replace('_', ' ').title()}: "
            f"{lead_participant.user_name}"
        )
    get_adapter().set_room_topic(room_id=record.channel_id, topic=topic)

    await client.send_text_async(room_id, f"{record.slug} marked as {final_status}.")

    if postmortem_link:
        await client.send_text_async(room_id, f"Postmortem: {postmortem_link}")
