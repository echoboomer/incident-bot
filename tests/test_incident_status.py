"""
Tests for incidentbot/incident/status.py, the platform-neutral status change.

The point of this module is that it runs the same for Slack, Matrix and the
widget API, so what is asserted here is the part that used to be Slack-only:
the reminder jobs get cancelled on a final status.
"""
import sys
from types import ModuleType, SimpleNamespace
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


def _stub_module(name: str, attr: str, value) -> ModuleType:
    """Put a stand-in module in sys.modules for an import inside a function.

    status.py imports the integration clients lazily, so the usual patch target
    does not exist until the call happens, and importing the real module would
    drag in the whole GitLab or Confluence client.
    """
    module = ModuleType(name)
    setattr(module, attr, value)
    sys.modules[name] = module
    return module


def _integrations(
    *, gitlab_postmortem=False, confluence_postmortem=False, gitlab_mapping=None,
    jira_mapping=None, pagerduty=False,
):
    gitlab = SimpleNamespace(
        enabled=bool(gitlab_postmortem or gitlab_mapping),
        auto_create_postmortem=gitlab_postmortem,
        status_mapping=gitlab_mapping,
    )
    confluence = SimpleNamespace(
        enabled=confluence_postmortem, auto_create_postmortem=confluence_postmortem
    )
    jira = SimpleNamespace(enabled=bool(jira_mapping), status_mapping=jira_mapping)
    return SimpleNamespace(
        gitlab=gitlab,
        atlassian=SimpleNamespace(confluence=confluence, jira=jira),
        pagerduty=SimpleNamespace(enabled=pagerduty),
    )


class TestPostmortem:
    def test_no_integrations_means_no_postmortem(self):
        with patch.object(_status, "settings", _make_settings(integrations=None)):
            assert _status._postmortem_classes() == []

    def test_both_integrations_run(self):
        """An install with both enabled expects both pages, not the last one.

        This is exactly what a single postmortem_class variable got wrong.
        """
        confluence = MagicMock(name="ConfluencePostmortem")
        gitlab = MagicMock(name="GitLabPostmortem")
        _stub_module("incidentbot.confluence.postmortem", "IncidentPostmortem", confluence)
        _stub_module("incidentbot.gitlab.postmortem", "IncidentPostmortem", gitlab)

        settings = _make_settings(
            integrations=_integrations(gitlab_postmortem=True, confluence_postmortem=True)
        )
        with patch.object(_status, "settings", settings):
            assert _status._postmortem_classes() == [confluence, gitlab]

    def test_only_confluence(self):
        confluence = MagicMock(name="ConfluencePostmortem")
        _stub_module("incidentbot.confluence.postmortem", "IncidentPostmortem", confluence)

        settings = _make_settings(integrations=_integrations(confluence_postmortem=True))
        with patch.object(_status, "settings", settings):
            assert _status._postmortem_classes() == [confluence]

    def test_only_gitlab(self):
        gitlab = MagicMock(name="GitLabPostmortem")
        _stub_module("incidentbot.gitlab.postmortem", "IncidentPostmortem", gitlab)

        settings = _make_settings(integrations=_integrations(gitlab_postmortem=True))
        with patch.object(_status, "settings", settings):
            assert _status._postmortem_classes() == [gitlab]

    def test_skips_creation_when_one_already_exists(self):
        with (
            patch.object(_status, "IncidentDatabaseInterface") as db,
            patch.object(_status, "_postmortem_classes") as classes,
        ):
            db.get_postmortem.return_value = MagicMock()
            assert _status._create_postmortem(_make_incident()) is None
        classes.assert_not_called()

    def test_records_the_link_and_writes_the_event_log(self):
        postmortem = MagicMock()
        postmortem.return_value.create.return_value = "https://gitlab.example/issues/1"

        with (
            patch.object(_status, "IncidentDatabaseInterface") as db,
            patch.object(_status, "EventLogHandler") as event_log,
            patch.object(_status, "_postmortem_classes", return_value=[postmortem]),
        ):
            db.get_postmortem.return_value = None
            link = _status._create_postmortem(_make_incident())

        assert link == "https://gitlab.example/issues/1"
        db.add_postmortem.assert_called_once_with(
            parent=1, url="https://gitlab.example/issues/1"
        )
        event_log.create.assert_called_once()

    def test_a_failed_creation_returns_nothing(self):
        postmortem = MagicMock()
        postmortem.return_value.create.return_value = None

        with (
            patch.object(_status, "IncidentDatabaseInterface") as db,
            patch.object(_status, "EventLogHandler"),
            patch.object(_status, "_postmortem_classes", return_value=[postmortem]),
        ):
            db.get_postmortem.return_value = None
            assert _status._create_postmortem(_make_incident()) is None
        db.add_postmortem.assert_not_called()


