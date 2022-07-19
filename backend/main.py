import config
import logging
import logging.config
import sys

from flask import Flask, request
from bot.db import db
from bot.scheduler import scheduler
from bot.shared import tools
from bot.slack.handler import app as slack_app
from slack_bolt.adapter.socket_mode import SocketModeHandler
from waitress import serve

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=config.log_level)

"""
Check for required environment variables first
"""

if __name__ == "__main__":
    # Pre-flight checks
    ## Check for environment variables
    config.env_check(
        required_envs=[
            "INCIDENTS_DIGEST_CHANNEL",
            "INCIDENT_GUIDE_LINK",
            "INCIDENT_POSTMORTEMS_LINK",
            "INCIDENT_CHANNEL_TOPIC",
            "SLACK_APP_TOKEN",
            "SLACK_BOT_TOKEN",
            "SLACK_WORKSPACE_ID",
            "POSTGRES_WRITER_HOST",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_PORT",
        ]
    )
    ## Make sure templates directory exists and all templates are present
    config.slack_template_check(
        required_templates=[
            "incident_channel_boilerplate.json",
            "incident_digest_notification_update.json",
            "incident_digest_notification.json",
            "incident_public_status_update.json",
            "incident_resolution_message.json",
            "incident_role_update.json",
            "incident_severity_update.json",
            "incident_status_update.json",
            "incident_user_role_dm.json",
            "role_definitions.json",
            "severity_levels.json",
        ]
    )

"""
Scheduler
"""

scheduler.process.start()

"""
Flask
"""

flask_app = Flask(__name__, static_folder="./app/static", template_folder="./app")


@flask_app.after_request
def webserver_logging(response):
    logger.info(
        '{} [{}] "{} {}" - {} - {} {}'.format(
            request.headers["host"],
            tools.fetch_timestamp(short=True),
            request.method,
            request.path,
            request.headers["user_agent"],
            request.environ.get("SERVER_PROTOCOL"),
            response.status,
        )
    )
    return response


@flask_app.route("/health", methods=["GET"])
def health():
    return {"status": "healthy"}


if config.web_interface_enabled == "true":
    import bot.web.routes

"""
Startup
"""


def db_check():
    logger.info("Testing the database connection...")
    db_info = f"""
------------------------------
Database host:  {config.database_host}
Database port:  {config.database_port}
Database user:  {config.database_user}
Database name:  {config.database_name}
------------------------------
    """
    print(db_info)
    if not db.db_verify():
        logger.fatal("Cannot connect to the database - check settings and try again.")
        exit(1)


if __name__ == "__main__":
    ## Make sure database connection works
    db_check()

    ## Startup splash for confirming key options
    startup_message = config.startup_message()
    print(startup_message)

    # Serve Slack Bolt app
    handler = SocketModeHandler(slack_app, config.slack_app_token)
    handler.connect()

    # Serve Flask app
    serve(flask_app, host="0.0.0.0", port=3000)
