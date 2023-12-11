import json
import os
import sys
import yaml

from bot.exc import ConfigurationError
from cerberus import Validator
from dotenv import load_dotenv
from iblog import logger, log_level
from typing import Dict, List

__version__ = "v1.7.0"

# .env parse
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)


"""
Global Variables
"""
is_test_environment = os.getenv("TEST_ENVIRONMENT", default="false") in (
    "True",
    "true",
    True,
)


class Configuration:
    def __init__(self):
        self.filepath = (
            os.getenv("CONFIG_FILE_PATH", default="config.yaml")
            if not is_test_environment
            else "config-test.yaml"
        )
        with open(self.filepath, "r") as yamlfile:
            self.live = yaml.load(yamlfile, Loader=yaml.FullLoader)
        self.url_regex = "^(?:http(s)?:\/\/)?[\w.-]+(?:\.[\w\.-]+)+[\w\-\._~:/?#[\]@!\$&'\(\)\*\+,;=.]+"

    def validate(self):
        """Given a config supplied as dict[str, any], validate its
        fields.

        Returns bool indicating whether or not the service passes validation
        """
        schema = {
            "platform": {
                "required": True,
                "type": "string",
                "allowed": ["slack"],
                "empty": False,
            },
            "digest_channel": {
                "required": True,
                "type": "string",
                "empty": False,
            },
            "roles": {
                "required": True,
                "type": "dict",
                "keysrules": {
                    "type": "string",
                    "empty": False,
                },
                "valuesrules": {
                    "type": "string",
                    "empty": False,
                },
            },
            "severities": {
                "required": True,
                "type": "dict",
                "keysrules": {
                    "type": "string",
                    "empty": False,
                },
                "valuesrules": {
                    "type": "string",
                    "empty": False,
                },
            },
            "incident_reminders": {
                "required": False,
                "type": "dict",
                "schema": {
                    "qualifying_severities": {
                        "required": True,
                        "type": "list",
                        "schema": {"type": "string", "empty": False},
                    },
                    "rate": {
                        "required": True,
                        "type": "integer",
                    },
                },
            },
            "statuses": {
                "required": True,
                "type": "list",
                "schema": {"type": "string", "empty": False},
            },
            "options": {
                "required": True,
                "type": "dict",
                "schema": {
                    "auto_invite_groups": {
                        "required": True,
                        "type": "dict",
                        "schema": {
                            "enabled": {
                                "required": True,
                                "type": "boolean",
                                "empty": False,
                            },
                            "groups": {
                                "required": False,
                                "type": "list",
                                "empty": True,
                            },
                        },
                    },
                    "channel_topic": {
                        "required": True,
                        "type": "dict",
                        "empty": False,
                        "schema": {
                            "default": {
                                "required": True,
                                "type": "string",
                                "empty": False,
                            },
                            "set_to_meeting_link": {
                                "required": False,
                                "type": "boolean",
                            },
                        },
                    },
                    "conference_bridge_link": {
                        "required": False,
                        "type": "string",
                        "empty": True,
                        "regex": self.url_regex,
                    },
                    "create_from_reaction": {
                        "required": True,
                        "type": "dict",
                        "schema": {
                            "enabled": {
                                "required": True,
                                "type": "boolean",
                                "empty": False,
                            },
                            "reacji": {
                                "required": True,
                                "type": "string",
                                "empty": False,
                            },
                        },
                    },
                    "show_most_recent_incidents_app_home_limit": {
                        "required": False,
                        "type": "integer",
                    },
                    "skip_logs_for_user_agent": {
                        "required": False,
                        "type": "list",
                        "schema": {"type": "string"},
                    },
                    "timezone": {
                        "required": True,
                        "type": "string",
                        "empty": False,
                    },
                },
            },
            "integrations": {
                "required": False,
                "type": "dict",
                "schema": {
                    "atlassian": {
                        "required": False,
                        "type": "dict",
                        "schema": {
                            "confluence": {
                                "required": False,
                                "type": "dict",
                                "schema": {
                                    "auto_create_rca": {
                                        "required": True,
                                        "type": "boolean",
                                        "empty": False,
                                    },
                                    "space": {
                                        "required": True,
                                        "type": "string",
                                        "empty": False,
                                    },
                                    "parent": {
                                        "required": True,
                                        "type": "string",
                                        "empty": False,
                                    },
                                },
                            },
                            "jira": {
                                "required": False,
                                "type": "dict",
                                "schema": {
                                    "project": {
                                        "required": True,
                                        "type": "string",
                                        "empty": False,
                                    },
                                    "issue_types": {
                                        "required": False,
                                        "type": "list",
                                        "empty": False,
                                    },
                                    "priorities": {
                                        "required": False,
                                        "type": "list",
                                        "empty": False,
                                    },
                                    "labels": {
                                        "required": True,
                                        "type": "list",
                                        "empty": False,
                                    },
                                },
                            },
                            "opsgenie": {
                                "required": False,
                                "type": "dict",
                                "schema": {
                                    "team": {
                                        "required": True,
                                        "type": "string",
                                        "empty": False,
                                    },
                                },
                            },
                        },
                    },
                    "pagerduty": {
                        "required": False,
                        "type": "dict",
                    },
                    "statuspage": {
                        "required": False,
                        "type": "dict",
                        "schema": {
                            "url": {
                                "required": True,
                                "type": "string",
                                "empty": False,
                                "regex": self.url_regex,
                            },
                            "permissions": {
                                "required": False,
                                "type": "dict",
                                "schema": {
                                    "groups": {
                                        "required": False,
                                        "type": "list",
                                        "empty": True,
                                    },
                                },
                            },
                        },
                    },
                    "zoom": {
                        "required": False,
                        "type": "dict",
                        "schema": {
                            "auto_create_meeting": {
                                "required": True,
                                "type": "boolean",
                                "empty": False,
                            },
                        },
                    },
                    "google_meet": {
                        "required": False,
                        "type": "dict",
                        "schema": {
                            "auto_create_meeting": {
                                "required": True,
                                "type": "boolean",
                                "empty": False,
                            },
                        },
                    },
                },
            },
            "links": {
                "required": True,
                "type": "dict",
                "schema": {
                    "incident_guide": {
                        "required": True,
                        "type": "string",
                        "empty": False,
                        "regex": self.url_regex,
                    },
                    "incident_postmortems": {
                        "required": False,
                        "type": "string",
                        "empty": False,
                        "regex": self.url_regex,
                    },
                },
            },
        }
        v = Validator(schema)
        if not v.validate(self.live, schema):
            raise ConfigurationError(
                f"Application configuration has errors: {v.errors}"
            )

    @property
    def path(self) -> str:
        return self.filepath

    @property
    def all(self) -> Dict:
        return self.live

    @property
    def digest_channel(self) -> str:
        return self.live.get("digest_channel")

    @property
    def incident_reminders(self) -> Dict:
        return self.live.get("incident_reminders")

    @property
    def integrations(self) -> Dict:
        return self.live.get("integrations")

    @property
    def links(self) -> Dict:
        return self.live.get("links")

    @property
    def options(self) -> Dict:
        return self.live.get("options")

    @property
    def platform(self) -> str:
        return self.live.get("platform")

    @property
    def roles(self) -> Dict[str, str]:
        return self.live.get("roles")

    @property
    def severities(self) -> Dict[str, str]:
        return self.live.get("severities")

    @property
    def statuses(self) -> List:
        return self.live.get("statuses")


