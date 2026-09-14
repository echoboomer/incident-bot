"""
Tests for incidentbot/incident/status.py, the platform-neutral status change.

The point of this module is that it runs the same for Slack, Matrix and the
widget API, so what is asserted here is the part that used to be Slack-only:
the reminder jobs get cancelled on a final status.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.runtime import load_module

_status = load_module("incidentbot.incident.status")


def _make_settings(statuses=None, integrations=None):
    s = MagicMock()
    s.statuses = statuses or {}
    s.integrations = integrations
    return s


def _make_incident(slug="inc-1", channel_id="!room:example.com", status="investigating"):
    return SimpleNamespace(
        id=1,
        slug=slug,
        channel_id=channel_id,
        channel_name="inc-1",
        description="Database outage",
        status=status,
    )


class TestFinalStatuses:
    def test_returns_final_statuses(self):
        statuses = {
            "investigating": SimpleNamespace(final=False),
            "resolved": SimpleNamespace(final=True),
        }
        with patch.object(_status, "settings", _make_settings(statuses=statuses)):
            assert _status.final_statuses() == {"resolved"}

    def test_empty_statuses_returns_empty_set(self):
        with patch.object(_status, "settings", _make_settings(statuses={})):
            assert _status.final_statuses() == set()

    def test_multiple_final_statuses(self):
        statuses = {
            "investigating": SimpleNamespace(final=False),
            "resolved": SimpleNamespace(final=True),
            "postmortem": SimpleNamespace(final=True),
        }
        with patch.object(_status, "settings", _make_settings(statuses=statuses)):
            assert _status.final_statuses() == {"resolved", "postmortem"}

    def test_is_final_true(self):
        statuses = {"resolved": SimpleNamespace(final=True)}
        with patch.object(_status, "settings", _make_settings(statuses=statuses)):
            assert _status.is_final("resolved") is True

    def test_is_final_false(self):
        statuses = {
            "investigating": SimpleNamespace(final=False),
            "resolved": SimpleNamespace(final=True),
        }
        with patch.object(_status, "settings", _make_settings(statuses=statuses)):
            assert _status.is_final("investigating") is False

    def test_is_final_unknown_status_is_false(self):
        statuses = {"resolved": SimpleNamespace(final=True)}
        with patch.object(_status, "settings", _make_settings(statuses=statuses)):
            assert _status.is_final("unknown") is False

    def test_first_final_status_follows_config_order(self):
        statuses = {
            "investigating": SimpleNamespace(final=False),
            "monitoring": SimpleNamespace(final=True),
            "archived": SimpleNamespace(final=True),
        }
        with patch.object(_status, "settings", _make_settings(statuses=statuses)):
            assert _status.first_final_status() == "monitoring"

    def test_first_final_status_falls_back(self):
        with patch.object(_status, "settings", _make_settings(statuses={})):
            assert _status.first_final_status() == "resolved"


class TestBuildPostmortemTitle:
    def test_title_contains_slug_and_description(self):
        incident = SimpleNamespace(slug="inc-2024-001", description="Database outage")
        title = _status.build_postmortem_title(incident)
        assert "INC-2024-001" in title
        assert "Database outage" in title

    def test_title_contains_date(self):
        import datetime

        incident = SimpleNamespace(slug="inc-001", description="Outage")
        title = _status.build_postmortem_title(incident)
        assert datetime.datetime.today().strftime("%Y-%m-%d") in title

    def test_title_format(self):
        incident = SimpleNamespace(slug="inc-001", description="DB crash")
        # Format: "YYYY-MM-DD - INC-001 - DB crash"
        assert len(_status.build_postmortem_title(incident).split(" - ")) == 3


class TestApplyStatusChange:
    def _run(self, status, statuses=None, user=None):
        statuses = statuses or {
            "investigating": SimpleNamespace(final=False),
            "resolved": SimpleNamespace(final=True),
        }
        incident = _make_incident()
        updated = _make_incident(status=status)

        with (
            patch.object(_status, "settings", _make_settings(statuses=statuses)),
            patch.object(_status, "IncidentDatabaseInterface") as db,
            patch.object(_status, "EventLogHandler") as event_log,
            patch.object(_status, "cancel_reminder_jobs") as cancel,
            patch.object(_status, "run_automations") as automations,
        ):
            db.get_one.return_value = updated
            result, postmortem_link = _status.apply_status_change(
                incident, status, user=user
            )

        return SimpleNamespace(
            incident=incident,
            result=result,
            postmortem_link=postmortem_link,
            db=db,
            event_log=event_log,
            cancel=cancel,
            automations=automations,
        )

    def test_writes_the_status(self):
        run = self._run("identified")
        run.db.update_col.assert_called_once_with(
            channel_id=run.incident.channel_id, col_name="status", value="identified"
        )

    def test_cancels_reminder_jobs_on_a_final_status(self):
        run = self._run("resolved")
        run.cancel.assert_called_once_with("inc-1")

    def test_leaves_reminder_jobs_alone_on_a_non_final_status(self):
        run = self._run("identified")
        run.cancel.assert_not_called()

    def test_runs_the_final_status_automation_once_resolved(self):
        run = self._run("resolved")
        triggers = [call.args[0] for call in run.automations.call_args_list]
        assert triggers == ["on_status_change", "on_final_status"]

    def test_automations_see_the_committed_record(self):
        run = self._run("resolved")
        assert run.automations.call_args_list[0].args[1] is run.result

    def test_event_log_records_the_user(self):
        run = self._run("identified", user="@alice:example.com")
        assert run.event_log.create.call_args[1]["user"] == "@alice:example.com"

    def test_a_second_resolve_does_nothing(self):
        """Resolving twice must not fire the final-status automations again.

        A retry, two responders or a double-clicked button all send it twice,
        and on_final_status is wired to whatever pages people.
        """
        incident = _make_incident(status="resolved")
        statuses = {
            "investigating": SimpleNamespace(final=False),
            "resolved": SimpleNamespace(final=True),
        }

        with (
            patch.object(_status, "settings", _make_settings(statuses=statuses)),
            patch.object(_status, "IncidentDatabaseInterface") as db,
            patch.object(_status, "cancel_reminder_jobs") as cancel,
            patch.object(_status, "run_automations") as automations,
        ):
            result, postmortem_link = _status.apply_status_change(incident, "resolved")

        assert result is incident
        assert postmortem_link is None
        db.update_col.assert_not_called()
        cancel.assert_not_called()
        automations.assert_not_called()

    def test_a_failed_write_stops_the_status_change(self):
        """No silent half-change: reminders must not be cancelled for an open incident."""
        incident = _make_incident()
        statuses = {"resolved": SimpleNamespace(final=True)}

        with (
            patch.object(_status, "settings", _make_settings(statuses=statuses)),
            patch.object(_status, "IncidentDatabaseInterface") as db,
            patch.object(_status, "EventLogHandler"),
            patch.object(_status, "cancel_reminder_jobs") as cancel,
            patch.object(_status, "run_automations") as automations,
            patch.object(_status, "_create_postmortem", return_value=None),
            patch.object(_status, "_resolve_pagerduty_incidents"),
        ):
            db.update_col.side_effect = RuntimeError("database down")

            try:
                _status.apply_status_change(incident, "resolved")
            except RuntimeError:
                pass
            else:
                raise AssertionError("apply_status_change swallowed the write failure")

        cancel.assert_not_called()
        automations.assert_not_called()

    def test_only_the_first_final_status_opens_a_postmortem(self):
        """resolved opens one; a later archived must not open a second."""
        incident = _make_incident(status="resolved")
        statuses = {
            "investigating": SimpleNamespace(final=False),
            "resolved": SimpleNamespace(final=True),
            "archived": SimpleNamespace(final=True),
        }

        with (
            patch.object(_status, "settings", _make_settings(statuses=statuses)),
            patch.object(_status, "IncidentDatabaseInterface") as db,
            patch.object(_status, "EventLogHandler"),
            patch.object(_status, "cancel_reminder_jobs") as cancel,
            patch.object(_status, "run_automations"),
            patch.object(_status, "_create_postmortem") as postmortem,
            patch.object(_status, "_resolve_pagerduty_incidents") as pagerduty,
        ):
            db.get_one.return_value = _make_incident(status="archived")
            _status.apply_status_change(incident, "archived")

        postmortem.assert_not_called()
        pagerduty.assert_not_called()
        # Still a final status, so the reminders do go.
        cancel.assert_called_once_with("inc-1")
