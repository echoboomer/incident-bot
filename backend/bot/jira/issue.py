import config
import requests

from bot.jira.api import JiraApi, logger
from bot.models.incident import db_read_incident
from dataclasses import dataclass


@dataclass
class JiraIssue:
    def __init__(
        self,
        incident_id: str,
        description: str,
        issue_type: str,
        # priority: str,
        summary: str,
    ):
        self.jira = JiraApi()
        self.incident_id = incident_id
        self.incident_data = db_read_incident(incident_id=self.incident_id)

        self.description = description
        self.issue_type = issue_type
        self.labels = (
            config.active.integrations.get("atlassian")
            .get("jira")
            .get("labels")
        ) + [self.incident_data.channel_name]
        # self.priority = priority
        self.summary = summary

    def new(self):
        """Creates a Jira issue"""
        # priority_id = self.__get_priority_id(priority=self.priority)
        try:
            resp = self.jira.api.issue_create(
                fields={
                    "description": self.description,
                    "issuetype": {"name": self.issue_type},
                    "labels": self.labels,
                    # "priority": {"id": priority_id},
                    "project": {"id": self.jira.project_id},
                    "summary": self.summary,
                }
            )

            return resp
        except requests.exceptions.HTTPError as error:
            logger.error(f"Error creating Jira issue: {error}")

    def __get_priority_id(self, priority: str):
        """Returns a priority id by name"""
        try:
            resp = self.jira.priorities

            return next(
                (
                    prid
                    for prid in resp
                    if prid is not None and prid == priority.lower().title()
                ),
                None,
            )
        except requests.exceptions.HTTPError as error:
            logger.error(f"Error finding Jira priority ID: {error}")
