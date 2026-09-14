"""
Tests for incidentbot/api/routes/widget.py
"""
import unittest
from unittest.mock import MagicMock, patch

# Pre-import fastapi so it stays in sys.modules after the patch.dict block
# exits.  FastAPI uses isinstance checks against its own classes at request
# time; if the module has been evicted from sys.modules the Header dependency
# silently resolves to None.
import fastapi  # noqa: F401
import fastapi.testclient  # noqa: F401

_mock_settings = MagicMock()
_mock_settings.IS_TEST_ENVIRONMENT = True
_mock_settings.DATABASE_URI = "sqlite:///:memory:"
_mock_settings.SLACK_BOT_TOKEN = "xoxb-test"
_mock_settings.LOG_LEVEL = "INFO"
_mock_settings.options.timezone = "UTC"
_mock_settings.SECRET_KEY = "test-secret-key-32-chars-minimum!"
_mock_settings.statuses = {
    "investigating": MagicMock(final=False, initial=True),
    "resolved": MagicMock(final=True, initial=False),
}
_mock_settings.roles = {
    "incident_commander": MagicMock(is_lead=True),
    "scribe": MagicMock(is_lead=False),
}

with (
    patch("incidentbot.configuration.settings.settings", _mock_settings),
    patch("sqlmodel.create_engine", return_value=MagicMock()),
    patch("slack_sdk.WebClient", return_value=MagicMock()),
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from incidentbot.api.routes.widget import router

_app = FastAPI()
_app.include_router(router)
client = TestClient(_app)

VALID_TOKEN = "valid.widget.token"
VALID_PAYLOAD = {"type": "widget", "room_id": "!room:example.com"}


def _make_incident(channel_id="!room:example.com", status="investigating", severity="sev2"):
    inc = MagicMock()
    inc.id = 1
    inc.channel_id = channel_id
    inc.channel_name = "inc-test"
    inc.slug = "inc-test"
    inc.status = status
    inc.severity = severity
    inc.description = "test"
    inc.has_private_channel = False
    inc.roles_all = ["incident_commander", "scribe"]
    inc.severities = ["sev1", "sev2", "sev3"]
    inc.statuses = ["investigating", "identified", "resolved"]
    inc.roles = {}
    return inc


def _mock_session(incident=None):
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    exec_mock = MagicMock()
    exec_mock.first.return_value = incident
    session.exec.return_value = exec_mock
    if incident:
        session.get.return_value = incident
    return session


# ── Token checking ────────────────────────────────────────────────────────────


class TestCheckToken:
    def test_missing_token_returns_403_on_api_route(self):
        resp = client.post("/widget/api/incident", json={
            "incident_description": "test",
            "severity": "sev2",
            "incident_components": "api",
        })
        self.assertEqual(resp.status_code, 403)

    def test_invalid_token_returns_403(self):
        with patch("incidentbot.api.routes.widget.verify_widget_token", side_effect=__import__("jwt").InvalidTokenError("bad")):
            resp = client.post(
                "/widget/api/incident",
                json={"incident_description": "t", "severity": "sev2", "incident_components": "api"},
                headers={"X-Widget-Token": "bad.token.here"},
            )
        self.assertEqual(resp.status_code, 403)

    def assertEqual(self, a, b):
        assert a == b, f"{a!r} != {b!r}"


# ── POST /widget/api/incident ─────────────────────────────────────────────────


class TestWidgetCreateIncident(unittest.TestCase):
    def test_creates_incident_with_valid_token(self):
        mock_incident = MagicMock()
        with (
            patch("incidentbot.api.routes.widget.verify_widget_token", return_value=VALID_PAYLOAD),
            patch("incidentbot.api.routes.widget.Incident") as mock_cls,
        ):
            mock_cls.return_value = mock_incident
            resp = client.post(
                "/widget/api/incident",
                json={
                    "incident_description": "Database is down",
                    "severity": "sev1",
                    "incident_components": "database",
                },
                headers={"X-Widget-Token": VALID_TOKEN},
            )

        self.assertEqual(resp.status_code, 201)
        mock_incident.start.assert_called_once()

    def test_returns_500_when_incident_start_raises(self):
        with (
            patch("incidentbot.api.routes.widget.verify_widget_token", return_value=VALID_PAYLOAD),
            patch("incidentbot.api.routes.widget.Incident") as mock_cls,
        ):
            mock_cls.return_value.start.side_effect = Exception("db error")
            resp = client.post(
                "/widget/api/incident",
                json={
                    "incident_description": "test",
                    "severity": "sev2",
                    "incident_components": "api",
                },
                headers={"X-Widget-Token": VALID_TOKEN},
            )

        self.assertEqual(resp.status_code, 500)

    def test_passes_security_flag(self):
        mock_incident = MagicMock()
        with (
            patch("incidentbot.api.routes.widget.verify_widget_token", return_value=VALID_PAYLOAD),
            patch("incidentbot.api.routes.widget.Incident") as mock_cls,
        ):
            mock_cls.return_value = mock_incident
            client.post(
                "/widget/api/incident",
                json={
                    "incident_description": "Security event",
                    "severity": "sev1",
                    "incident_components": "auth",
                    "is_security_incident": True,
                },
                headers={"X-Widget-Token": VALID_TOKEN},
            )

        call_kwargs = mock_cls.call_args[1]["params"]
        self.assertTrue(call_kwargs.is_security_incident)


# ── POST /widget/api/incident-room ────────────────────────────────────────────


class TestWidgetUpdateIncidentRoom(unittest.TestCase):
    def _post(self, body, session=None, apply_status_change=None, adapter=None):
        incident = _make_incident()
        ctx = _mock_session(incident) if session is None else session
        apply = apply_status_change or MagicMock(return_value=(incident, None))
        with (
            patch("incidentbot.api.routes.widget.verify_widget_token", return_value=VALID_PAYLOAD),
            patch("incidentbot.api.routes.widget.Session", return_value=ctx),
            patch("incidentbot.api.routes.widget.get_adapter", return_value=adapter or MagicMock()),
            patch("incidentbot.api.routes.widget.EventLogHandler"),
            patch("incidentbot.api.routes.widget.apply_status_change", apply),
            patch("incidentbot.api.routes.widget.settings", _mock_settings),
        ):
            return client.post(
                "/widget/api/incident-room",
                json=body,
                headers={"X-Widget-Token": VALID_TOKEN},
            )

    def test_join_role_returns_200(self):
        mock_adapter = MagicMock()
        mock_adapter.get_user_display_name.return_value = "alice"
        incident = _make_incident()
        session = _mock_session(incident)
        # Route calls exec().first() twice: once for the incident lookup, once
        # for the existing-participant check.  The first must return the incident;
        # the second must return None so the role assignment proceeds.
        session.exec.return_value.first.side_effect = [incident, None]

        with (
            patch("incidentbot.api.routes.widget.verify_widget_token", return_value=VALID_PAYLOAD),
            patch("incidentbot.api.routes.widget.Session", return_value=session),
            patch("incidentbot.api.routes.widget.get_adapter", return_value=mock_adapter),
            patch("incidentbot.api.routes.widget.EventLogHandler"),
            patch("incidentbot.api.routes.widget.settings", _mock_settings),
        ):
            resp = client.post(
                "/widget/api/incident-room",
                json={"action": "join_role", "role": "scribe", "user": "U001"},
                headers={"X-Widget-Token": VALID_TOKEN},
            )

        self.assertEqual(resp.status_code, 200)

    def test_join_role_missing_user_returns_400(self):
        resp = self._post({"action": "join_role", "role": "scribe"})
        self.assertEqual(resp.status_code, 400)

    def test_join_role_missing_role_returns_400(self):
        resp = self._post({"action": "join_role", "user": "U001"})
        self.assertEqual(resp.status_code, 400)

    def test_join_role_invalid_role_returns_400(self):
        resp = self._post({"action": "join_role", "role": "nonexistent_role", "user": "U001"})
        self.assertEqual(resp.status_code, 400)

    def test_set_severity_returns_200(self):
        resp = self._post({"action": "set_severity", "severity": "sev2"})
        self.assertEqual(resp.status_code, 200)

    def test_set_severity_invalid_value_returns_400(self):
        resp = self._post({"action": "set_severity", "severity": "invalid"})
        self.assertEqual(resp.status_code, 400)

    def test_set_status_returns_200(self):
        resp = self._post({"action": "set_status", "status": "identified"})
        self.assertEqual(resp.status_code, 200)

    def test_set_status_without_a_status_returns_400(self):
        resp = self._post({"action": "set_status"})
        self.assertEqual(resp.status_code, 400)

    def test_set_status_invalid_value_returns_400(self):
        resp = self._post({"action": "set_status", "status": "bogus"})
        self.assertEqual(resp.status_code, 400)

    def test_resolve_returns_200(self):
        resp = self._post({"action": "resolve"})
        self.assertEqual(resp.status_code, 200)

    def test_resolve_goes_through_apply_status_change(self):
        """Resolving from the widget must cancel the reminder jobs.

        The widget used to write incident.status straight to the session, which
        left the reminders firing until someone restarted the deployment.
        """
        apply = MagicMock(return_value=(_make_incident(status="resolved"), None))
        resp = self._post({"action": "resolve", "user": "@alice:example.com"}, apply_status_change=apply)

        self.assertEqual(resp.status_code, 200)
        apply.assert_called_once()
        self.assertEqual(apply.call_args[0][1], "resolved")
        self.assertEqual(apply.call_args[1]["user"], "@alice:example.com")

    def test_resolve_posts_the_postmortem_link_in_the_room(self):
        """Slack announces it, so the widget has to as well."""
        adapter = MagicMock()
        apply = MagicMock(
            return_value=(_make_incident(status="resolved"), "https://gitlab.example/-/issues/7")
        )
        resp = self._post({"action": "resolve"}, apply_status_change=apply, adapter=adapter)

        self.assertEqual(resp.status_code, 200)
        posted = [call.args[1] for call in adapter.send_text.call_args_list]
        self.assertIn("Postmortem: https://gitlab.example/-/issues/7", posted)

    def test_no_postmortem_means_one_message(self):
        adapter = MagicMock()
        self._post({"action": "resolve"}, adapter=adapter)
        self.assertEqual(adapter.send_text.call_count, 1)

    def test_set_status_goes_through_apply_status_change(self):
        apply = MagicMock(return_value=(_make_incident(status="identified"), None))
        resp = self._post({"action": "set_status", "status": "identified"}, apply_status_change=apply)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(apply.call_args[0][1], "identified")

    def test_404_when_incident_not_found(self):
        session = _mock_session(incident=None)
        with (
            patch("incidentbot.api.routes.widget.verify_widget_token", return_value=VALID_PAYLOAD),
            patch("incidentbot.api.routes.widget.Session", return_value=session),
            patch("incidentbot.api.routes.widget.get_adapter", return_value=MagicMock()),
        ):
            resp = client.post(
                "/widget/api/incident-room",
                json={"action": "resolve"},
                headers={"X-Widget-Token": VALID_TOKEN},
            )
        self.assertEqual(resp.status_code, 404)
