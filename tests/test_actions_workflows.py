"""
Tests for set_status, set_severity, join_incident_as_role, leave_incident_as_role
in incidentbot/incident/actions.py
"""
import asyncio
from unittest.mock import MagicMock, patch

_mock_settings = MagicMock()
_mock_settings.IS_TEST_ENVIRONMENT = True
_mock_settings.DATABASE_URI = "sqlite:///:memory:"
_mock_settings.SLACK_BOT_TOKEN = "xoxb-test"
_mock_settings.LOG_LEVEL = "INFO"
_mock_settings.options.timezone = "UTC"
_mock_settings.integrations = None
_mock_settings.statuses = {
    "investigating": MagicMock(final=False, initial=True),
    "resolved": MagicMock(final=True, initial=False),
}
_mock_settings.roles = {
    "incident_commander": MagicMock(is_lead=True, description="The IC."),
    "scribe": MagicMock(is_lead=False, description="The scribe."),
}

with (
    patch("incidentbot.configuration.settings.settings", _mock_settings),
    patch("sqlmodel.create_engine", return_value=MagicMock()),
    patch("slack_sdk.WebClient", return_value=MagicMock()),
):
    from incidentbot.incident.actions import (
        join_incident_as_role,
        leave_incident_as_role,
        set_severity,
        set_status,
    )
    from incidentbot.models.slack import User


def _make_incident(
    id=1,
    slug="inc-test",
    channel_id="C123",
    channel_name="inc-test",
    severity="sev2",
    status="investigating",
):
    inc = MagicMock()
    inc.id = id
    inc.slug = slug
    inc.channel_id = channel_id
    inc.channel_name = channel_name
    inc.severity = severity
    inc.status = status
    inc.description = "test incident"
    inc.components = "api"
    inc.impact = "high"
    inc.has_private_channel = False
    inc.meeting_link = None
    inc.digest_message_ts = "ts-digest"
    return inc


def _make_user(id="U001", name="alice"):
    user = MagicMock(spec=User)
    user.id = id
    user.name = name
    return user


# ── set_severity ──────────────────────────────────────────────────────────────


class TestSetSeverity:
    def test_updates_db_and_posts_messages(self):
        incident = _make_incident()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.update_col") as mock_update,
            patch("incidentbot.incident.actions.EventLogHandler.create") as mock_event,
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
            patch("incidentbot.incident.actions.get_digest_channel_id", return_value="C-digest"),
            patch("incidentbot.incident.actions.run_automations"),
            patch("incidentbot.incident.actions._get_channel_topic", return_value=["Severity: SEV2", "Status: Investigating"]),
        ):
            asyncio.run(set_severity("C123", "sev1", "api"))

        mock_update.assert_called_once_with(
            channel_id="C123", col_name="severity", value="sev1"
        )
        mock_event.assert_called_once()

    def test_early_return_when_severity_unchanged_for_human(self):
        incident = _make_incident(severity="sev2")
        user = _make_user()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.update_col") as mock_update,
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
        ):
            asyncio.run(set_severity("C123", "sev2", user))

        mock_update.assert_not_called()

    def test_fires_on_severity_change_automation(self):
        incident = _make_incident()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.update_col"),
            patch("incidentbot.incident.actions.EventLogHandler.create"),
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
            patch("incidentbot.incident.actions.get_digest_channel_id", return_value="C-digest"),
            patch("incidentbot.incident.actions.run_automations") as mock_auto,
            patch("incidentbot.incident.actions._get_channel_topic", return_value=["Severity: SEV2", "Status: Investigating"]),
        ):
            asyncio.run(set_severity("C123", "sev1", "api"))

        mock_auto.assert_called_once_with("on_severity_change", incident)

    def test_posts_error_when_incident_not_found(self):
        mock_client = MagicMock()
        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=None),
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
        ):
            asyncio.run(set_severity("C-unknown", "sev1", "api"))
        mock_client.chat_postMessage.assert_called_once()


# ── set_status ────────────────────────────────────────────────────────────────


