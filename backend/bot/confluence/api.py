from functools import lru_cache
from typing import Literal
import requests
import atlassian.errors
import config

from atlassian import Confluence
from atlassian.errors import ApiPermissionError
from iblog import logger


class ConfluenceApi:
    def __init__(self, confluence: Confluence | None = None) -> None:
        self.confluence = confluence or Confluence(
            url=config.atlassian_api_url,
            username=config.atlassian_api_username,
            password=config.atlassian_api_token,
            cloud=True,
        )

    def fetch_template(self, template_id: int) -> dict | None:
        """Fetches the body of a Confluence template"""
        try:
            response = self.confluence.get_content_template(template_id)
        except atlassian.errors.ApiError as error:
            logger.error(f"Could not find template with id: {template_id}")
            return None
        except requests.HTTPError as error:
            logger.error(
                f"Error fetching template body from confluence: {error}"
            )
            return None
        return {
            "name": response['name'],
            "labels": [l['label'] for l in response.get('labels', [])],
            "body": response["body"]["storage"]["value"],
        }

    def create_page(
        self,
        space: str,
        title: str,
        body: str,
        parent_id: str | None = None,
        type: str = "page",
        representation: str = "storage",
        editor: str | None = None,
        full_width: bool = False,
        labels: list[str] | None = None,
        status: Literal["draft"] | None = None,
    ) -> dict:
        """
        Unfortunately the atlassian-python-api does not support creating pages
        with labels or any other advanced features. This method is a copy and paste with a few workarounds.
        """
        url = "rest/api/content/"
        data = {
            "type": type,
            "title": title,
            "status": status,
            "space": {"key": space},
            "body": self.api._create_body(body, representation),
            "metadata": {"properties": {}},
        }
        if parent_id:
            data["ancestors"] = [{"type": type, "id": parent_id}]
        if editor is not None and editor in ["v1", "v2"]:
            data["metadata"]["properties"]["editor"] = {"value": editor}
        if full_width is True:
            data["metadata"]["properties"]["content-appearance-draft"] = {
                "value": "full-width"
            }
            data["metadata"]["properties"]["content-appearance-published"] = {
                "value": "full-width"
            }
        else:
            data["metadata"]["properties"]["content-appearance-draft"] = {
                "value": "fixed-width"
            }
            data["metadata"]["properties"]["content-appearance-published"] = {
                "value": "fixed-width"
            }

        # https://community.atlassian.com/t5/Answers-Developer-Questions/Creating-a-confluence-page-via-rest-api-with-a-label/qaq-p/469849
        if labels:
            data["metadata"]["labels"] = [{"name": label} for label in labels]

        try:
            response = self.api.post(url, data=data)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                raise ApiPermissionError(
                    "The calling user does not have permission to view the content",
                    reason=e,
                )

            raise
        return response

    @property
    def api(self) -> Confluence:
        return self.confluence

    def test(self) -> bool:
        try:
            return self.confluence.page_exists(
                config.active.integrations.get("atlassian")
                .get("confluence")
                .get("space"),
                config.active.integrations.get("atlassian")
                .get("confluence")
                .get("parent"),
            )
        except Exception as error:
            logger.error(f"Error authenticating to Confluence: {error}")
            logger.error(
                "Please check Confluence configuration and try again."
            )
        return False


    @lru_cache
    def _fetch_users(self) -> list[dict]:
        """
        Fetches all users in the Atlassian Cloud instance

        This is cached but this is fine because this instance does not last forever.
        """
        groups = self.api.get_all_groups(start=0, limit=50)
        users = []
        for g in groups:
            users += self.api.get_group_members(
                group_name=g["name"], start=0, limit=1000
            )
        return users

    def get_user_id(self, name: str, email: str) -> int | None:
        """
        Finds the account id of a user by their public name or email
        """
        for user in self._fetch_users():
            if user["publicName"] == name or user["email"] == email:
                return user["accountId"]
        return None