active = Configuration()
active.validate()

"""
Database Settings
"""
database_host = os.getenv("POSTGRES_HOST")
database_name = os.getenv("POSTGRES_DB")
database_password = os.getenv("POSTGRES_PASSWORD")
database_port = os.getenv("POSTGRES_PORT")
database_user = os.getenv("POSTGRES_USER")
database_url = f"postgresql://{database_user}:{database_password}@{database_host}:{database_port}/{database_name}"

"""
Slack
"""
slack_app_token = os.getenv("SLACK_APP_TOKEN")
slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
slack_user_token = os.getenv("SLACK_USER_TOKEN")

# For internal pagination when iterating over collections returned from Slack
slack_items_pagination_per_page = 5

# App home only shows 5 most recent incidents by default - this can be supplied and adjusted
# Note that setting it too high may cause errors due to limitations in the Slack API for blocks in messages
show_most_recent_incidents_app_home_limit = (
    active.options.get("show_most_recent_incidents_app_home_limit")
    if "show_most_recent_incidents_app_home_limit" in active.options
    else 5
)

"""
Statuspage Module
"""
statuspage_api_key = os.getenv("STATUSPAGE_API_KEY", default="")
statuspage_integration_enabled = os.getenv(
    "STATUSPAGE_INTEGRATION_ENABLED", default="false"
)
statuspage_page_id = os.getenv("STATUSPAGE_PAGE_ID", default="")
sp_logo_url = "https://i.imgur.com/v4xmF6u.png"

