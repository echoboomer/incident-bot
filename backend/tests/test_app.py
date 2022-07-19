import json
import time

from slack_sdk.signature import SignatureVerifier
from slack_sdk.web import WebClient

from slack_bolt.app import App
from slack_bolt.request import BoltRequest
from tests.mock_web_api_server import (
    setup_mock_web_api_server,
    cleanup_mock_web_api_server,
    assert_auth_test_count,
)
from typing import Any, Dict

placeholder_token = "verification-token"
placeholder_team_id = "T111"
placeholder_enterprise_id = "E111"
placeholder_app_id = "A111"


class TestBotSlackHandler:
    signing_secret = "secret"
    valid_token = "xoxb-valid"
    mock_api_server_base_url = "http://localhost:8888"
    signature_verifier = SignatureVerifier(signing_secret)
    web_client = WebClient(
        token=valid_token,
        base_url=mock_api_server_base_url,
    )

    def setup_method(self):
        setup_mock_web_api_server(self)

    def teardown_method(self):
        cleanup_mock_web_api_server(self)

    def generate_signature(self, body: str, timestamp: str):
        return self.signature_verifier.generate_signature(
            body=body,
            timestamp=timestamp,
        )

    def build_headers(self, timestamp: str, body: str):
        return {
            "content-type": ["application/json"],
            "x-slack-signature": [self.generate_signature(body, timestamp)],
            "x-slack-request-timestamp": [timestamp],
        }

    def build_request(self, event_payload: dict) -> BoltRequest:
        timestamp, body = str(int(time.time())), json.dumps(event_payload)
        return BoltRequest(body=body, headers=self.build_headers(timestamp, body))

    def test_message_handler(self):
        app = App(
            client=self.web_client,
            signing_secret=self.signing_secret,
        )

        result = {"call_count": 0}

        @app.message("Hi there!")
        def handle_messages(event, logger):
            logger.info(event)
            result["call_count"] = result["call_count"] + 1

        request = self.build_request(user_message_event_payload)
        response = app.dispatch(request)
        assert response.status == 200

        assert_auth_test_count(self, 1)
        time.sleep(1)  # wait a bit after auto ack()
        assert result["call_count"] == 1

    def test_event_handler(self):
        app = App(
            client=self.web_client,
            signing_secret=self.signing_secret,
        )

        result = {"call_count": 0}
        mentions = []

        @app.event("app_mention")
        def handle_mention(body, event, logger):
            logger.info(event)
            message = body["event"]["text"].split(" ")
            logger.debug(body)

            if "help" in message:
                result["call_count"] = result["call_count"] + 1
                mentions.append("help")
            elif "new" in message:
                result["call_count"] = result["call_count"] + 1
                mentions.append("new")
            elif "lsoi" in message:
                result["call_count"] = result["call_count"] + 1
                mentions.append("lsoi")
            elif "lsai" in message:
                result["call_count"] = result["call_count"] + 1
                mentions.append("lsai")
            elif "ls-sp-inc" in " ".join(message):
                result["call_count"] = result["call_count"] + 1
                mentions.append("ls-sp-inc")
            elif "scheduler" in message:
                result["call_count"] = result["call_count"] + 1
                mentions.append("scheduler")
            elif "tell me a joke" in " ".join(message):
                result["call_count"] = result["call_count"] + 1
                mentions.append("tell me a joke")
            elif "ping" in message:
                result["call_count"] = result["call_count"] + 1
                mentions.append("ping")
            elif "version" in message:
                result["call_count"] = result["call_count"] + 1
                mentions.append("version")
            else:
                result["call_count"] = result["call_count"] + 1
                mentions.append("other")

        calls = [
            "help",
            "new",
            "lsoi",
            "lsai",
            "ls-sp-inc",
            "scheduler",
            "tell me a joke",
            "ping",
            "version",
            "other",
        ]

        for call in calls:
            request = self.build_request(bot_mention_event_payload(call))
            response = app.dispatch(request)
            assert response.status == 200

        assert_auth_test_count(self, 1)
        time.sleep(1)  # wait a bit after auto ack()
        assert result["call_count"] == len(calls)
        assert mentions == calls

    # The mock API doesn't like reaction_added for some reason?
    # def test_reaction_added(self):
    #    app = App(
    #        client=self.web_client,
    #        signing_secret=self.signing_secret,
    #    )
    #
    #    result = {"call_count": 0, "reaction_added": ""}
    #
    #    @app.event("reaction_added")
    #    def reaction_added(event, logger):
    #        logger.info(event)
    #        emoji = event["reaction"]
    #        if emoji == "create-incident":
    #            result["call_count"] = result["call_count"] + 1
    #            result["reaction_added"] = emoji
    #
    #    request = self.build_request(reaction_added_event_payload)
    #    response = app.dispatch(request)
    #    assert response.status == 200
    #
    #    assert_auth_test_count(self, 1)
    #    time.sleep(1)  # wait a bit after auto ack()
    #    assert result["call_count"] == 1
    #    assert result["reaction_added"] == "create-incident"

    def test_action_handler(self):
        app = App(
            client=self.web_client,
            signing_secret=self.signing_secret,
        )

        result = {"call_count": 0}
        actions = []

        calls = [
            "incident.export_chat_logs",
            "incident.assign_role",
            "incident.claim_role",
            "incident.reload_status_message",
            "incident.set_incident_status",
            "incident.set_severity",
        ]

        for call in calls:

            @app.action(call)
            def handle_some_action(ack, event, logger):
                ack()
                logger.info(event)
                result["call_count"] = result["call_count"] + 1
                actions.append(call)

            request = self.build_request(bot_action_event_payload(call))
            response = app.dispatch(request)
            assert response.status == 200

        assert_auth_test_count(self, 1)
        time.sleep(1)  # wait a bit after auto ack()
        assert result["call_count"] == len(calls)
        assert actions == calls


