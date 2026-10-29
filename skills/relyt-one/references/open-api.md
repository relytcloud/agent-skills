# Relyt One Open API

Base URL: `https://relytone.data.cloud/api/v1`

Authentication: an API key created in the console (organization **Settings**), sent as `x-api-key: <key>` or
`Authorization: Bearer <key>`. Requests act as the user who owns the key and see only that user's organizations.

```bash
export RELYT_API_KEY=...          # never commit or print it
export RELYT_API=https://relytone.data.cloud/api/v1
```

Rules:

- Use only the calls on this page. Anything else (databases, roles, metrics, usage, auth settings) is done in
  the console.
- Use the `id` values from responses as path and query parameters. They are opaque strings; do not build them.
  Branches are the exception: branch calls take the branch's `slug` (`br-...`), not its `id`.
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

Create a project. `region` is a region `id` from [the regions list](#regions); `password` becomes the password
of the default database user `relytdb_owner`. Read it from the environment rather than writing it inline:

```bash
curl -sS -X POST "$RELYT_API/projects" \
  -H "x-api-key: $RELYT_API_KEY" -H "content-type: application/json" \
  -d "$(jq -n --arg org "$ORG_ID" --arg pw "$DB_PASSWORD" \
        '{name: "my-app", orgId: $org, region: "<region id>", password: $pw}')"
```

The response (`201`) is the new project; `branchSlug` is the `slug` of its primary branch. Its compute starts in
`CREATING`; poll the computes list until the status is `READY` before connecting. Sending the same request again
while the first is still running returns `202`; after it finished, it returns the same project with `200`.

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

A compute has `status` (wait for `READY`), `computeType` (`primary` or `replica`), `host` (direct) and
`poolerHost` (PgBouncer). Build the connection string from these hosts; the
database user and password are not returned by the API.

## Branches

Every project has a primary branch; each branch has its own primary compute. List a project's branches (primary
first). Each branch has an `id` and a `slug`; use the `slug` in branch paths and as `parentBranchSlug`. Its
`computes` carry `slug` (the compute `id` used by the compute calls), `status`, `host` and `poolerHost`:

```bash
curl -sS "$RELYT_API/projects/$PROJECT_ID/branches" -H "x-api-key: $RELYT_API_KEY"
```

Create a branch. With `parentBranchSlug` it starts as a copy of that branch's data (at `pointInTime`, an ISO 8601
timestamp, if given); without it, it starts empty. The response is `{id, name, slug}`; poll the branches list
until the new branch's compute is `READY`. A name already used by an active branch returns `409`:

```bash
curl -sS -X POST "$RELYT_API/projects/$PROJECT_ID/branches" \
  -H "x-api-key: $RELYT_API_KEY" -H "content-type: application/json" \
  -d '{"name": "dev", "parentBranchSlug": "br-example"}'

curl -sS -X POST "$RELYT_API/projects/$PROJECT_ID/branches" \
  -H "x-api-key: $RELYT_API_KEY" -H "content-type: application/json" \
  -d '{"name": "before-migration", "parentBranchSlug": "br-example", "pointInTime": "2026-01-01T12:00:00Z"}'
```

Rename and delete a branch. The primary branch, and a branch that still has child branches, cannot be deleted
(`400`; the response lists the children):

```bash
curl -sS -X PATCH "$RELYT_API/projects/$PROJECT_ID/branches/$BRANCH_SLUG" \
  -H "x-api-key: $RELYT_API_KEY" -H "content-type: application/json" \
  -d '{"name": "staging"}'

# Destructive: deletes the branch's compute and data. Ask the user first.
curl -sS -X DELETE "$RELYT_API/projects/$PROJECT_ID/branches/$BRANCH_SLUG" -H "x-api-key: $RELYT_API_KEY"
```

## Regions

List the regions a project can be created in; use a region's `id` as `region` when creating a project:

```bash
curl -sS "$RELYT_API/regions" -H "x-api-key: $RELYT_API_KEY"
```

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
