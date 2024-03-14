import datetime
import uuid
from bot.shared.tools import parse_timestamp
import config
from bot.slack.client import get_slack_user, slack_workspace_id

from bot.confluence.api import ConfluenceApi, logger
from bot.models.pg import IncidentLogging
from bot.templates.confluence.postmortem import (
    PostmortemContext,
    PostmortemTemplate,
)
from bot.exc import PostmortemException
from html import escape
from iblog import logger
from typing import Any


class IncidentPostmortem:
    def __init__(
        self,
        incident_id: str,
        incident_created_at: str,
        incident_description: str,
        severity: str,
        channel_id: str,
        channel_name: str,
        severity_definition: str,
        pinned_items: list[IncidentLogging],
        timeline: list[dict],
        roles: dict | None = None,
        confluence: ConfluenceApi | None = None,
    ) -> None:
        self.incident_id = incident_id
        self.incident_datetime = parse_timestamp(incident_created_at)
        self.incident_description = incident_description
        self.severity = severity
        self.severity_definition = severity_definition
        self.pinned_items = pinned_items
        self.timeline = timeline
        self.roles = roles or {}
        self.incident_commander = self.roles.get('incident_commander', 'Unknown')
        self.channel_id = channel_id
        self.channel_name = channel_name

        self.parent_page = (
            config.active.integrations.get("atlassian")
            .get("confluence")
            .get("parent")
        )
        self.space = (
            config.active.integrations.get("atlassian")
            .get("confluence")
            .get("space")
        )

        self.confluence = confluence or ConfluenceApi()
        self.exec = self.confluence.api

    def create(self) -> str:
        """
        Creates a starting postmortem page and returns the create page's URL
        """
        parent_page_id = self.exec.get_page_id(self.space, self.parent_page)
        logger.info(
            f"Creating postmortem {self.incident_id} in Confluence space {self.space} under parent {self.parent_page}..."
        )
        # Generate html for postmortem doc
        # Create postmortem doc
        if not self.exec.page_exists(space=self.space, title=self.parent_page):
            msg = (
                "Couldn't create postmortem page, does the parent page exist?"
            )
            logger.error(msg)
            raise PostmortemException(msg)
        try:
            context = self._generate_incident_context()
            title = self.__render_postmortem_title(context)
            body = self.__render_postmortem_html(
                context=context,
            )
            self.confluence.create_page(
                space=self.space,
                title=title,
                body=body,
                parent_id=parent_page_id,
                type="page",
                representation="storage",
                editor="v2",
                labels=["postmortem"],
            )
            created_page_id = self.exec.get_page_id(self.space, title)
            created_page_info = self.exec.get_page_by_id(
                page_id=created_page_id
            )
            url = (
                created_page_info["_links"]["base"]
                + created_page_info["_links"]["webui"]
            )
            # If there are images in pinned items
            # Add them as attachments
            if self.pinned_items:
                for item in self.pinned_items:
                    if item.img:
                        try:
                            logger.info(
                                f"Attaching pinned item image to {title}..."
                            )
                            # Attach content to postmortem document
                            self.exec.attach_content(
                                item.img,
                                name=item.title,
                                content_type=item.mimetype,
                                page_id=created_page_id,
                                space=config.active.integrations.get(
                                    "atlassian"
                                )
                                .get("confluence")
                                .get("space"),
                                comment=f"This item was pinned to the incident by {item.user} at {item.ts}.",
                            )
                        except Exception as error:
                            logger.error(
                                f"Error attaching file to {title}: {error}"
                            )
            return url
        except Exception as error:
            msg = "Something unexpected happened and we couldn't create the postmortem."
            logger.exception(msg)
            raise PostmortemException(msg) from error

    def __generate_pinned_messages(self) -> str:
        if not self.pinned_items:
            return "<p>No items were pinned for this incident.</p>"
        all_items_formatted = ""
        for item in self.pinned_items:
            if item.content:
                all_items_formatted += f"""
                <blockquote><p><strong>{item.user} @ {item.ts} - </strong> {escape(item.content)}</p></blockquote><p />
                """

        return all_items_formatted

    def __generate_timeline(self) -> str:
        if len(self.timeline) == 0:
            return """
    <tr>
        <td>
            <p></p>
        </td>
        <td>
            <p>No items were added to this incident's timeline.</p>
        </td>
    </tr>
    """
        all_items_formatted = ""
        self.timeline.sort(key=lambda x: x["ts"])
        for item in self.timeline:
            all_items_formatted += f"""
    <tr>
        <td>
            <p>{item["ts"]}</p>
        </td>
        <td>
            <p>{item["log"]}</p>
        </td>
    </tr>
    """
        # Boilerplate
        all_items_formatted += f"""
    <tr>
        <td>
            <p>&hellip;</p>
        </td>
        <td>
            <p>&hellip;</p>
        </td>
    </tr>
    """
        return all_items_formatted

    def __render_postmortem_html(
        self,
        context: PostmortemContext,
    ) -> str:
        """Renders HTML for use in Confluence documents"""
        template_id = (
            config.active.integrations.get("atlassian")
            .get("confluence")
            .get("postmortem_template_id")
        )
        template_body = (
            self.confluence.fetch_template(template_id)['body']
            if template_id
            else None
        )
        try:
            return PostmortemTemplate.template(
                context=context,
                template_body=template_body,
            )
        except Exception as error:
            msg = f"Error generating Confluence postmortem html: {error}"
            logger.error(msg)
            raise PostmortemException(msg) from error

    def __render_postmortem_title(
        self,
        context: PostmortemContext,
    ) -> str:
        """Renders HTML for use in Confluence documents"""
        template_id = (
            config.active.integrations.get("atlassian")
            .get("confluence")
            .get("postmortem_template_id")
        )
        if template_id:
            template_response = (
                self.confluence.fetch_template(template_id)
            )
            if template_response:
                template_title = template_response["name"]
        else:
            template_title = config.active.integrations.get("atlassian").get("confluence").get("postmortem_title")

        if not template_title:
            # defaulting to %Y-%m-%d - {incident_id}
            template_title = "{incident_date} - {incident_id}"

        for k, v in context.items():
            if v is not None:
                template_title = template_title.replace(f"{{{k}}}", str(v))
        return template_title

    def __generate_roles(self) -> str:
        html = ""
        if self.roles:
            for role, user in self.roles.items():
                confluence_user = self.convert_slack_name_to_confluence_html(user)
                html += f"<b>{role}</b>: {confluence_user} <br />"
        return html

    def convert_slack_name_to_confluence_html(self, user_name: str) -> str:
        """Converts a Slack username to a Confluence username reference"""
        user = get_slack_user(user_name)
        if user:
            user['email'] = 'chudood@gmail.com'
            confluence_account_id = self.confluence.get_user_id(name=user['real_name'], email=user['email'])
            if confluence_account_id:
                return f'<ac:link><ri:user ri:account-id="{confluence_account_id}"/></ac:link>'
            else:
                return f"{user['real_name']}"
        else:
            return user_name

    def _generate_incident_context(self) -> PostmortemContext:
        channel_link =  f'<b><a href="https://{slack_workspace_id}.slack.com/archives/{self.channel_id}">#{self.channel_name}</a></b>'

        incident_commander=self.convert_slack_name_to_confluence_html(self.incident_commander)
        print(incident_commander)

        context = PostmortemContext(
            incident_commander=incident_commander,
            severity=self.severity,
            severity_definition=self.severity_definition,
            timeline_table_html=self.__generate_timeline_table_html(),
            pinned_messages_html=self.__generate_pinned_messages(),
            incident_id=self.incident_id,
            # TODO: This should be whoever clicked the button to create the postmortem
            description=self.incident_description,
            author=incident_commander,
            postmortem_date=datetime.datetime.now().strftime("%Y-%m-%d"),
            roles_html=self.__generate_roles(),
            incident_date=self.incident_datetime.strftime("%Y-%m-%d"),
            channel_link=channel_link
        )
        return context

    def __generate_timeline_table_html(self) -> str:
        return f"""
        <table data-layout="default" ac:local-id="{uuid.uuid4()}">
        <colgroup>
            <col style="width: 340.0px;" />
            <col style="width: 340.0px;" />
        </colgroup>
        <tbody>
            <tr>
            <td data-highlight-colour="#f4f5f7">
                <p><strong>Time</strong></p>
            </td>
            <td data-highlight-colour="#f4f5f7">
                <p><strong>Event</strong></p>
            </td>
            </tr>
            {self.__generate_timeline()}
        </tbody>
        </table>
        """
