# Browser: sessions, social sign-in, teams

Patterns from the TODO example's
[`lib/browser-auth.ts`](https://github.com/relytcloud/relyt-auth-examples/blob/main/todo/lib/browser-auth.ts)
and the [`@relyt/auth` README](https://github.com/relytcloud/relyt-auth-js#readme).

## Session token and JWTs

```ts
import { createAuthClient } from "@relyt/auth";

const authUrl = process.env.NEXT_PUBLIC_RELYT_AUTH_URL!; // from the console, never hard-coded
const KEY = "relyt-session";
export const client = createAuthClient({
  authUrl,
  sessionToken: () => localStorage.getItem(KEY),
  onSessionToken: (t) => localStorage.setItem(KEY, t),
});

export async function emailSignIn(email: string, password: string) {
  const res = await fetch(`${authUrl}/api/auth/sign-in/email`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
    credentials: "omit",
  });
  if (!res.ok) throw new Error(`sign-in failed (${res.status})`);
  const token = res.headers.get("set-auth-token"); // missing => origin not in Trusted origins
  if (!token) throw new Error("no session token");
  localStorage.setItem(KEY, token);
}

const jwt = await client.getToken(); // cached, refreshed before expiry
await fetch("/api/todos", { headers: { authorization: `Bearer ${jwt}` } });
```

- Sign-up is `POST <authUrl>/api/auth/sign-up/email` with `{ email, password, name }`.
- The client only carries tokens; the server verifies them.
- A session token in `localStorage` is readable by any script on your origin: load no third-party scripts, or keep
  the token in memory only.
- Sign-out: `POST <authUrl>/api/auth/sign-out` with `Authorization: Bearer <session token>`, then `client.clear()`,
  remove the stored token, and clear the page cookie on your server (`clearTokenCookie`).
- Page navigation: post the JWT to your own server route, which verifies it and calls `setTokenCookie(res, jwt)`
  (`HttpOnly; Secure; SameSite=Lax`, cookie `__Host-relyt-at`). Safari refuses `Secure` cookies on
  `http://localhost`; develop over HTTPS or in another browser.

## Social sign-in (GitHub, Google)

```ts
import { startSocialSignIn, completeSocialSignIn } from "@relyt/auth";

// sign-in button
const cb = `${location.origin}/auth/callback`;      // registered exactly in Callback URLs
await startSocialSignIn({ authUrl, provider: "github", callbackURL: cb, errorCallbackURL: cb, newUserCallbackURL: cb });

// /auth/callback page, first thing on load
await completeSocialSignIn({ authUrl, client, onSessionToken: (t) => localStorage.setItem(KEY, t) });
```

Callback page rules (a security boundary):

1. Call `completeSocialSignIn` **before** loading any third-party script.
2. **No HTTP redirect** before the code is read, and no open redirect. List the callback path in the middleware's
   `publicPaths`.
3. Register the **exact** callback URLs and the app's **exact origin** in the console. No wildcards.
4. Every page that can receive the redirect (`callbackURL`, `errorCallbackURL`, `newUserCallbackURL`) calls
   `completeSocialSignIn`.
5. Start and finish on **the same origin** (`www.example.com` and `example.com` differ): the PKCE verifier is in
   `sessionStorage`.
6. Send `Referrer-Policy: no-referrer` (or `<meta name="referrer" content="no-referrer">`) on the callback page.

The code is single-use and valid for 60 seconds; the exchange is not retried. On failure, let the user click
sign-in again. Errors are `RelytAuthError` with `code` such as `no_pending_sign_in`, `invalid_handoff_code`,
`oauth_error`, `rate_limited`, `network`.

## Teams (organizations)

Organization endpoints are on the auth host and take the user's **session token** as `Authorization: Bearer`:

- `POST <authUrl>/api/auth/organization/set-active` to switch the active organization; then call `client.clear()`
  and get a new JWT so `o` reflects the new team, and refresh the page cookie.
- `POST .../organization/invite-member` `{ "email", "role" }`, `POST .../organization/accept-invitation`
  `{ "invitationId" }`, `GET .../organization/list-members`, `POST .../organization/update-member-role`,
  `POST .../organization/remove-member`.

If `set-active` succeeded but refreshing the page cookie failed, send the browser through your sign-in page so
the page and the API never disagree about the active team.
