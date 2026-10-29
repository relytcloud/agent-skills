---
name: relyt-one
description: Relyt One serverless Postgres. Use when the user wants to create or connect to a Relyt One database, get a connection string (direct or pooled), automate organizations, projects, computes or API keys through the Relyt One Open API with an API key, pick Postgres extensions on Relyt One (vector search with pgvecto.rs, UUIDs, trigram search), or use row-level security on Relyt One. Not for the managed-auth integration; see the relyt-managed-auth skill.
license: MIT
metadata:
  author: relytcloud
  version: "0.1.0"
---

# Relyt One

Relyt One is a serverless Postgres service. You manage it in the web console at
<https://relytone.data.cloud> and, for automation, through its Open API.

Resources form a tree:

```
Organization -> Project -> Branch (a tree; one primary branch) -> Compute (a Postgres endpoint)
```

- An **organization** holds members and projects. Members have the role `owner`, `admin` or `member`.
- A **project** has a region and a Postgres version (`pgVersion`). Creating a project also creates its primary
  branch and a compute.
- A **branch** is a copy of a project's data that can be changed independently of its parent.
- A **compute** is the Postgres server you connect to. It has a direct `host` and a pooled `poolerHost`.

## Before you act

- Only use what this skill and its references describe. Relyt One has **no MCP server, no CLI, no Data API and
  no Neon migration tool**. Do not invent commands, packages or endpoints for them.
- Never put an API key, database password or connection string with a password into code, commits, logs or chat.
  Read them from environment variables (`RELYT_API_KEY`, `DATABASE_URL`).
- Deleting a project deletes its branches, computes and data. Ask the user before calling a delete endpoint.

## Get started in the console

1. Sign in at <https://relytone.data.cloud> and pick (or create) an organization.
2. Create a project: choose a name, a region and the password of the default database user. The project gets a
   primary branch and a compute; wait until the compute is `READY`.
3. On the branch page, open **Connect** to copy the connection details. The default database user is
   `relytdb_owner` with the password from step 2.

## Connect

The console's Connect dialog gives `psql`, JDBC and connection-string forms. All of them require TLS:

```bash
export DATABASE_URL='postgresql://relytdb_owner:<password>@<host>/<database>?sslmode=require'
psql "$DATABASE_URL"
```

- **Direct host** (`host`): use for migrations, long-lived sessions, `LISTEN/NOTIFY`, session-level `SET`,
  advisory locks and prepared statements that must survive across transactions.
- **Pooled host** (`poolerHost`, "Connection pooling via PgBouncer" in the Connect dialog): use for serverless
  functions and apps that open many short connections. Keep per-request state transaction-local
  (`SET LOCAL`, `set_config(..., true)`), because the next client can get the same server connection.
- Copy the host names from the console or from the compute returned by the Open API. Do not guess or construct
  host names.

## Automate with the Open API

Base URL `https://relytone.data.cloud/api/v1`. Create an API key in the console (organization **Settings**). The
full key is shown only once, at creation. Send it as `x-api-key` (or `Authorization: Bearer <key>`):

```bash
export RELYT_API_KEY=...   # from the console; never commit it
curl -sS https://relytone.data.cloud/api/v1/organizations -H "x-api-key: $RELYT_API_KEY"
```

The `id` values in responses are the identifiers to pass back in paths and parameters (`orgId`, project `id`,
compute `id`). Every supported call, with request bodies, is in [references/open-api.md](references/open-api.md).
Use only the endpoints listed there.

## Extensions

Available: `vectors` (pgvecto.rs, vector search), `pg_trgm`, `citext`, `pgcrypto`. Check what a compute offers
with `SELECT name, default_version, installed_version FROM pg_available_extensions ORDER BY name;`.

**Not available**, and what to use instead:

| Do not use | Use instead |
|---|---|
| `vector` (pgvector), `CREATE EXTENSION vector` | `vectors` (pgvecto.rs). Different extension, different index syntax; see [references/extensions.md](references/extensions.md) |
| `uuid-ossp` (`uuid_generate_v4()`) | `gen_random_uuid()` (built into Postgres 13 and later; no extension needed) |
| `postgis` | No geospatial extension is available; store coordinates in plain columns |

When code or an ORM migration says `CREATE EXTENSION vector` or uses pgvector-only features, adapt it as shown in
[references/extensions.md](references/extensions.md) instead of retrying.

## Row-level security: BYPASSRLS pitfall

Database users created from the Relyt One console, including the default `relytdb_owner`, have the `BYPASSRLS`
attribute. If your app connects as one of them, **every RLS policy is silently skipped**. For RLS, create a
dedicated application role with SQL and connect the app as that role. Steps and checks are in
[references/rls.md](references/rls.md).

## References

- [references/open-api.md](references/open-api.md): every supported Open API call with curl examples
- [references/extensions.md](references/extensions.md): pgvecto.rs (`vectors`) syntax, UUIDs, trigram search
- [references/rls.md](references/rls.md): NOBYPASSRLS application role and RLS checklist
- Managed auth (sign-in for your app's end users, Preview): the `relyt-managed-auth` skill
