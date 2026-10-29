# Relyt One Open API

Base URL: `https://relytone.data.cloud/api/v1`

Authentication: an API key created in the console (organization **Settings**), sent as `x-api-key: <key>` or
`Authorization: Bearer <key>`. Requests act as the user who owns the key and see only that user's organizations.

```bash
export RELYT_API_KEY=...          # never commit or print it
export RELYT_API=https://relytone.data.cloud/api/v1
```

Rules:

- Use only the calls on this page. Anything else (branches, databases, roles, metrics, usage, auth settings) is
  done in the console.
- Use the `id` values from responses as path and query parameters. They are opaque strings; do not build them.
- Responses are JSON. Errors are JSON with an `error` field; `401` means the key is missing or invalid, `404`
  means the resource does not exist **or** the key's user cannot see it.
- Ask the user before any `DELETE`.

## Organizations

List the organizations the key's user belongs to:

```bash
curl -sS "$RELYT_API/organizations" -H "x-api-key: $RELYT_API_KEY"
```

Get one organization:

```bash
curl -sS "$RELYT_API/organizations/$ORG_ID" -H "x-api-key: $RELYT_API_KEY"
```

Rename an organization (owners and admins only; other members get `404`):

```bash
curl -sS -X PATCH "$RELYT_API/organizations/$ORG_ID" \
  -H "x-api-key: $RELYT_API_KEY" -H "content-type: application/json" \
  -d '{"name": "Acme Data"}'
```

## Projects

List the projects of an organization (`orgId` is the organization's `id`):

```bash
curl -sS "$RELYT_API/projects?orgId=$ORG_ID" -H "x-api-key: $RELYT_API_KEY"
```

Create a project. `region` is a region identifier as offered in the console's create-project dialog (ask the
user if you do not know it); `password` becomes the password of the default database user `relytdb_owner`.
Read it from the environment rather than writing it inline:

```bash
curl -sS -X POST "$RELYT_API/projects" \
  -H "x-api-key: $RELYT_API_KEY" -H "content-type: application/json" \
  -d "$(jq -n --arg org "$ORG_ID" --arg pw "$DB_PASSWORD" \
        '{name: "my-app", orgId: $org, region: "<region id>", password: $pw}')"
```

The response (`201`) is the new project. Its compute starts in `CREATING`; poll the computes list until the
status is `READY` before connecting.

Get, rename and delete a project:

```bash
curl -sS "$RELYT_API/projects/$PROJECT_ID" -H "x-api-key: $RELYT_API_KEY"

curl -sS -X PATCH "$RELYT_API/projects/$PROJECT_ID" \
  -H "x-api-key: $RELYT_API_KEY" -H "content-type: application/json" \
  -d '{"name": "my-app-prod"}'

# Destructive (owners and admins only): deletes the project's branches, computes and data. Ask the user first.
curl -sS -X DELETE "$RELYT_API/projects/$PROJECT_ID" -H "x-api-key: $RELYT_API_KEY"
```

## Computes

List a project's computes (optionally only one, with `compute=<compute id>`):

```bash
curl -sS "$RELYT_API/projects/$PROJECT_ID/computes" -H "x-api-key: $RELYT_API_KEY"
curl -sS "$RELYT_API/projects/$PROJECT_ID/computes?compute=$COMPUTE_ID" -H "x-api-key: $RELYT_API_KEY"
```

Get one compute:

```bash
curl -sS "$RELYT_API/projects/$PROJECT_ID/computes/$COMPUTE_ID" -H "x-api-key: $RELYT_API_KEY"
```

A compute has `status` (`READY`, `FROZEN`, `CREATING`, `PROVISIONING`, `ERROR`), `computeType` (`primary` or
`replica`), `host` (direct) and `poolerHost` (PgBouncer). Build the connection string from these hosts; the
database user and password are not returned by the API.

## API keys

List the current user's keys (masked), create one, delete one:

```bash
curl -sS "$RELYT_API/user/api-keys" -H "x-api-key: $RELYT_API_KEY"

curl -sS -X POST "$RELYT_API/user/api-keys" \
  -H "x-api-key: $RELYT_API_KEY" -H "content-type: application/json" \
  -d '{"name": "ci", "description": "CI pipeline"}'

curl -sS -X DELETE "$RELYT_API/user/api-keys?id=$KEY_ID" -H "x-api-key: $RELYT_API_KEY"
```

The create response contains the full key **once**. Hand it to the user or store it in their secret manager;
do not print it into logs.
