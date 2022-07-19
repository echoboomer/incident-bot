from typing import Any, Dict


class ActionParameters:
    """Builds parameters based on actions input"""

    def __init__(self, payload: str):
        self.payload = payload

    def actions(self) -> str:
        return self.payload["actions"][0]

    def channel_details(self) -> str:
        return self.payload["channel"]

    def message_details(self) -> str:
        return self.payload["message"]

    def user_details(self) -> str:
        return self.payload["user"]

    def state(self) -> str:
        return self.payload["state"]

    def parameters(self) -> Dict[str, Any]:
        self.parameters_payload = {
            "action_id": self.actions()["action_id"],
            "channel_id": self.channel_details()["id"],
            "channel_name": self.channel_details()["name"],
            "timestamp": self.message_details()["ts"],
            "user": self.user_details()["name"],
            "user_id": self.user_details()["id"],
        }
        return self.parameters_payload