"""
Atlassian
"""
atlassian_api_url = os.getenv("ATLASSIAN_API_URL", default="")
atlassian_api_username = os.getenv("ATLASSIAN_API_USERNAME", default="")
atlassian_api_token = os.getenv("ATLASSIAN_API_TOKEN", default="")
atlassian_opsgenie_api_key = os.getenv(
    "ATLASSIAN_OPSGENIE_API_KEY", default=""
)
atlassian_opsgenie_api_team_integration_key = os.getenv(
    "ATLASSIAN_OPSGENIE_API_TEAM_INTEGRATION_KEY", default=""
)

"""
PagerDuty
"""
pagerduty_api_username = os.getenv("PAGERDUTY_API_USERNAME", default="")
pagerduty_api_token = os.getenv("PAGERDUTY_API_TOKEN", default="")

"""
External
"""
zoom_account_id = os.getenv("ZOOM_ACCOUNT_ID", default="")
zoom_client_id = os.getenv("ZOOM_CLIENT_ID", default="")
zoom_client_secret = os.getenv("ZOOM_CLIENT_SECRET", default="")

 google_client_id = os.getenv("GOOGLE_CLIENT_ID", default="")
 google_project_id = os.getenv("GOOGLE_PROJECT_ID", default="")
 google_auth_uri = os.getenv("GOOGLE_AUTH_URI", default="")
 google_token_uri = os.getenv("GOOGLE_TOKEN_URI", default="")
 google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", default="")
 google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", default="")

"""
Web Application
"""
default_admin_password = os.getenv("DEFAULT_WEB_ADMIN_PASSWORD")
flask_app_secret_key = os.getenv("FLASK_APP_SECRET_KEY")
flask_debug_mode = os.getenv("FLASK_DEBUG_MODE_ENABLED", default="false") in (
    "True",
    "true",
    True,
)
jwt_secret_key = os.getenv("JWT_SECRET_KEY")

"""
Helper Methods
"""


