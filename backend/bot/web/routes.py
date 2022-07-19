import config
import flask_login
import json
import logging

from __main__ import flask_app as app
from bot.audit import log
from bot.db import db
from bot.incident import incident, actions as inc_actions
from bot.scheduler import scheduler
from bot.slack.client import store_slack_user_list
from datetime import timedelta
from flask import redirect, render_template, request, Response
from flask_cors import CORS
from flask_jwt_extended import jwt_required
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from urllib.parse import urlparse, urljoin
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)

"""
Flask
"""

# JWT Configuration

cors = CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})
app.config["CORS_HEADERS"] = "Content-Type"
app.config["JWT_SECRET_KEY"] = config.jwt_secret_key
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=8)

# Rate Limiter

limiter = Limiter(
    app,
    key_func=get_remote_address,
)


@app.before_request
def basic_authentication():
    if request.method.lower() == "options":
        return Response()


@app.route("/")
def redirect_root():
    return redirect("/app")


@app.route("/app", defaults={"path": ""})
@app.route("/app/<path:path>")
def catch_all(path):
    return render_template("index.html")


@app.errorhandler(429)
def ratelimit_handler(e):
    return (
        json.dumps(
            {"success": False, "error": "ratelimit exceeded %s" % e.description}
        ),
        429,
        {"ContentType": "application/json"},
    )


"""
Web application routes
"""
signups_enabled = False


@app.route("/api/incidents", methods=["GET"])
def incidents():
    try:
        incidents = db.db_read_all_incidents(return_json=True)
        return json.dumps({"data": incidents}), 200, {"ContentType": "application/json"}
    except Exception as error:
        return (
            json.dumps({"success": False, "error": str(error)}),
            500,
            {"ContentType": "application/json"},
        )


@app.route("/api/incidents", methods=["POST"])
def create_incident_post():
    try:
        data = request.json
        description = data["description"]
        user = data["user"]
        request_parameters = {
            "channel": "web",
            "channel_description": description,
            "descriptor": description,
            "user": user,
            "created_from_web": True,
        }
        # Create an incident based on the message using the internal path
        try:
            incident.create_incident(
                internal=False, request_parameters=request_parameters
            )
            return (
                json.dumps({"success": True}),
                200,
                {"ContentType": "application/json"},
            )
        except Exception as error:
            logger.error(f"Error when trying to create an incident: {error}")
            return (
                json.dumps({"success": False, "error": str(error)}),
                500,
                {"ContentType": "application/json"},
            )
    except Exception as error:
        return (
            json.dumps({"success": False, "error": str(error)}),
            500,
            {"ContentType": "application/json"},
        )


@app.route("/api/incidents/<incident_id>", methods=["GET"])
def single_incident(incident_id):
    try:
        incident = db.db_read_incident(incident_id=incident_id, return_json=True)
        return (
            json.dumps({"data": incident}),
            200,
            {"ContentType": "application/json"},
        )
    except Exception as error:
        return (
            json.dumps({"success": False, "error": str(error)}),
            500,
            {"ContentType": "application/json"},
        )


@app.route("/api/incidents/<incident_id>/audit", methods=["GET"])
def read_audit_log(incident_id):
    try:
        audit_logs = log.read(incident_id)
        return (
            json.dumps({"data": audit_logs}),
            200,
            {"ContentType": "application/json"},
        )
    except Exception as error:
        return (
            json.dumps({"success": False, "error": str(error)}),
            500,
            {"ContentType": "application/json"},
        )


@app.route("/api/incidents/<incident_id>/role", methods=["POST"])
def set_incident_role(incident_id):
    try:
        request_data = request.json
        int_request_data = {
            "incident_id": incident_id,
            "channel_id": request_data["channel_id"],
            "role": request_data["role"],
            "bp_message_ts": request_data["bp_message_ts"],
            "user": request_data["user"],
        }
        inc_actions.assign_role(web_data=int_request_data, request_origin="web")
        return (
            json.dumps({"success": True}),
            200,
            {"ContentType": "application/json"},
        )
    except Exception as error:
        return (
            json.dumps({"success": False, "error": str(error)}),
            500,
            {"ContentType": "application/json"},
        )


@app.route("/api/incidents/slack_users", methods=["GET"])
def list_slack_users():
    try:
        data = (
            db.Session.query(db.OperationalData)
            .filter(db.OperationalData.id == "slack_users")
            .one()
            .serialize()
        )
        return (
            json.dumps({"data": data["json_data"]}),
            200,
            {"ContentType": "application/json"},
        )
    except Exception as error:
        return (
            json.dumps({"success": False, "error": str(error)}),
            500,
            {"ContentType": "application/json"},
        )


@app.route("/api/jobs", methods=["GET"])
def return_jobs():
    try:
        jobs = scheduler.process.list_jobs()
        job_details = []
        for j in jobs:
            job_details.append(
                {
                    "id": j.id,
                    "name": j.name,
                    "function": j.func_ref,
                    "trigger": str(j.trigger),
                    "next_run": str(j.next_run_time),
                }
            )
        return (
            json.dumps(job_details),
            200,
            {"ContentType": "application/json"},
        )
    except Exception as error:
        return (
            json.dumps({"success": False, "error": str(error)}),
            500,
            {"ContentType": "application/json"},
        )


@app.route("/api/jobs/run", methods=["POST"])
def run_job():
    try:
        request_data = request.json
        if request.json == None:
            return (
                json.dumps({"success": False, "error": "must provide job_id"}),
                500,
                {"ContentType": "application/json"},
            )
        job_id = request_data["job_id"]
        if job_id == "update_pagerduty_oc_data":
            if config.pagerduty_features_enabled == "true":
                from bot.pagerduty import api as pd_api

                try:
                    pd_api.store_on_call_data()
                    return (
                        json.dumps({"success": True}),
                        200,
                        {"ContentType": "application/json"},
                    )
                except Exception as error:
                    return (
                        json.dumps({"success": False, "error": str(error)}),
                        500,
                        {"ContentType": "application/json"},
                    )
            else:
                return (
                    json.dumps(
                        {"success": False, "error": "pagerduty integration not enabled"}
                    ),
                    500,
                    {"ContentType": "application/json"},
                )
        elif job_id == "update_slack_user_list":
            try:
                store_slack_user_list()
                return (
                    json.dumps({"success": True}),
                    200,
                    {"ContentType": "application/json"},
                )
            except Exception as error:
                return (
                    json.dumps({"success": False, "error": str(error)}),
                    500,
                    {"ContentType": "application/json"},
                )
        return (
            json.dumps({"success": False, "error": "job does not exist"}),
            500,
            {"ContentType": "application/json"},
        )
    except Exception as error:
        return (
            json.dumps({"success": False, "error": str(error)}),
            500,
            {"ContentType": "application/json"},
        )


@app.route("/api/pager", methods=["GET"])
def return_pager():
    try:
        data = (
            db.Session.query(db.OperationalData)
            .filter(db.OperationalData.id == "pagerduty_oc_data")
            .one()
            .serialize()
        )
        return (
            json.dumps({"data": data["json_data"], "ts": data["updated_at"]}),
            200,
            {"ContentType": "application/json"},
        )
    except Exception as error:
        return (
            json.dumps({"success": False, "error": str(error)}),
            500,
            {"ContentType": "application/json"},
        )