class TestTicketSync:
    def test_nothing_happens_without_a_status_mapping(self):
        settings = _make_settings(integrations=_integrations())
        with patch.object(_status, "settings", settings):
            # No stub modules registered, so an import here would raise.
            _status._sync_tickets(_make_incident(), "resolved")

    def test_gitlab_and_jira_are_both_updated(self):
        gitlab_api = MagicMock()
        jira_api = MagicMock()
        _stub_module("incidentbot.gitlab.api", "GitLabApi", gitlab_api)
        _stub_module("incidentbot.jira.api", "JiraApi", jira_api)

        settings = _make_settings(
            integrations=_integrations(
                gitlab_mapping={"resolved": "closed"}, jira_mapping={"resolved": "Done"}
            )
        )
        with patch.object(_status, "settings", settings):
            _status._sync_tickets(_make_incident(), "resolved")

        gitlab_api.return_value.update_issue_status.assert_called_once_with(
            incident_name="inc-1", incident_status="resolved"
        )
        jira_api.return_value.update_issue_status.assert_called_once_with(
            incident_name="inc-1", incident_status="resolved"
        )


class TestPagerDuty:
    def test_nothing_happens_when_disabled(self):
        settings = _make_settings(integrations=_integrations(pagerduty=False))
        with patch.object(_status, "settings", settings):
            _status._resolve_pagerduty_incidents(_make_incident())

    def test_every_linked_incident_is_resolved(self):
        interface = MagicMock()
        _stub_module("incidentbot.pagerduty.api", "PagerDutyInterface", interface)

        settings = _make_settings(integrations=_integrations(pagerduty=True))
        with (
            patch.object(_status, "settings", settings),
            patch.object(_status, "IncidentDatabaseInterface") as db,
        ):
            db.list_pagerduty_incident_records.return_value = [
                SimpleNamespace(url="https://pd.example/incidents/PD1"),
                SimpleNamespace(url="https://pd.example/incidents/PD2"),
            ]
            _status._resolve_pagerduty_incidents(_make_incident())

        assert [c.args[0] for c in interface.return_value.resolve.call_args_list] == [
            "PD1",
            "PD2",
        ]

    def test_one_failure_does_not_stop_the_rest(self):
        interface = MagicMock()
        interface.return_value.resolve.side_effect = [RuntimeError("pagerduty down"), None]
        _stub_module("incidentbot.pagerduty.api", "PagerDutyInterface", interface)

        settings = _make_settings(integrations=_integrations(pagerduty=True))
        with (
            patch.object(_status, "settings", settings),
            patch.object(_status, "IncidentDatabaseInterface") as db,
        ):
            db.list_pagerduty_incident_records.return_value = [
                SimpleNamespace(url="https://pd.example/incidents/PD1"),
                SimpleNamespace(url="https://pd.example/incidents/PD2"),
            ]
            _status._resolve_pagerduty_incidents(_make_incident())

        assert interface.return_value.resolve.call_count == 2
