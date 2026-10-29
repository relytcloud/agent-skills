# Server and database patterns

These mirror the [TODO example](https://github.com/relytcloud/relyt-auth-examples/tree/main/todo)
(`lib/auth.ts`, `lib/authz.ts`, `lib/db.ts`, `drizzle/*.sql`). Read those files for the complete, tested version.

## Claims

`getClaims` / `createVerifier` return `RelytClaims`:

| Claim | Meaning |
|---|---|
| `sub` | user id on the auth host (use as the user key in your tables) |
| `iss`, `aud` | both equal the auth host origin (`RELYT_AUTH_ISSUER`) |
| `iat`, `exp` | issued / expiry; lifetime at most 15 minutes |
| `role` | always `"authenticated"` |
| `o` | optional active organization: `{ id, slug, role, perms }`; `perms` is `string[]` (`"resource:action"`) or `null` |

The SDK pins `EdDSA`, takes keys only from `<issuer>/.well-known/jwks.json`, and never follows `jku` / `x5u` /
embedded keys. Do not add your own JWT parsing next to it.

## Identity and authorization (one module)

```ts
// lib/authz.ts
import type { RelytClaims } from "@relyt/auth";

export type Identity = { sub: string; org: { id: string; role: string; perms: readonly string[] | null } | null };

export function identityFromClaims(c: RelytClaims): Identity {
  return { sub: c.sub, org: c.o ? { id: c.o.id, role: c.o.role, perms: c.o.perms } : null };
}

export type Decision = { ok: true } | { ok: false; status: 403 | 404; error: string };

export function authorizeTeam(id: Identity, permission: string): Decision {
  if (!id.org) return { ok: false, status: 403, error: "no_active_organization" };
  if (id.org.perms === null) return { ok: false, status: 403, error: "permissions_unavailable" }; // unknown = deny
  return id.org.perms.includes(permission) ? { ok: true } : { ok: false, status: 403, error: "forbidden" };
}
```

Route handlers call `authorizeTeam(identity, "todo:create")` and similar; they never compare roles or permission
strings themselves. For a single row: if the caller cannot see it at all, answer 404 (same as a missing row); if
they can see it but lack the permission, answer 403.

`o.perms` is `null` when the permission list is too large for a token. The auth host expects the app to ask its
`organization/has-permission` endpoint with the user's session instead; a server that only sees JWTs should deny.

## One database entry point

```ts
// lib/db.ts (node-postgres)
import pg from "pg";
const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL }); // a NOBYPASSRLS role

export async function withIdentity<T>(id: Identity, fn: (c: pg.PoolClient) => Promise<T>): Promise<T> {
  if (!id.sub) throw new Error("withIdentity: empty subject");
  const c = await pool.connect();
  try {
    await c.query("begin");
    await c.query("select set_config('app.user_id', $1, true), set_config('app.org_id', $2, true)", [id.sub, id.org?.id ?? ""]);
    const out = await fn(c);
    await c.query("commit");
    return out;
  } catch (e) {
    await c.query("rollback").catch(() => undefined);
    throw e;
  } finally {
    c.release();
  }
}
```

## Schema and policies

```sql
CREATE TABLE todos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL,        -- JWT sub
  org_id text,                  -- JWT o.id; NULL = personal row
  title text NOT NULL,
  done boolean NOT NULL DEFAULT false
);
ALTER TABLE todos ENABLE ROW LEVEL SECURITY;
ALTER TABLE todos FORCE ROW LEVEL SECURITY;

CREATE POLICY todos_personal ON todos
  USING (org_id IS NULL AND user_id = current_setting('app.user_id', true))
  WITH CHECK (org_id IS NULL AND user_id = current_setting('app.user_id', true));

CREATE POLICY todos_team ON todos
  USING (org_id IS NOT NULL AND org_id = current_setting('app.org_id', true))
  WITH CHECK (org_id IS NOT NULL AND org_id = current_setting('app.org_id', true));
```

RLS decides visibility only; which role may write is the authorization module's job. Keep the query's own filter
(`WHERE org_id IS NULL AND user_id = $sub`, or `WHERE org_id = $orgId`) as well.

Connect as a dedicated role created with
`CREATE ROLE todo_app LOGIN NOBYPASSRLS NOSUPERUSER NOCREATEROLE NOCREATEDB;` plus the needed `GRANT`s, and check
`SELECT rolbypassrls FROM pg_roles WHERE rolname = 'todo_app'` returns `f`. Console-created database users have
`BYPASSRLS`.

## Tests worth having

Sign JWTs with a local fake issuer (EdDSA key pair and a JWKS endpoint), as the example's
`test/helpers/issuer.ts` does, and cover: forged `org_id` / `x-user-id` inputs are ignored, missing `o`,
`perms: null` is denied, another user's row is 404, and no pooled connection keeps `app.user_id` / `app.org_id`
after a request.
