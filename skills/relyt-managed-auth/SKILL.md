---
name: relyt-managed-auth
description: Add Relyt One managed auth (Preview) to a web app. Use when the user wants end-user sign-in (email and password, GitHub, Google) hosted by Relyt One, to verify Relyt One JWTs on a server with the @relyt/auth SDK, to protect Next.js routes, to use the JWT subject with Postgres row-level security, to authorize by team (organization) roles and permissions, or to debug sign-in, CORS, callback or 401/403/503 errors with Relyt One managed auth.
license: MIT
metadata:
  author: relytcloud
  version: "0.1.0"
---

# Relyt One managed auth (Preview)

Managed auth is a **Preview** feature. It gives each Relyt One branch its own auth host that signs users in
(email and password, GitHub, Google), manages organizations ("teams") with roles and permissions, and issues
short-lived EdDSA-signed JWTs. Your server verifies those JWTs with
[`@relyt/auth`](https://github.com/relytcloud/relyt-auth-js#readme) (npm `@relyt/auth`).

The reference implementation is the
[Relyt One TODO example](https://github.com/relytcloud/relyt-auth-examples/tree/main/todo); its
[AGENTS.md](https://github.com/relytcloud/relyt-auth-examples/blob/main/todo/AGENTS.md) is the integration
checklist. Follow it and copy its patterns rather than inventing new ones.

## Prerequisites (console; ask the user to do these)

1. **Enable auth on the branch**: in the Relyt One console open the project, then the branch, then its **Auth**
   section, and enable auth (organization owners and admins only). Wait until setup is finished.
2. **Copy the Auth URL** shown there. It is the auth host's origin, `https://<authHost>`. **Never hard-code or
   guess an auth host name**; always take it from the console and keep it in configuration.
3. **Sign-in methods**: enable email and password, and for social sign-in GitHub and/or Google with the
   provider's client id and secret. In the provider's OAuth app, the redirect URL is the **auth host's**
   `https://<authHost>/api/auth/callback/<provider>`, not your app's.
4. **Redirects & origins**: add your app's **exact origin** to **Trusted origins** (`https://app.example.com`: no
   wildcard, no path, no trailing slash) and, for social sign-in, your app's **exact callback URL** to **Callback
   URLs** (`https://app.example.com/auth/callback`). Register every origin you serve from, including
   `http://localhost:<port>` for development.
5. **Roles and permissions** (only for teams): add your resources and actions, for example a `todo` resource with
   `create`, `read`, `update`, `delete`, and grant them to roles (`owner`, `admin`, `member` are built in).

## Configuration

```bash
RELYT_AUTH_ISSUER=https://<authHost>           # server; the Auth URL from the console, exactly
NEXT_PUBLIC_RELYT_AUTH_URL=https://<authHost>  # browser; same value, inlined at build time
```

`RELYT_AUTH_ISSUER` must equal the token's `iss` byte for byte (scheme, host, port, no trailing slash).

## Server: verify every request

```bash
npm install @relyt/auth   # Node.js 20+, ESM only; Next.js ^14.2.35 or >=15.5.28 <16 for @relyt/auth/next
```

```ts
// lib/auth.ts
import { getClaims, RelytAuthUnavailableError } from "@relyt/auth/next";

export async function requireUser(req: Request) {
  try {
    // API routes: bearer tokens only (no cookie), so the API needs no CSRF protection.
    const claims = await getClaims(req, { issuer: process.env.RELYT_AUTH_ISSUER! }, { cookie: false });
    if (!claims) return { ok: false as const, response: Response.json({ error: "unauthorized" }, { status: 401 }) };
    return { ok: true as const, claims };
  } catch (e) {
    if (e instanceof RelytAuthUnavailableError) {
      // signing keys (JWKS) unreachable: 503, never 401
      return { ok: false as const, response: Response.json({ error: "auth_unavailable" }, { status: 503, headers: { "retry-after": "2" } }) };
    }
    throw e;
  }
}
```

```ts
// middleware.ts: a convenience (redirects pages, early 401 for the API), not the security boundary
import { createAuthMiddleware } from "@relyt/auth/next";
export const middleware = createAuthMiddleware({
  issuer: process.env.RELYT_AUTH_ISSUER!,
  signInUrl: "/sign-in",                 // use an absolute URL in production
  publicPaths: ["/sign-in", "/auth/callback"],
  cookieOnApi: false,
});
export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
```

Outside Next.js, use `createVerifier({ issuer })` from `@relyt/auth`: `invalid_token` / `invalid_claims` map to 401,
`jwks_unavailable` to 503.

## Rules that must hold

- **Identity comes only from the verified JWT.** The user is `claims.sub`; the active team is `claims.o`
  (`id`, `slug`, `role`, `perms`). Never read a user or organization id from the body, query string or headers.
- **Every route handler calls `requireUser` itself.** The middleware strips `x-relyt-*` headers and does not
  forward claims.
- **API routes accept `Authorization: Bearer <JWT>` only.** The HttpOnly cookie (`setTokenCookie`) is for page
  navigation.
- **Database access goes through one function** that opens a transaction and first runs
  `select set_config('app.user_id', $1, true), set_config('app.org_id', $2, true)` with `sub` and `o.id`
  (third argument `true`: transaction-local, so pooled connections never carry one user's identity to the next).
- **RLS is enabled and forced** on user-data tables, with policies on `current_setting('app.user_id', true)` /
  `current_setting('app.org_id', true)`, and the app connects as a **NOBYPASSRLS** role. Database users created in
  the Relyt One console have `BYPASSRLS`, which silently skips RLS (see the `relyt-one` skill, RLS reference).
- **All permission decisions live in one module.** `o.perms` is a list of `resource:action` strings;
  **`o.perms === null` means unknown and must be denied** (403), never treated as full access.
- **Invisible is 404, visible but not allowed is 403.**
- **A 503 is not a sign-out.** Clear the stored session token only on 401/403 from the auth host or a rejected JWT.

Code for these rules: [references/server-and-database.md](references/server-and-database.md).

## Browser: sign-in and tokens

- `createAuthClient({ authUrl, sessionToken, onSessionToken })` from `@relyt/auth` turns the auth host's session
  token into cached short-lived JWTs (`getToken()`), which you send as `Authorization: Bearer`.
- Email sign-in and sign-up: `POST <authUrl>/api/auth/sign-in/email` or `/api/auth/sign-up/email`; the session
  token comes back in the `set-auth-token` response header.
- Social sign-in: `startSocialSignIn` on the button, and a callback page that calls `completeSocialSignIn` first.
  Callback page rules (public, no redirect, no third-party scripts before the call, same origin as the start
  page) are in [references/browser-and-social.md](references/browser-and-social.md).
- Teams: switching organization goes through the auth host (`organization/set-active`); afterwards call
  `client.clear()` and fetch a new JWT so `o` changes.

## When something fails

See [references/troubleshooting.md](references/troubleshooting.md). The usual causes: origin not in Trusted
origins (browser shows a network error), `RELYT_AUTH_ISSUER` not exactly the token's `iss` (every call 401),
JWKS unreachable (503), callback URL or origin mismatch (`no_pending_sign_in`), no active organization or a
missing permission (403).

## Not available yet

Do not use or invent: a Relyt One Data API (REST over the database), a CLI, an MCP server, server-side admin SDK
calls, or migration tools from other auth providers. Use the console and `@relyt/auth` only.
