# incident-bot

<img src="https://github.com/echoboomer/incident-bot/blob/master/assets/bot.png" width="125" height="125">

Incident management ChatOps bot for Slack.

This bot runs using the `slack-bolt` framework and leverages websockets to avoid a requirement for public inbound access.

- [incident-bot](#incident-bot)
  - [Architecture](#architecture)
  - [Requirements](#requirements)
  - [Features](#features)
    - [Incident Management](#incident-management)
      - [Incident Management Module Requirements](#incident-management-module-requirements)
      - [Incident Management Features](#incident-management-features)
        - [Automatically inviting specific members to the channel every time an incident is started.](#automatically-inviting-specific-members-to-the-channel-every-time-an-incident-is-started)
        - [Automatically posting information regarding external providers](#automatically-posting-information-regarding-external-providers)
        - [Automatically creating an incident via a react](#automatically-creating-an-incident-via-a-react)
      - [Statuspage Integration](#statuspage-integration)
    - [Web Interface](#web-interface)
  - [Updating Literature](#updating-literature)
  - [Required Variables](#required-variables)
  - [Optional Variables](#optional-variables)
  - [Database Migrations](#database-migrations)
  - [Testing](#testing)

## Architecture

The app is written in Python and backed by Postgresql.

Each incident stores unique data referenced by processes throughout the app for lifecycle management on creation. The database should be durable and connection information should be passed to the application securely. In the event that a record is lost while an incident is open, the bot will be unable to manage that incident and none of the commands will work.

If you plan on allowing users to reopen incidents by setting their status back to anything other than `Resolved`, you will need to keep these records intact as well.

## Requirements

- [Create a Slack app](https://api.slack.com/apps?new_app=1) for this application. Call it whatever you want.
- Use the option to create the app from a manifest. Run `make render` to output `slack_app_manifest.yaml` at project root and paste in the contents.
- Install the app to your workspace. You'll now have an OAuth token. Provide that as `SLACK_BOT_TOKEN`.
- Verify that websocket mode is enabled and provide the generated app token as `SLACK_APP_TOKEN`. You need both this and the previous token.

## Features

### Incident Management

- Facilitates creation of incident channels.
- Allows assigning roles for incident management.
  - These roles are currently: `incident commander`, `communications liaison`, and `technical lead`.
  - The first two are based on the first and second tier of roles described by PagerDuty. The last can be thought of as a primary SME contact.
  - If you'd like to change these definitions within the app, see the section below on customization.
- A fully functioning digest channel that stays up to date with incident statuses that can be used by others to watch the status of incidents.
- Optional features documented below.

#### Incident Management Module Requirements

Since this bot mainly helps run incidents, there are a few prerequisites.

- You should have a digest channel that serves as a collection of information for all of your incidents. Provide this as `INCIDENTS_DIGEST_CHANNEL` - this is the channel **name**, not the **ID**. A common sense one is `incidents`. The idea is that all information about ongoing incidents will be sent to this channel and everyone who cares about incident management can go look there.
- Your Slack workspace name (`foobar.slack.com`) minus the domain (`foobar`) should be provided as `SLACK_WORKSPACE_ID`. This is used to format some things related to sending messages to Slack.
- You should invite your bot user to the aforementioned incidents digest channel at a minimum as well as anywhere else you'd like to use it. If you'd like to enable the react-to-create feature, the bot will need to be in every channel you plan to use this in. Common places are alert channels, etc.

#### Incident Management Features

There are two optional features with the incident management module:

##### Automatically inviting specific members to the channel every time an incident is started.

Set the OS environment variable `INCIDENT_AUTO_GROUP_INVITE_ENABLED` to `true`.

Set the OS environment variable `INCIDENT_AUTO_GROUP_INVITE_GROUP_NAME` to the name of the Slack group you want to invite to each newly created incident channel.

##### Automatically posting information regarding external providers

This feature currently supports the following providers, but you can write your own using the existing logic:

- Auth0
- GitHub

To enable, set `INCIDENT_EXTERNAL_PROVIDERS_ENABLED` to `true` and set `INCIDENT_EXTERNAL_PROVIDERS_LIST` to a comma-separated list of providers you'd like to enable. Example: `auth0,github`

By enabling this feature, a message will be dropped into each new incident channel for each provider that recaps, by default, all incidents in the last 5 days. There is a refresh button that will fetch status again and repost the message. This is handy when a provider is experiencing an incident but hasn't updated their status page yet.

##### Automatically creating an incident via a react

If setting `INCIDENT_AUTO_CREATE_FROM_REACT_ENABLED` to `true` and `INCIDENT_AUTO_CREATE_FROM_REACT_EMOJI_NAME` to the name of a Slack emoji, you can automatically have an incident create based on reacting to a message. The bot will create the channel with the suffix `auto-<random 6 char hashed value>` and will paste the contents of the message that was reacted to in the incident channel.

#### Statuspage Integration

If enabling the variable to set the Statuspage integration to enabled (see below) and providing the API key and page ID for your Statuspage account, the bot will drop in a message after the incident is opened that will allow you to create a corresponding Statuspage incident. In a future update, this process will be automated and tied to stages managed by the bot.

For now, you can kick off a new incident by providing a title, description, impact, and by selecting impacted components. You can then move the Statuspage incident through phases until is resolved. Each time you do this, the message will automatically update in your incident channel.

### Web Interface

The application includes a web interface with user management features that can optionally be enabled by setting `WEB_INTERFACE_ENABLED` to `true`. If enabled, the interface is accessible at `/admin`. You also need to set `FLASK_APP_SECRET_KEY` to a secret string of your choosing.

You will most likely want to edit the templates at `templates/webapp` to customize what options you may want available. You can set the bot name and other default parameters for the web interface within `lib/core/webapp.py` using the `@app.context_processor` section.

A default admin account is created with the username `admin@admin.com` and password `admin` when the app is first started. You should login using these credentials, access the admin panel, create your own users, and then disable the admin account. As long as the admin account is disabled, it will not be recreated.

If you wish to allow users to sign up for their own (non-admin) accounts, you can set `signups_enabled=True` in `lib/core/webapp.py` which will enable the route and the sign up button in the UI.

You can customize the HTML templates files to adjust the roles that users can be assigned, etc. This is all up to you.

## Updating Literature

You can change the definitions of severity levels and the incident roles via the `templates/` directory - whatever changes you make to the `json` files will impact the messaging the application uses when advertising information about severity levels, role responsibilities, etc.

## Required Variables

- `POSTGRES_WRITER_HOST` - the hostname of the database.
- `POSTGRES_NAME` - database name to use.
- `POSTGRES_USER` - database user to use.
- `POSTGRES_PASSWORD` - password for the user.
- `POSTGRES_PORT` - the port to use when connecting to the database.
- `INCIDENTS_DIGEST_CHANNEL` - the **name** of the incidents digest channel as described above.
- `INCIDENT_GUIDE_LINK` - a link to your internal guide for handling incidents. **Note:** This must be a fully formed URL - example: `https://mylink.com`.
- `INCIDENT_POSTMORTEMS_LINK` - a link to your postmortem process documentation or postmortem collection. **Note:** This must be a fully formed URL - example: `https://mylink.com`.
- `INCIDENT_CHANNEL_TOPIC` - the topic that will be set for all new incident channels.
- `SLACK_BOT_TOKEN` - the API token to be used by your bot once it is deployed to your workspace.
- `SLACK_APP_TOKEN` - the app-level token for enabling websocket communication.
- `SLACK_WORKSPACE_ID` - if your Slack workspace is `mycompany.slack.com`, this should be `mycompany`.
- `PAGERDUTY_API_TOKEN` - an API token for PagerDuty to enable on-call information parsing and paging.
- `PAGERDUTY_API_USERNAME` - the username associated with the PagerDuty API token.

## Optional Variables

- `AUTH0_DOMAIN` - If using `auth0` as an entry when enabling status for external providers, you must provide this variable and set it to the name of your Auth0 domain.
- `INCIDENT_AUTO_GROUP_INVITE_ENABLED` - to enable the automatic invitation of a Slack group to each newly created incident channel (documented above), set this to `true`.
- `INCIDENT_AUTO_GROUP_INVITE_GROUP_NAME` - if enabling the automatic invitation of a Slack group to each newly created incident channel (documented above), set this to the name of the Slack group. For example: `whatever-group`
- `INCIDENT_EXTERNAL_PROVIDERS_ENABLED` - if enabling status snapshots for external providers (documented above), set this to `true`.
- `INCIDENT_EXTERNAL_PROVIDERS_LIST` - if enabling status snapshots for external providers (documented above), set this to a comma-separated list of providers to enable. For example: `github,heroku`
- `INCIDENT_AUTO_CREATE_FROM_REACT_ENABLED` - if enabling auto incident channel create based on react, set this to `true`.
- `INCIDENT_AUTO_CREATE_FROM_REACT_EMOJI_NAME` - the name of the emoji that will trigger automatic incident creation.
- `STATUSPAGE_INTEGRATION_ENABLED` - set to `true` to enable the Statuspage integration.
- `STATUSPAGE_API_KEY` - Statuspage API key if enabling.
- `STATUSPAGE_PAGE_ID` - Statuspage page ID if enabling.
- `STATUSPAGE_URL` - Link to the public Statuspage for your organization. **Note:** This must be a fully formed URL - example: `https://status.foo.com`.
- `TEMPLATES_DIRECTORY` - set this to the directory your templates will be located in from the project root if you want to override the default of `templates/slack/`. You do not need to provide this otherwise. If you do, you must include the trailing `/` - i.e. `mydirfortemplates/`
- `WEB_INTERFACE_ENABLED` - set this to `true` to enable the optional web management interface.

It is also possible to automatically create an RCA/postmortem document when an incident is transitioned to resolved.

- `AUTO_CREATE_RCA` - Set this to `true` to enable RCA creation. If this is `true`, you must provide all values below.
- `CONFLUENCE_API_URL` - The URL of the Atlassian account.
- `CONFLUENCE_API_USERNAME` - Username that owns the API token.
- `CONFLUENCE_API_TOKEN` - The API token.
- `CONFLUENCE_SPACE` - The space in which the RCAs page lives.
- `CONFLUENCE_PARENT_PAGE` - The name of the page within the above space where RCAs are created as child objects.

## Database Migrations

Migrations can be done using [Alembic](https://github.com/sqlalchemy/alembic). This process uses `config.database_url` so it depends on the same environment variables the main application does for the database. You will need to have a functioning `.env` file configured locally and this process must be done from your local machine for authorized users.

**Note:** The `.env` file is ignored via `.gitignore` - do not commit any sensitive information to this repository when running migrations locally.

To stage a migration file:

```bash
$ make stage_migration DESCRIPTION="Description of the change"
  Generating /Users/scott/src/incident-bot/alembic/versions/e585abb1f948_description_of_the_change_.py ...  done
```

Open the file that was created and adjust the `upgrade()` and `downgrade()` methods accordingly. Consult the [documentation](https://alembic.sqlalchemy.org/en/latest/) for full usage instructions. Create migrations for each necessary transaction.

Finally, run the migration:

```bash
$ make run_migrations
./venv/bin/alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade e585abb1f948 -> 476b2348392c, Description of the change
```

Past migrations can be viewed in the `alembic/` directory for reference and context. Don't delete them as they can be used for downgrading/rolling back.

## Testing

Tests will run on each pull request and merge to the primary branch. To run them locally:

```bash
$ make run-tests
```
