# Setup

## Installation

For those who wish to get started quickly without customizing core behavior, there is a public image available based on the latest primary build. The image is available [here](https://hub.docker.com/r/eb129/incident-bot).

You can run the image however you choose. A Docker Compose file is provided for guidance. It is recommended to use the Helm chart if running in Kubernetes.

### Kubernetes

#### Helm

You can get started quickly by using the Helm chart:

```bash
helm repo add echoboomer-charts https://charts.echoboomer.net
```

Sensitive data should come from Kubernetes `Secret` objects at a minimum. 

!!! warning

    Secret management is outside of the scope of this application. Choose the solution that works best for you.

One method is to used something like [sealed secrets](https://github.com/bitnami-labs/sealed-secrets>).

If using `sealed-secrets`, you could create your sensitive environment variables in a `.env` file and create the `Secret` like this:

```bash
kubectl create secret generic incident-bot-secret --from-env-file=.env --dry-run='client' -ojson --namespace incident-bot >incident-bot-secret.json &&
  kubeseal --controller-name sealed-secrets <incident-bot-secret.json >incident-bot-secret-sealed.json &&
  kubectl create -f incident-bot-secret-sealed.json
```

Contained with `.env`, you'd want to include the sensitive values for this application. For example:

```bash
SLACK_APP_TOKEN=xapp-1-...
SLACK_BOT_TOKEN=...
SLACK_USER_TOKEN=xoxp-...
POSTGRES_HOST=...
POSTGRES_DB=incident_bot
POSTGRES_USER=incident_bot
POSTGRES_PASSWORD=...
POSTGRES_PORT=5432
STATUSPAGE_API_KEY=b...
STATUSPAGE_PAGE_ID=f5...
STATUSPAGE_URL=https://status.e...
FLASK_APP_SECRET_KEY=supersecret
ATLASSIAN_API_URL=...
ATLASSIAN_API_USERNAME=...
ATLASSIAN_API_TOKEN=...
ATLASSIAN_OPSGENIE_API_KEY=...
PAGERDUTY_API_TOKEN=...
PAGERDUTY_API_USERNAME=...
DEFAULT_WEB_ADMIN_PASSWORD=...
JWT_SECRET_KEY=...
ZOOM_ACCOUNT_ID=...
ZOOM_CLIENT_ID=...
ZOOM_CLIENT_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_PROJECT_ID=...
GOOGLE_AUTH_URI=...
GOOGLE_TOKEN_URI=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=...
# This is required if setting a custom path for the config file.
# CONFIG_FILE_PATH=config.yaml
```

This will create the required `Secret` in the `Namespace` `incident-bot`. You may need to create the `Namespace` if it doesn't exist.

Create a values file. We'll call this one `incident-bot-values.yaml`:

```yaml
configMap:
  create: true
  data:
    platform: slack
    digest_channel: incidents
    roles:
      incident_commander: "The Incident Commander is the decision maker during a major incident, delegating tasks and listening to input from subject matter experts in order to bring the incident to resolution. They become the highest ranking individual on any major incident call, regardless of their day-to-day rank. Their decisions made as commander are final.\\n\\nYour job as an Incident Commander is to listen to the call and to watch the incident Slack room in order to provide clear coordination, recruiting others to gather context and details. You should not be performing any actions or remediations, checking graphs, or investigating logs. Those tasks should be delegated.\\n\\nAn IC should also be considering next steps and backup plans at every opportunity, in an effort to avoid getting stuck without any clear options to proceed and to keep things moving towards resolution.\\n\\nMore information: https://response.pagerduty.com/training/incident_commander/"
      communications_liaison: "The purpose of the Communications Liaison is to be the primary individual in charge of notifying our customers of the current conditions, and informing the Incident Commander of any relevant feedback from customers as the incident progresses.\\n\\nIt's important for the rest of the command staff to be able to focus on the problem at hand, rather than worrying about crafting messages to customers.\\n\\nYour job as Communications Liaison is to listen to the call, watch the incident Slack room, and track incoming customer support requests, keeping track of what's going on and how far the incident is progressing (still investigating vs close to resolution).\\n\\nThe Incident Commander will instruct you to notify customers of the incident and keep them updated at various points throughout the call. You will be required to craft the message, gain approval from the IC, and then disseminate that message to customers.\\n\\nMore information: https://response.pagerduty.com/training/customer_liaison/"
    severities:
      sev1: 'This signifies a critical production scenario that impacts most or all users with a major impact on SLAs. This is an all-hands-on-deck scenario that requires swift action to restore operation. Customers must be notified.'
      sev2: 'This signifies a significant production degradation scenario impacting a large portion of users.'
      sev3: 'This signifies a minor production scenario that may or may not result in degradation. This situation is worth coordination to resolve quickly but does not indicate a critical loss of service for users.'
      sev4: 'This signifies an ongoing investigation. This incident has not been promoted to SEV3 yet, indicating there may be little to no impact, but the situation warrants a closer look. This is diagnostic in nature. This is the default setting for a new incident.'
    # Whether or not to deliver incident update reminders for critical incidents
    # This will send out a reminder message to an active incident channel at the supplied
    # interval
    incident_reminders:
      # Any severity in this list will have a scheduled reminder job created
      # This job will remind the channel to send out updates at the interval
      # specified rate below
      qualifying_severities:
        - sev1
      # rate determines how often reminders are sent to an incident channel
      # This is an int and is interpreted as minutes
      rate: 30
    statuses:
      - investigating
      - identified
      - monitoring
      - resolved
    options:
      auto_invite_groups:
        enabled: false
        groups:
          - my-slack-group
          - my-other-slack-group
      channel_topic:
        default: 'This is the default incident channel topic. You can edit it in settings.'
        # If set to true, set the channel topic to the meeting link. This will override incident_channel_topic.
        # set_to_meeting_link: true
      conference_bridge_link: 'https://zoom.us'
      create_from_reaction:
        enabled: false
        reacji: create-incident
      # integrations: {}
      # Integrations are covered in their own section.
      skip_logs_for_user_agent:
        # Kubernetes health check user-agent
        - kube-probe
        # AWS ELB health check user-agent
        - ELB-HealthChecker/2.0
      timezone: UTC
    links:
      incident_guide: https://changeme.com
      incident_postmortems: https://changeme.com
envFromSecret:
  enabled: true
  secretName: incident-bot-secret
ingress:
  enabled: true
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: incident-bot.mydomain.com
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls:
    - secretName: incident-bot-tls
      hosts:
        - incident-bot.mydomain.com
podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

You can now install the application. As an example:

```bash
helm install echoboomer-charts/incident-bot --version 1.6.1 --values incident-bot-values.yaml --namespace incident-bot
```

Everything that needs to be configured has been configured directly in the values file as part of the values file.

If you'd like to clean everything up:

```bash
helm uninstall incident-bot --namespace incident-bot
```

#### Kustomize

`kustomize` manifests are provided for convenience.

The manifests are located at: `deploy/kustomize/incident-bot`

To preview generated manifests, run `kubectl kustomize .` from an overlay directory like `development`.

To apply the resources, run: `kubectl apply -k .`

!!! warning

    You will want to adjust the settings within the manifests to suit your needs before deploying. Specifically, `.env` in the overlay folder is used to generate a `Secret` containing sensitive values. Non-sensitive values are provided as literals in the overlay-level `kustomization.yaml` file.

    In production, you should use a secret management tool that integrates with Kubernetes. You should not hardcode sensitive values. This setup is provided for convenience.

    In the default setup, your application's `config.yaml` will be mounted as a volume via a `ConfigMap`.

    Check out the `helm` section above for info on what should go in the `Secret`.

#### Docker Compose

A sample compose file is provided with sample variables. This is useful for running the application locally or in environment that can leverage compose logic. In this scenario, the database runs as a container. This is not recommended for production usage.

!!! warning

    Management of a database is outside of the scope of this application. Setup for a containerized database is provided for convenience when using Docker Compose.

    You should use a Postgres provider of your choice and provide the parameters in the variables mentioned below. At a minimum, the `user`, `password`, and `database` should already exist.

## Required Variables

Regardless of your installation method, these variables are **required**:

- `POSTGRES_HOST` - the hostname of the database.
- `POSTGRES_DB` - database name to use.
- `POSTGRES_USER` - database user to use.
- `POSTGRES_PASSWORD` - password for the user.
- `POSTGRES_PORT` - the port to use when connecting to the database.
- `SLACK_APP_TOKEN` - the app-level token for enabling websocket communication. Found under your Slack app's `Basic Information` tab in the `App-Level Tokens` section.
- `SLACK_BOT_TOKEN` - the API token to be used by your bot once it is deployed to your workspace for `bot`-scoped pemissions. Found under your Slack app's `OAuth & Permissions` tab.
- `SLACK_USER_TOKEN` - the API token to be used by your bot for `user`-scoped permissions. Found under your Slack app's `OAuth & Permissions` tab.
- `DEFAULT_WEB_ADMIN_PASSWORD` - the default password for the default admin account. See section on user management for more details.
- `JWT_SECRET_KEY` - this must be provided for user management. Set to a secure string.
- `FLASK_APP_SECRET_KEY` - this must be provided for the API.

Other variables are covered in the sections below documenting additional integrations.

## Access

It is recommended to deploy this application in a private network or at least behind a private load balancer. There is no need to expose the application to the public Internet.

The web UI should only be accessible internally, and websocket mode eliminates the need to expose any endpoints to Slack.

Please exercise good judgment and caution when deploying this application.

!!! warning

    The application does have an API that can be used to create incidents covered in the configuration section. It is recommended to keep this communication private as well.

## User Management

The value of `DEFAULT_WEB_ADMIN_PASSWORD` will become the default login password for the admin user for the web UI.

The automatically created web UI admin user is `admin@admin.com`. Once you login, you can disable this user. We don't recommend deleting it in the event you need to use it again.

You're able to add new users from the settings page. You can optionally enable/disable and delete the users as well.

At this time, this is basic username (in the form of email) and password authentication. In the future, integration with OAuth providers will be added.
