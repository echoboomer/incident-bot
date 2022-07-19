import config
import feedparser
import json
import logging
import requests

from bot.shared import tools
from datetime import datetime, timedelta
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ExternalProviderIncidents:
    """
    Retrieve and use incidents from external providers
    """

    def __init__(
        self,
        provider: str,
        slack_channel: str,
        days_back: int = 2,
        feed_type: str = "atom",
    ):
        self.provider = provider
        self.slack_channel = slack_channel
        self.days_back = days_back
        self.feed_type = feed_type
        self.provider_urls = {
            "auth0": f"https://status.auth0.com/feed?domain={config.auth0_domain}",
            "github": "https://www.githubstatus.com/history.atom",
            "heroku": "https://status.heroku.com/api/v4/current-status",
        }
        self.parsed_feed = feedparser.parse(self.provider_urls[self.provider.lower()])

    def matched(self) -> Dict[str, Any]:
        """
        Return incidents within the time delta window
        """
        if self.feed_type == "json":
            resp = requests.get(self.feed)
            resp_json = json.loads(resp.text)
            return resp_json
        else:
            matched = []
            for e in self.parsed_feed.entries:
                updated_ts = e["updated_parsed"]
                dt = datetime(*updated_ts[:6])
                delta = datetime.today() - timedelta(days=self.days_back)
                if dt > delta:
                    matched.append(e)
            return matched

    def slack_message(self) -> Dict[str, str]:
        blocks = [
            {"type": "divider"},
            {
                "block_id": "header",
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":gear: Recent {self.provider} Status Updates",
                },
            },
        ]
        if len(self.matched()) == 0:
            blocks.append(
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"No events in the last {self.days_back} days.",
                        },
                    ],
                }
            )
        else:
            for e in self.matched():
                title = e["title"]
                link = e["link"]
                updated = e["updated"]
                summary = e["summary"]
                blocks.append(
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"<{link}|{title}>",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Updated:* {updated}",
                            },
                        ],
                    }
                )
        blocks.append(
            {"type": "divider"},
        )
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":hourglass: Updated at {tools.fetch_timestamp()}",
                    },
                ],
            }
        )
        blocks.append(
            {"type": "divider"},
        )
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "external.reload",
                        "text": {"type": "plain_text", "text": "Reload"},
                        "style": "primary",
                        "value": self.provider,
                        "action_id": "incident.reload_status_message",
                    },
                    {
                        "type": "button",
                        "action_id": "external.view_status_page",
                        "text": {"type": "plain_text", "text": "Provider Status"},
                        "url": f"https://status.{self.provider}.com",
                    },
                ],
            },
        )
        return {
            "channel": self.slack_channel,
            "blocks": blocks,
        }
