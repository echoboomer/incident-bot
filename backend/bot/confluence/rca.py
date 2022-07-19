import config
import datetime
import logging

from atlassian import Confluence
from bot.shared import tools
from typing import Any


logger = logging.getLogger(__name__)


confluence = Confluence(
    url=config.confluence_api_url,
    username=config.confluence_api_username,
    password=config.confluence_api_token,
    cloud=True,
)

today = datetime.datetime.today().strftime("%Y-%m-%d")


def create_rca(
    rca_title: str,
    incident_commander: str,
    technical_lead: str,
    severity: str,
    severity_definition: str,
    parent_page: str = config.confluence_parent_page,
    space: str = config.confluence_space,
):
    """
    Creates a starting RCA page and returns the create page's URL
    """
    title = f"{today} - {rca_title.title()}"
    parent_page_id = confluence.get_page_id(space, parent_page)
    logger.info(
        f"Creating RCA {title} in Confluence space {space} under parent {parent_page}..."
    )
    # Generate html for rca doc
    body = render_rca_html(
        incident_commander=incident_commander,
        technical_lead=technical_lead,
        severity=severity,
        severity_definition=severity_definition,
    )
    # Create rca doc
    if confluence.page_exists(space=space, title="RCAs"):
        try:
            confluence.create_page(
                space,
                title,
                body,
                parent_id=parent_page_id,
                type="page",
                representation="storage",
                editor="v2",
            )
            created_page_id = confluence.get_page_id(space, title)
            created_page_info = confluence.get_page_by_id(page_id=created_page_id)
            url = (
                created_page_info["_links"]["base"]
                + created_page_info["_links"]["webui"]
            )
            return url
        except Exception as error:
            logger.error(error)
    else:
        logger.error("Couldn't create RCA page, does the parent page exist?")


def find_user_id(user: str) -> tuple[bool, Any]:
    """
    Accepts the publicName of a user in Atlassian Cloud and returns the ID if it exists
    """
    groups = confluence.get_all_groups(start=0, limit=50)
    for g in groups:
        users = confluence.get_group_members(group_name=g["name"], start=0, limit=1000)
        for u in users:
            if user in u["publicName"]:
                return True, u["accountId"]
            else:
                pass
    return False, None


def render_rca_html(
    incident_commander: str,
    technical_lead: str,
    severity: str,
    severity_definition: str,
) -> str:
    """Renders HTML for use in Confluence documents"""
    variables = {
        "incident_commander": user_mention_format(incident_commander),
        "technical_lead": user_mention_format(technical_lead),
        "severity": severity.upper(),
        "severity_definition": severity_definition,
    }
    return tools.render_html(f"templates/confluence/rca.html", variables)


def user_mention_format(role: str) -> str:
    """
    Determines whether a user mention is a link or a string based on whether or
    not we could find the user ID
    """
    result = find_user_id(role)
    if result[0]:
        return f"""
            <ac:link>
                <ri:user ri:userkey="{result[1]}" />
            </ac:link>
        """
    else:
        return f"@{role}"
