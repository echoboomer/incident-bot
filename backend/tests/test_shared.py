import datetime

from bot.shared import tools


class TestUtils:
    def test_fetch_timestamp(self):
        ts = tools.fetch_timestamp()
        assert len(ts) == 23
        time = datetime.datetime.strptime(ts, tools.timestamp_fmt)
        assert type(time) == datetime.datetime

    def test_find_index_in_list(self):
        index = tools.find_index_in_list(
            [
                {
                    "token": "verification-token",
                    "team_id": "T111",
                    "enterprise_id": "E111",
                    "api_app_id": "A111",
                    "event": {
                        "type": "message",
                        "subtype": "bot_message",
                        "text": "TEST 1",
                        "ts": "1610262363.001600",
                        "username": "classic-bot",
                        "bot_id": "B888",
                        "channel": "C111",
                        "event_ts": "1610262363.001600",
                        "channel_type": "channel",
                    },
                    "type": "event_callback",
                    "event_id": "Ev111",
                    "event_time": 1610262363,
                    "authorizations": [
                        {
                            "enterprise_id": "E111",
                            "team_id": "T111",
                            "user_id": "UB222",
                            "is_bot": True,
                            "is_enterprise_install": False,
                        }
                    ],
                    "is_ext_shared_channel": False,
                    "event_context": "1-message-T111-C111",
                },
                {
                    "token": "verification-token",
                    "team_id": "T111",
                    "enterprise_id": "E111",
                    "api_app_id": "A111",
                    "event": {
                        "type": "message",
                        "subtype": "bot_message",
                        "text": "TEST 2",
                        "ts": "1610262363.001600",
                        "username": "classic-bot",
                        "bot_id": "B888",
                        "channel": "C111",
                        "event_ts": "1610262363.001600",
                        "channel_type": "channel",
                    },
                    "type": "event_callback",
                    "event_id": "Ev222",
                    "event_time": 1610262363,
                    "authorizations": [
                        {
                            "enterprise_id": "E111",
                            "team_id": "T111",
                            "user_id": "UB222",
                            "is_bot": True,
                            "is_enterprise_install": False,
                        }
                    ],
                    "is_ext_shared_channel": False,
                    "event_context": "1-message-T111-C111",
                },
            ],
            "event_id",
            "Ev222",
        )
        assert index == 1

    def test_read_json_from_file(self):
        json_data = tools.read_json_from_file("tests/files/sample.json")
        assert json_data == {"sample_json": "somevalue"}

    def test_render_html(self):
        variables = {
            "foo": "Bar",
        }
        html = tools.render_html(f"tests/files/sample.html", variables)
        assert html == "<h1>Test Bar Page</h1>"

    def test_render_json(self):
        variables = {
            "foo": "bar",
        }
        json_data = tools.render_json(f"tests/files/sample2.json", variables)
        assert json_data == {"sample_json": "bar"}

    def test_validate_ip_address(self):
        is_ip = tools.validate_ip_address("127.0.0.1")
        assert is_ip == True

        is_ip = tools.validate_ip_address("300.0.0.2")
        assert is_ip == False
