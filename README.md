# incident-bot

![tests](https://github.com/echoboomer/incident-bot/actions/workflows/tests.yml/badge.svg)
![version](https://img.shields.io/github/v/release/echoboomer/incident-bot)

Incident management framework centered around a ChatOps bot for Slack to allow your teams to easily and effectively identify and manage technical incidents impacting your cloud infrastructure, your products, or your customers' ability to use your applications and services.

[Check out Incident Bot's Documentation](https://docs.incidentbot.io)

Need support or just want to chat with us? Join us on [Discord](https://discord.gg/PzqSQUY88c).

- [incident-bot](#incident-bot)
  - [Features at a Glance](#features-at-a-glance)
  - [Quick Start](#quick-start)
    - [Kubernetes](#kubernetes)
  - [Testing](#testing)
  - [Feedback](#feedback)
  - [Contributing](#contributing)

Interacting with the bot is incredibly easy through the use of modals and simplified commands:

<img src="https://github.com/echoboomer/incident-bot/blob/main/assets/incident-bot-demo-1.gif" width="700" height="500" />

Featuring a rich web management UI:

<img src="https://github.com/echoboomer/incident-bot/blob/main/assets/incident-bot-demo-2.gif" width="700" height="500" />

## Features at a Glance

- Helps you declare and run incidents - All the automation you'll need to organize, strategize, and explain
  - Create a a war room Slack channel - Create a Slack channel automatically and prepopulate with key information and manage all of your incidents in a centralized digest channel
  - Control from start to finish - Shift the incident through status and severity from a management menu - never leave the channel
- Helps you find the right people to assist - Page teams, automatically add groups or users, and start putting out fires
  - Manage user participation - Invite key users to an incident channel automatically - users can be elected to roles or can claim them
  - Send out internal updates - Keep your internal users up to date via the incident digest channel
- Handles organizing facts, documentation, and evidence - Automatically build a postmortem doc with a timeline, attach evidence, and collect relevant data
- Integrates with your favorite tools
  - Confluence - Automatically format and create a postmortem document in Confluence
  - Jira - Create and associate Issues for your incidents directly from the channel
  - PagerDuty & OpsGenie - Interact with teams and page or invite them to incidents
  - Statuspage - Create and manage a Statuspage incident directly within the Slack channel
  - Zoom - Create a Zoom meeting for each incident and populate the channel with the link
  - Google Meet - Create a Google Meet meeting for each incident and populate the channel with the link

New features are being added all the time.

## Quick Start

- [Create a Slack app](https://api.slack.com/apps?new_app=1) for this application. You can name it whatever you'd like, but `incident-bot` seems to make the most sense.
- Select `from an app manifest` and copy `manifest.yaml` out of this repository and paste it in to automatically configure the app.
- You'll need the app token, bot token, and user token for your application and provide those as `SLACK_APP_TOKEN`, `SLACK_BOT_TOKEN`, and `SLACK_USER_TOKEN` - these can be found within the app's configuration page in Slack. For more information on Slack tokens, see the documentation [here](https://api.slack.com/authentication/token-types).
- You'll need a Postgres instance to connect to.
- Configure the app using `config.yaml` and deploy it to Kubernetes, Docker, or whichever platform you choose. The structure of the `config.yaml` is explained in the documentation linked below.

Full setup documentation is available [here](https://docs.incidentbot.io/setup/).

### Kubernetes

- The Helm chart is the recommended way to deploy - instructions are available [here](https://docs.incidentbot.io/setup/#helm).
- You can use [kustomize](https://github.com/echoboomer/incident-bot/blob/main/deploy/kustomize/incident-bot/overlays/development/kustomization.yaml). More details available [here](https://docs.incidentbot.io/setup/#kustomize).

## Testing

Tests will run on each pull request and merge to the primary branch. To run them locally:

```bash
make -C backend run-tests
```

## Feedback

This application is not meant to solve every problem with regard to incident management. It was created as an open-source alternative to paid solutions that integrate with Slack.

If you encounter issues with functionality or wish to see new features, please open an issue and let us know.

We encourage you to join the community [Discord](https://discord.gg/PzqSQUY88c) if you wish to interact with us directly.

## Contributing

A pull request template will ask required questions for each pull request. Most importantly, you should make sure to bump all version refs throughout the app. There is a script for this in which the only argument is the version to bump to:

```bash
./scripts/version-bump.sh v1.6.3
```
