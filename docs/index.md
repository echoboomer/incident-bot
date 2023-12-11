# Incident Bot Docs

Incident Bot is an incident management ChatOps bot for Slack to allow your teams to easily and effectively identify and manage technical incidents impacting your cloud infrastructure, your products, or your customers' ability to use your applications and services.

Interacting with the bot is incredibly easy through the use of modals and simplified commands.

!!! note

    We are looking to add support to other platforms in the future.

Need support or just want to chat with us? Join us on [Discord](https://discord.gg/PzqSQUY88c).

## Features at a Glance

- Create a war-room in Slack to gather resources and handle incidents.
- A fully functioning digest channel that stays up to date with incident statuses that can be used by others to watch the status of incidents. Incident statuses are updated there in real time.
- Define your own roles, severities, and statuses. There are some provided out of the box, but you can control them.
- The ability to send out internal status updates that will be viewable in the incident digest channel.
- Automatically generate unique Zoom or Google Meet meetings for each incident and tell everyone about them.
- Create Statuspage incidents.
- Page teams in PagerDuty.
- Automatically create an RCA/postmortem document in Confluence.
- Create issues in Jira related to an incident.
- Notify participants when they are assigned a role.
- Automatically generate and manage a timeline of events.

### Additional Features

#### Automation

The following features are implemented to assist with managing incidents:

- If the bot sees messages being sent in the incidents digest channel, it will drop in a message encouraging users to open an incident. This helps to prevent hesitation in declaring and running incidents.

#### Automatic Timeline Generation

There is a section in the postmortem documentation that holds timeline information for the incident. The application will automatically added many of these events, such as:

- Status changes
- Severity changes
- User role assignments
- Postmortem doc creation

You are also able to add your own events to the timeline by using the application's `Manage incident timeline` shortcut searchable as a slash command or in the Slack search bar. This modal will show you all current timeline events and then allow you to add more.

These will automatically be populated in the table and added to the postmortem document when the incident is resolved.

#### Pinning Items

In any incident channel, you can use the `pushpin` emote in Slack to attach messages to the incident. This are viewable in the web UI where you can optionally delete them if you no longer want them. These are automatically added to the postmortem document when the incident is resolved. You can attach the following items:

- Messages - these are timestamped and added to the RCA showing which user sent the message
- Images - these are added to the RCA as attachments - note that if an image is attached with a message, only the image is attached to the incident

#### Scheduled Actions

By default, the app will look for incidents that are not resolved that are older than 7 days. You may adjust this behavior via the scheduler module if you wish.

#### Security Incidents

When you create a channel via the modal, you have the option to mark an incident as security-related. If selecting this option, the created channel will be private.

This will flag the incident as a security incident in the digest channel. There will also be an alert in the channel letting users know the incident is security-related.

## Integrations

For more information on integrations, check out the [integrations](/integrations/) documentation.

## Quick Start

- [Create a Slack app](https://api.slack.com/apps?new_app=1) for this application. You can name it whatever you'd like, but `incident-bot` seems to make the most sense.
- Select `from an app manifest` and copy `manifest.yaml` out of this repository and paste it in to automatically configure the app.
- You'll need the app token, bot token, and user token for your application and provide those as `SLACK_APP_TOKEN`, `SLACK_BOT_TOKEN`, and `SLACK_USER_TOKEN` - these can be found within the app's configuration page in Slack.
- You'll need a Postgres instance to connect to.
- Create a channel to serve as your incident "digest" channel - something like `#incidents`.
- Configure the app using `config.yaml` and deploy it to Kubernetes, Docker, or whichever platform you choose. Check out the [setup](/setup/) guide for more details.

## Testing

Tests will run on each pull request and merge to the primary branch. To run them locally:

```bash
make -C backend run-tests
```
