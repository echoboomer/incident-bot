import config
import json
import logging
import requests

from bot.audit import log
from typing import Dict, List

logger = logging.getLogger(__name__)

api = "https://api.statuspage.io/v1/"
api_key = config.statuspage_api_key
page_id = config.statuspage_page_id

headers = {
    "Authorization": f"OAuth {api_key}",
}


class StatuspageIncident:
    """Instantiates a Statuspage incident"""

    def __init__(self, request_data: Dict[str, str]):
        """Creates a Statuspage incident

        Args:
            name: the title of the incident
            status: the initial status of the incident
            body: the description for the incident
        """
        self.request_data = request_data
        # Construct payload for request to API
        payload = {
            "incident": {
                "name": self.request_data["name"],
                "status": self.request_data["status"],
                "body": self.request_data["body"],
                "impact_override": self.request_data["impact"],
                "components": self.request_data["components"],
            }
        }
        resp = requests.post(
            f"{api}/pages/{page_id}/incidents", headers=headers, json=payload
        )
        json_response = json.loads(resp.text)
        incident_name = json_response["name"]
        logger.info(f"Created Statuspage incident: {incident_name}")
        self.info = json.loads(resp.text)

    def info(self) -> Dict[str, str]:
        return self.info


class StatuspageComponents:
    """Return and use Statuspage components"""

    def __init__(self) -> List[Dict[str, str]]:
        """Retrieves a list of components from the Statuspage API
        for the supplied page ID

        Returns Dict[str, str] containing the formatted message
        to be sent to Slack
        """
        components_raw = requests.get(
            f"{api}/pages/{page_id}/components",
            headers=headers,
        )
        self.resp = json.loads(components_raw.text)

    def list_of_names(self) -> List[str]:
        self.components = []
        for c in self.resp:
            self.components.append(c["name"])
        return self.components

    def list_of_dict_name_ids(self) -> List[Dict[str, str]]:
        self.components = []
        for c in self.resp:
            self.components.append({c["name"]: c["id"]})
        return self.components

    def formatted_components_update(
        self, selected_components: List[str], status: str
    ) -> List[str]:
        formatted_json = {}
        for dict in self.list_of_dict_name_ids():
            for sc in selected_components:
                if sc in dict:
                    for key, value in dict.items():
                        formatted_json[value] = status
        return formatted_json


class StatuspageObjects:
    """Return and use Statuspage objects"""

    def __init__(self) -> List[Dict[str, str]]:
        """Retrieves a list of components from the Statuspage API
        for the supplied page ID

        Returns Dict[str, str] containing the formatted message
        to be sent to Slack
        """
        incidents_raw = requests.get(
            f"{api}/pages/{page_id}/incidents",
            headers=headers,
        )
        self.open_incidents = json.loads(incidents_raw.text)

    def open_incidents(self) -> Dict[str, str]:
        return self.open_incidents


def update_sp_incident(update_data: Dict[str, str]) -> Dict[str, str]:
    """Updates a Statuspage incident

    Args:
        update_data: Dict[str, str] containing fields to update
    """
    # Retrieve ID from info
    id = update_data["id"]
    # Construct payload for request to API
    payload = {
        "incident": {
            "status": update_data["status"],
            "body": update_data["body"],
            "components": update_data["components"],
        }
    }
    resp = requests.patch(
        f"{api}/pages/{page_id}/incidents/{id}", headers=headers, json=payload
    )
    return json.loads(resp.text)
