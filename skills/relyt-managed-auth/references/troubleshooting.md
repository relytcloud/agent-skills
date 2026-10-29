# Troubleshooting managed auth

| Symptom | Check |
|---|---|
| Sign-in shows "Failed to fetch" / a network error | The app's exact origin is missing from **Trusted origins**, or `NEXT_PUBLIC_RELYT_AUTH_URL` was wrong at build time (rebuild after changing it). |
| Email sign-in succeeds but there is no `set-auth-token` header | Same: the origin is not trusted, so the browser hides the header. |
| Every API call is 401 `invalid_token` | `RELYT_AUTH_ISSUER` differs from the token's `iss` (scheme, host, port, trailing slash). Copy the Auth URL from the console exactly. |
| API calls are 503 | The server cannot fetch `<RELYT_AUTH_ISSUER>/.well-known/jwks.json` (egress, DNS, proxy). Do not turn this into 401. |
| 401 right after a key rotation, only for some tokens | Tokens without a `kid` header are rejected while two keys are published; this resolves when old tokens expire (15 minutes). |
| Social sign-in ends with `no_pending_sign_in` | Started on another origin (`www.` vs bare, `localhost` vs `127.0.0.1`), in another tab, or more than 10 minutes earlier. |
| Social sign-in ends with a network error | Origin missing from Trusted origins (the code exchange is a CORS request). |
| The provider says redirect URI mismatch | The provider's OAuth app must redirect to `https://<authHost>/api/auth/callback/<provider>`, not to your app. |
| Callback URL rejected by the auth host | It is not registered exactly under **Callback URLs**, or its origin is not in Trusted origins. |
| 403 `no_active_organization` | The session has no active organization; let the user pick or create one (`organization/set-active`). |
| 403 `forbidden` | The role lacks `<resource>:<action>` in the branch's **Roles and permissions**. |
| 403 `permissions_unavailable` | `o.perms` is `null` (the permission list overflowed the token); reduce resources and actions. |
| After switching teams the API still sees the old team | The cached JWT was not dropped: `client.clear()` after `set-active`, then `getToken()`. |
| Users see each other's rows when querying by hand | You are connected as a `BYPASSRLS` role (console-created database users are) or a superuser. |
| Users are signed out during an outage | The app clears the session token on any error; clear it only on 401/403. |
| Signed in, but pages keep redirecting to the sign-in page on `http://localhost` in Safari | Safari rejects `Secure` / `__Host-` cookies over plain HTTP. |