class TestSetStatus:
    def test_delegates_the_status_change_and_posts_messages(self):
        """Slack owns the messages; the rest goes through apply_status_change.

        That shared function is what cancels the reminder jobs, so every
        platform gets the same behaviour. See tests/test_incident_status.py.
        """
        incident = _make_incident()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.apply_status_change", return_value=(incident, None)) as mock_apply,
            patch("incidentbot.incident.actions.is_final", return_value=False),
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
            patch("incidentbot.incident.actions.get_digest_channel_id", return_value="C-digest"),
            patch("incidentbot.incident.actions._get_channel_topic", return_value=["Severity: SEV2", "Status: Investigating"]),
        ):
            asyncio.run(set_status("C123", "identified", "api"))

        mock_apply.assert_called_once_with(incident, "identified")
        mock_client.chat_postMessage.assert_called()

    def test_early_return_when_status_unchanged_for_human(self):
        incident = _make_incident(status="investigating")
        user = _make_user()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.update_col") as mock_update,
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
        ):
            asyncio.run(set_status("C123", "investigating", user))

        mock_update.assert_not_called()

    def test_an_api_call_for_the_current_status_announces_nothing(self):
        """Nothing changed, so the room should not be told that it did."""
        incident = _make_incident(status="resolved")
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.apply_status_change") as mock_apply,
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
        ):
            asyncio.run(set_status("C123", "resolved", "api"))

        mock_apply.assert_not_called()
        mock_client.chat_postMessage.assert_not_called()

    def test_posts_the_resolution_message_on_a_final_status(self):
        incident = _make_incident()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.apply_status_change", return_value=(incident, None)) as mock_apply,
            patch("incidentbot.incident.actions.is_final", return_value=True),
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
            patch("incidentbot.incident.actions.get_digest_channel_id", return_value="C-digest"),
            patch("incidentbot.incident.actions.BlockBuilder.resolution_message", return_value={"channel": "C123"}) as mock_resolution,
            patch("incidentbot.incident.actions._get_channel_topic", return_value=["Severity: SEV2", "Status: Investigating"]),
        ):
            asyncio.run(set_status("C123", "resolved", "api"))

        mock_apply.assert_called_once_with(incident, "resolved")
        mock_resolution.assert_called_once()

    def test_posts_error_when_incident_not_found(self):
        mock_client = MagicMock()
        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=None),
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
        ):
            asyncio.run(set_status("C-unknown", "resolved", "api"))
        mock_client.chat_postMessage.assert_called_once()


# ── join_incident_as_role ─────────────────────────────────────────────────────


class TestJoinIncidentAsRole:
    def test_associates_role_and_logs_event(self):
        incident = _make_incident()
        user = _make_user()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.check_role_assigned_to_user", return_value=False),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.associate_role") as mock_assoc,
            patch("incidentbot.incident.actions.EventLogHandler.create") as mock_event,
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
            patch("incidentbot.incident.actions._refresh_roles_panel"),
            patch("incidentbot.incident.actions._get_channel_topic", return_value=["Severity: SEV2", "Status: Investigating"]),
        ):
            asyncio.run(join_incident_as_role("C123", "scribe", user))

        mock_assoc.assert_called_once()
        mock_event.assert_called_once()

    def test_ephemeral_when_already_assigned(self):
        incident = _make_incident()
        user = _make_user()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.check_role_assigned_to_user", return_value=True),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.associate_role") as mock_assoc,
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
        ):
            asyncio.run(join_incident_as_role("C123", "scribe", user))

        mock_assoc.assert_not_called()
        mock_client.chat_postEphemeral.assert_called_once()

    def test_sets_topic_for_lead_role(self):
        incident = _make_incident()
        user = _make_user()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.check_role_assigned_to_user", return_value=False),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.associate_role"),
            patch("incidentbot.incident.actions.EventLogHandler.create"),
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
            patch("incidentbot.incident.actions._refresh_roles_panel"),
            patch("incidentbot.incident.actions._get_channel_topic", return_value=["Severity: SEV2", "Status: Investigating"]),
        ):
            asyncio.run(join_incident_as_role("C123", "incident_commander", user))

        mock_client.conversations_setTopic.assert_called_once()

    def test_does_not_set_topic_for_non_lead_role(self):
        incident = _make_incident()
        user = _make_user()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.check_role_assigned_to_user", return_value=False),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.associate_role"),
            patch("incidentbot.incident.actions.EventLogHandler.create"),
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
            patch("incidentbot.incident.actions._refresh_roles_panel"),
        ):
            asyncio.run(join_incident_as_role("C123", "scribe", user))

        mock_client.conversations_setTopic.assert_not_called()


# ── leave_incident_as_role ────────────────────────────────────────────────────


class TestLeaveIncidentAsRole:
    def test_removes_role_when_assigned(self):
        incident = _make_incident()
        user = _make_user()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.check_role_assigned_to_user", return_value=True),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.remove_role") as mock_remove,
            patch("incidentbot.incident.actions.EventLogHandler.create"),
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
            patch("incidentbot.incident.actions._refresh_roles_panel"),
            patch("incidentbot.incident.actions._get_channel_topic", return_value=["Severity: SEV2", "Status: Investigating"]),
        ):
            asyncio.run(leave_incident_as_role("C123", "scribe", user))

        mock_remove.assert_called_once()

    def test_early_return_when_not_assigned(self):
        incident = _make_incident()
        user = _make_user()
        mock_client = MagicMock()

        with (
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.get_one", return_value=incident),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.check_role_assigned_to_user", return_value=False),
            patch("incidentbot.incident.actions.IncidentDatabaseInterface.remove_role") as mock_remove,
            patch("incidentbot.incident.actions.slack_web_client", mock_client),
        ):
            asyncio.run(leave_incident_as_role("C123", "scribe", user))

        mock_remove.assert_not_called()
