import datetime
import uuid

from bot.shared import tools
from bot.confluence.postmortem import IncidentPostmortem
from bot.templates.confluence.postmortem import PostmortemTemplate


class TestPostMortem:
    def test_template_replacement_uuid(self):
        template_body = "{uuid}"

        result = PostmortemTemplate.template(
            incident_commander="",
            severity="",
            severity_definition="",
            timeline="",
            pinned_messages="",
            template_body=template_body,
        )

        assert uuid.UUID(result), "{uuid} was not replaced with a valid UUID"

    def test_template_replaces_each_uuid_with_unique_uuid(self):
        template_body = "{uuid}\n{uuid}"

        result = PostmortemTemplate.template(
            incident_commander="",
            severity="",
            severity_definition="",
            timeline="",
            pinned_messages="",
            template_body=template_body,
        )

        assert (
            result.split()[0] != result.split()[1]
        ), "{uuid} was not replaced with a unique UUID"

    def test_default_template(self):
        result = PostmortemTemplate.template(
            incident_commander="INCIDENT_COMMANDER",
            severity="SEV1",
            severity_definition="SEV1_DESCRIPTION",
            timeline="TIMELINE",
            pinned_messages="PINNED_MESSAGES",
        )

        assert "INCIDENT_COMMANDER" in result
        assert "SEV1" in result
        assert "SEV1_DESCRIPTION" in result
        assert "PINNED_MESSAGES" in result
        assert "TIMELINE" in result