"""
Mock Payloads
"""


def bot_action_event_payload(id: str) -> Dict[Any, Any]:
    return {
        "type": "block_actions",
        "actions": [
            {
                "type": "button",
                "action_id": id,
                "block_id": id,
                "action_ts": "111.222",
                "value": id,
            }
        ],
    }


def bot_mention_event_payload(text: str) -> Dict[Any, Any]:
    return {
        "token": placeholder_token,
        "team_id": placeholder_team_id,
        "api_app_id": placeholder_app_id,
        "event": {
            "type": "app_mention",
            "user": "U061F7AUR",
            "text": text,
            "ts": "1515449522.000016",
            "channel": "C0LAN2Q65",
            "event_ts": "1515449522000016",
        },
        "type": "event_callback",
        "event_id": "Ev0LAN670R",
        "event_time": 1515449522000016,
        "authed_users": ["U0LAN0Z89"],
    }


reaction_added_event_payload = {
    "token": placeholder_token,
    "team_id": placeholder_team_id,
    "enterprise_id": placeholder_enterprise_id,
    "api_app_id": placeholder_app_id,
    "type": "reaction_added",
    "user": "U024BE7LH",
    "reaction": "create-incident",
    "item_user": "U0G9QF9C6",
    "item": {"type": "message", "channel": "C0G9QF9GZ", "ts": "1360782400.498405"},
    "event_ts": "1360782804.083113",
}

user_message_event_payload = {
    "token": placeholder_token,
    "team_id": placeholder_team_id,
    "enterprise_id": placeholder_enterprise_id,
    "api_app_id": placeholder_app_id,
    "event": {
        "client_msg_id": "968c94da-c271-4f2a-8ec9-12a9985e5df4",
        "type": "message",
        "text": "Hi there! Thanks for sharing the info!",
        "user": "W111",
        "ts": "1610261659.001400",
        "team": "T111",
        "blocks": [
            {
                "type": "rich_text",
                "block_id": "bN8",
                "elements": [
                    {
                        "type": "rich_text_section",
                        "elements": [
                            {
                                "type": "text",
                                "text": "Hi there! Thanks for sharing the info!",
                            }
                        ],
                    }
                ],
            }
        ],
        "channel": "C111",
        "event_ts": "1610261659.001400",
        "channel_type": "channel",
    },
    "type": "event_callback",
    "event_id": "Ev111",
    "event_time": 1610261659,
    "authorizations": [
        {
            "enterprise_id": "E111",
            "team_id": "T111",
            "user_id": "W111",
            "is_bot": True,
            "is_enterprise_install": False,
        }
    ],
    "is_ext_shared_channel": False,
    "event_context": "1-message-T111-C111",
}
