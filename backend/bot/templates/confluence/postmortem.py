import uuid
from typing import TypedDict


default_template = """
<table data-layout="default" ac:local-id="{uuid}">
  <colgroup>
    <col style="width: 340.0px;" />
    <col style="width: 340.0px;" />
  </colgroup>
  <tbody>
    <tr>
      <td data-highlight-colour="#f4f5f7">
        <p><strong>Role</strong></p>
      </td>
      <td data-highlight-colour="#f4f5f7">
        <p><strong>Participants</strong></p>
      </td>
    </tr>
    <tr>
      <td>
        <p>Incident Commander</p>
      </td>
      <td>
        {incident_commander}
      </td>
    </tr>
    <tr>
      <td>
        <p>Contributors</p>
      </td>
      <td>
        <p>Tag other people that participated in the resolution of the incident here.</p>
      </td>
    </tr>
  </tbody>
</table>

<h2>Summary</h2>

<ac:structured-macro ac:name="info" ac:schema-version="1" ac:macro-id="{uuid}">
  <ac:rich-text-body>
    <p>This incident was classified as a <b>{severity}</b> incident.</p>
    <p>{severity_definition}</p>
  </ac:rich-text-body>
</ac:structured-macro>

<ac:structured-macro ac:name="note" ac:schema-version="1" ac:macro-id="{uuid}">
  <ac:rich-text-body>
    <p>A summary of the impact of this incident should go here.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h2>User Impact</h2>
<ac:structured-macro ac:name="note" ac:schema-version="1" ac:macro-id="{uuid}">
  <ac:rich-text-body>
    <p>Describe how this incident affected users. Summarize answers to these two questions:</p>
    <ul>
      <li>
        <p>Was the service from the point of view of the user running in a degraded state?</p>
      </li>
      <li>
        <p>What else?</p>
      </li>
    </ul>
    <p>Full details can be added to the incident description.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h1>Timeline</h1>
{timeline_table_html}

<h1>Incident Description</h1>
<ac:structured-macro ac:name="note" ac:schema-version="1" ac:macro-id="{uuid}">
  <ac:rich-text-body>
    <p>Longer description of the problem with screenshots/links to help readers understand the entire incident.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h1>Root Cause</h1>
<ac:structured-macro ac:name="note" ac:schema-version="1" ac:macro-id="{uuid}">
  <ac:rich-text-body>
    <p>Explain the root cause of the issue.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h1>Actions</h1>

<h2>Immediate Actions</h2>
<ac:structured-macro ac:name="note" ac:schema-version="1" ac:macro-id="{uuid}">
  <ac:rich-text-body>
    <p>Actions to mitigate the impact of the incident directly following declaration should be listed here.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h2>Preventive Actions</h2>
<ac:structured-macro ac:name="note" ac:schema-version="1" ac:macro-id="{uuid}">
  <ac:rich-text-body>
    <p>What can be implemented to avoid this condition in the future?</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h1>Pinned Messages</h1>
<ac:structured-macro ac:name="info" ac:schema-version="1" ac:macro-id="{uuid}">
  <ac:rich-text-body>
    <p>These messages were pinned during the incident by users in Slack.</p>
    <p>This information is useful for establishing the incident timeline and providing diagnostic data.</p>
  </ac:rich-text-body>
</ac:structured-macro>
{pinned_messages_html}
<ac:structured-macro ac:name="attachments" ac:schema-version="1" data-layout="wide"
  ac:local-id="{uuid}" ac:macro-id="{uuid}" />
"""


class PostmortemContext(TypedDict):
    incident_id: str
    incident_commander: str | None
    severity: str | None
    severity_definition: str | None
    timeline_table_html: str | None
    pinned_messages_html: str | None
    author: str | None
    incident_date: str | None
    postmortem_date: str | None
    roles_html: str | None
    description: str | None
    channel_link: str | None


class PostmortemTemplate:
    @staticmethod
    def template(
        context: PostmortemContext,
        template_body: str | None = None,
    ):
        template_body = template_body or default_template
        # For each {uuid} replace with a new uuid.uuid4()
        while "{uuid}" in template_body:
            template_body = template_body.replace(
                "{uuid}", str(uuid.uuid4()), 1
            )

        for k, v in context.items():
            if v is not None:
                template_body = template_body.replace(f"{{{k}}}", str(v))
        return template_body