def env_check(required_envs: List[str]):
    """Check for the existence of required env vars

    Keyword arguments:
    required_envs -- List[str] containing vars to check
    """
    logger.info("Running env check...")
    for e in required_envs:
        if os.getenv(e) == "":
            logger.fatal(f"The environment variable {e} cannot be empty.")
            sys.exit(1)
    if active.options.get("auto_invite_groups").get("enabled"):
        if active.options.get("auto_invite_groups").get("groups") is None:
            logger.fatal(
                f"If enabling auto group invite, the groups field in config.yaml should be set."
            )
            sys.exit(1)
    if active.options.get("create_from_reaction"):
        if active.options.get("create_from_reaction").get("reacji") is None:
            logger.fatal(
                f"If enabling auto create via react, the reacji field in config.yaml should be set."
            )
            sys.exit(1)
    if "atlassian" in active.integrations:
        if "confluence" in active.integrations.get("atlassian"):
            for var in [
                "ATLASSIAN_API_URL",
                "ATLASSIAN_API_USERNAME",
                "ATLASSIAN_API_TOKEN",
            ]:
                if os.getenv(var) == "":
                    logger.fatal(
                        f"If enabling the Confluence integration to auto create an RCA, the {var} variable must be set."
                    )
                    sys.exit(1)
        if "jira" in active.integrations.get("atlassian"):
            for var in [
                "ATLASSIAN_API_URL",
                "ATLASSIAN_API_USERNAME",
                "ATLASSIAN_API_TOKEN",
            ]:
                if os.getenv(var) == "":
                    logger.fatal(
                        f"If enabling the Jira integration, the {var} variable must be set."
                    )
                    sys.exit(1)
        if "opsgenie" in active.integrations.get("atlassian"):
            if "pagerduty" in active.integrations:
                logger.fatal(f"PagerDuty cannot be enabled with Opsgenie.")
                sys.exit(1)
            if (
                active.integrations.get("atlassian")
                .get("opsgenie")
                .get("team")
            ):
                if (
                    os.getenv("ATLASSIAN_OPSGENIE_API_TEAM_INTEGRATION_KEY")
                    == ""
                ):
                    logger.fatal(
                        f"If enabling the Opsgenie integration and setting a team, you must provide the ATLASSIAN_OPSGENIE_API_TEAM_INTEGRATION_KEY environment variable."
                    )
                    sys.exit(1)
            else:
                if os.getenv("ATLASSIAN_OPSGENIE_API_KEY") == "":
                    logger.fatal(
                        f"If enabling the Opsgenie integration, you must provide the ATLASSIAN_OPSGENIE_API_KEY environment variable."
                    )
                    sys.exit(1)
    if "pagerduty" in active.integrations:
        if active.integrations.get(
            "atlassian"
        ) and "opsgenie" in active.integrations.get("atlassian"):
            logger.fatal(f"PagerDuty cannot be enabled with Opsgenie.")
            sys.exit(1)

        for var in [
            "PAGERDUTY_API_USERNAME",
            "PAGERDUTY_API_TOKEN",
        ]:
            if os.getenv(var) == "":
                logger.fatal(
                    f"If enabling the PagerDuty integration, the {var} variable must be set."
                )
                sys.exit(1)
    if "statuspage" in active.integrations:
        for var in [
            "STATUSPAGE_API_KEY",
            "STATUSPAGE_PAGE_ID",
            "STATUSPAGE_URL",
        ]:
            if os.getenv(var) == "":
                logger.fatal(
                    f"If enabling the Statuspage integration, the {var} variable must be set."
                )
                sys.exit(1)
    if "zoom" in active.integrations:
        for var in [
            "ZOOM_ACCOUNT_ID",
            "ZOOM_CLIENT_ID",
            "ZOOM_CLIENT_SECRET",
        ]:
            if os.getenv(var) == "":
                logger.fatal(
                    f"If enabling Zoom meeting auto-create, the {var} variable must be set."
                )
                sys.exit(1)
    if "google_meet" in active.integrations:
        for var in [
            "GOOGLE_CLIENT_ID",
            "GOOGLE_PROJECT_ID",
            "GOOGLE_AUTH_URI",
            "GOOGLE_TOKEN_URI",
            "GOOGLE_CLIENT_SECRET",
            "GOOGLE_REDIRECT_URI",
        ]:
            if os.getenv(var) == "":
                logger.fatal(
                    f"If enabling Google Meet meeting auto-create, the {var} variable must be set."
                )
                sys.exit(1)


def startup_message(workspace: str, wrap: bool = False) -> str:
    """
    Returns diagnostic info for startup or troubleshooting
    """
    msg = f"""
--------------------------------------------------------------------------------
                            incident bot {__version__}
--------------------------------------------------------------------------------
Core functionality:
    Database host:                      {database_host}
    Incidents digest channel:           {active.digest_channel}
    Slack workspace:                    {workspace}
    Logging level:                      {log_level}

Integrations Configuration:                           
{json.dumps(active.integrations, sort_keys=True, indent=4)}
--------------------------------------------------------------------------------
    """
    if wrap:
        return f"""
```
{msg}
```
        """
    else:
        return msg
