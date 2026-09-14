"""
Tests for `!incident resolve` in incidentbot/matrix/commands.py.

This is the path from the bug report: it used to write record.status straight to
the session, which left the reminder jobs firing for a resolved incident.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.runtime import load_module

_commands = load_module("incidentbot.matrix.commands")

ROOM = "!room:example.com"


class FakeClient:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_text_async(self, room_id, text, html=None):
        self.sent.append((room_id, text))


def _make_record(status="investigating"):
    return SimpleNamespace(
        id=42,
        slug="inc-42",
        channel_id="!incident:example.com",
        channel_name="inc-42",
        severity="sev2",
        status=status,
        description="Database outage",
    )


def _resolve(args, *, record, apply_result=None, postmortem_link=None):
    client = FakeClient()
    resolved = _make_record(status="resolved")
    apply = MagicMock(return_value=(apply_result or resolved, postmortem_link))
    session = MagicMock()
    session.__enter__.return_value = session
    session.exec.return_value.first.return_value = None

    with (
        patch.object(_commands, "IncidentDatabaseInterface") as db,
        patch.object(_commands, "apply_status_change", apply),
        patch.object(_commands, "first_final_status", return_value="resolved"),
        patch.object(_commands, "Session", return_value=session),
        patch.object(_commands, "get_adapter") as adapter,
    ):
        db.get_one.return_value = record
        asyncio.run(_commands.handle_resolve(ROOM, args, client))

    return SimpleNamespace(client=client, apply=apply, adapter=adapter, db=db)


class TestHandleResolve:
    def test_routes_through_apply_status_change(self):
        record = _make_record()
        run = _resolve(["42"], record=record)

        run.apply.assert_called_once_with(record, "resolved")
        assert run.client.sent[0][1] == "inc-42 marked as resolved."

    def test_looks_the_incident_up_by_id(self):
        run = _resolve(["42"], record=_make_record())
        run.db.get_one.assert_called_once_with(id=42)

    def test_sets_the_room_topic_from_the_updated_record(self):
        run = _resolve(["42"], record=_make_record())
        topic = run.adapter.return_value.set_room_topic.call_args[1]["topic"]
        assert topic == "Severity: SEV2 | Status: Resolved"

    def test_reports_the_postmortem_link(self):
        """Slack posts it; the Matrix room was left in the dark before."""
        run = _resolve(
            ["42"], record=_make_record(), postmortem_link="https://gitlab.example/-/issues/7"
        )
        assert run.client.sent[-1][1] == "Postmortem: https://gitlab.example/-/issues/7"

    def test_no_link_means_no_second_message(self):
        run = _resolve(["42"], record=_make_record())
        assert len(run.client.sent) == 1

    def test_unknown_incident_is_reported_and_changes_nothing(self):
        run = _resolve(["42"], record=None)
        assert run.client.sent == [(ROOM, "Incident 42 not found.")]
        run.apply.assert_not_called()

    def test_a_non_numeric_id_is_refused(self):
        client = FakeClient()
        with patch.object(_commands, "apply_status_change") as apply:
            asyncio.run(_commands.handle_resolve(ROOM, ["abc"], client))
        assert client.sent == [(ROOM, "Invalid incident ID: abc")]
        apply.assert_not_called()

    def test_without_an_id_it_explains_itself(self):
        client = FakeClient()
        with patch.object(_commands, "apply_status_change") as apply:
            asyncio.run(_commands.handle_resolve(ROOM, [], client))
        assert client.sent == [(ROOM, "Usage: !incident resolve <incident_id>")]
        apply.assert_not_called()
