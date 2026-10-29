# Row-level security on Relyt One

## The pitfall

Database users created from the Relyt One console, including the default `relytdb_owner`, are created with the
`BYPASSRLS` attribute. Postgres skips every row-level security policy for such a role, even with
`FORCE ROW LEVEL SECURITY`. An app that connects as one of them gets no protection from RLS, and nothing reports
it.

Check a role:

```sql
SELECT rolname, rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user;
```

## Create a NOBYPASSRLS application role

Connect as the database owner (for example `relytdb_owner`) with `psql`, not through the console, and run:

```sql
CREATE ROLE app_user LOGIN NOBYPASSRLS NOSUPERUSER NOCREATEROLE NOCREATEDB;
\password app_user
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
```

`\password` prompts for the password, so it does not end up in shell history or SQL logs. Tables created later
need their own `GRANT` (or `ALTER DEFAULT PRIVILEGES`). Verify:

```sql
SELECT rolname, rolbypassrls, rolsuper FROM pg_roles WHERE rolname = 'app_user';  -- expect f, f
```

Point the app's `DATABASE_URL` at `app_user`; keep the owner role for migrations only.
Do not grant `app_user` membership in a `BYPASSRLS` role: `SET ROLE` to it would bypass RLS again.

## RLS checklist

1. Enable **and force** RLS on every table with per-user or per-tenant rows, so the policies also apply to the
   table owner:

   ```sql
   ALTER TABLE todos ENABLE ROW LEVEL SECURITY;
   ALTER TABLE todos FORCE ROW LEVEL SECURITY;
   CREATE POLICY todos_owner ON todos
     USING (user_id = current_setting('app.user_id', true))
     WITH CHECK (user_id = current_setting('app.user_id', true));
   ```

2. Set the caller's identity **inside a transaction, transaction-local** (third argument `true`), before the
   queries:

   ```sql
   BEGIN;
   SELECT set_config('app.user_id', $1, true);
   -- queries
   COMMIT;
   ```

   With `false`, the setting stays on the connection and, with a pool (including the PgBouncer `poolerHost`),
   the next request can run as the previous user.

3. When the setting is missing, `current_setting('app.user_id', true)` is `NULL`, so the policy matches no row.
   That is the safe default; do not add `OR current_setting(...) IS NULL`.

4. Keep filtering in the application as well (`WHERE user_id = $1`); RLS is the second line of defence.

For end-user identities from Relyt One managed auth (the JWT `sub` claim), see the `relyt-managed-auth` skill.
