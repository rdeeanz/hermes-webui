# Reverse proxy, TLS, and HTTPS

How to put Hermes WebUI behind nginx or Caddy on a public hostname, with TLS.

Read this if you want a real domain, a browser padlock, or **Web Push
notifications**. If you only need to reach the WebUI from your own devices, an
SSH tunnel or Tailscale is simpler and needs none of this --
see [`remote-access.md`](remote-access.md).

## Why HTTPS is not optional here

Three features are gated by the browser's *secure context* rule and simply do
not exist over plain HTTP on a non-loopback host:

| Feature | Without HTTPS |
|---|---|
| **Web Push** (notifications when the browser is closed) | `PushManager.subscribe()` never succeeds. The toggle in Settings cannot be turned on. |
| **PWA install / "Add to Home Screen"** | Not offered. On iPhone and iPad this is the *only* way to receive push at all -- a Safari tab cannot. |
| **Passkeys / WebAuthn** | Registration and login are refused by the browser. |

`localhost` is exempt from the secure-context rule, which is why everything
works when you tunnel to `http://localhost:8787` but stops working the moment
you expose the same server on `http://your-domain.com`. Plain HTTP on a public
hostname is the one configuration that is *worse* than the tunnel it replaced.

---

## Caddy (recommended -- automatic TLS)

Caddy obtains and renews certificates on its own and streams unbuffered by
default. This complete `Caddyfile` is all you need:

```caddyfile
hermes.example.com {
    reverse_proxy 127.0.0.1:8787 {
        # SSE: flush every write instead of buffering. Caddy already does this
        # for text/event-stream, but being explicit costs nothing and survives
        # someone adding a buffering directive later.
        flush_interval -1

        # An idle agent turn can hold a stream open for a long time.
        transport http {
            read_timeout 24h
        }
    }

    # Workspace file uploads. Raise together with HERMES_WEBUI_MAX_UPLOAD_MB.
    request_body {
        max_size 20MB
    }
}
```

Then set these in your `.env` and restart the WebUI:

```bash
HERMES_WEBUI_HOST=127.0.0.1                 # only Caddy should reach it
HERMES_WEBUI_PASSWORD=<something-strong>
HERMES_WEBUI_TRUST_FORWARDED_PROTO=1        # see "Cookies" below
HERMES_WEBUI_TRUST_FORWARDED_HOST=1
HERMES_WEBUI_TRUST_FORWARDED_FOR=1
```

(Sessions already last 30 days by default -- nothing to set for that.)

Skip to [Verifying it works](#verifying-it-works).

---

## nginx

nginx buffers proxied responses by default, which breaks SSE. The three lines
marked below are the difference between a working app and one that appears to
hang on every message.

```nginx
server {
    listen 443 ssl;
    http2 on;                    # nginx >= 1.25.1
    # On older nginx, delete the line above and use: listen 443 ssl http2;
    server_name hermes.example.com;

    ssl_certificate     /etc/letsencrypt/live/hermes.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/hermes.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # Workspace file uploads. Keep in sync with HERMES_WEBUI_MAX_UPLOAD_MB
    # (default 20). Too low here surfaces as a 413 from nginx, not from Hermes.
    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_http_version 1.1;

        # Host must be the PUBLIC hostname, not the upstream address. The CSRF
        # origin check compares the browser's Origin header against this value;
        # forwarding "127.0.0.1:8787" makes every POST fail. See "CSRF" below.
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection        "";     # keep-alive, required for SSE

        # ══ REQUIRED FOR SSE — do not remove ═════════════════════════════════
        # Without these, nginx accumulates the stream in its own buffer and
        # releases it only when the response ends. The agent's reply arrives
        # all at once when the turn finishes, or not at all.
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 24h;
        # ═════════════════════════════════════════════════════════════════════
    }
}

server {
    listen 80;
    server_name hermes.example.com;
    return 301 https://$host$request_uri;
}
```

Get the certificate:

```bash
sudo certbot --nginx -d hermes.example.com
```

Then apply the same `.env` block shown in the [Caddy section](#caddy-recommended----automatic-tls).

> **If another proxy sits in front of nginx** (Cloudflare, a load balancer),
> it must also stream unbuffered. Cloudflare's proxy does not buffer
> `text/event-stream`, but "Rocket Loader" and some optimization features can
> interfere -- turn them off for this hostname if streaming misbehaves.

---

## The environment variables, and why each one matters

### Cookies: `HERMES_WEBUI_TRUST_FORWARDED_PROTO`

The session cookie gets the `Secure` flag only when the server believes the
connection is HTTPS. Behind a proxy, the server's own socket is plain HTTP --
TLS was terminated upstream -- so it cannot tell on its own.

`api/auth.py` decides in this order:

1. `HERMES_WEBUI_SECURE=1` (or `0`) -- explicit override, wins over everything.
2. A direct TLS socket (only when Hermes serves HTTPS itself, see below).
3. `X-Forwarded-Proto: https` -- **but only if
   `HERMES_WEBUI_TRUST_FORWARDED_PROTO=1` is set.**
4. Otherwise: not secure.

Step 3 is opt-in on purpose. `X-Forwarded-Proto` is a plain request header that
any client can send; trusting it unconditionally would let someone on a
plain-HTTP deployment forge it. Enable it only when a proxy *you run* sets it,
which is exactly the setup on this page.

If you would rather not think about it, `HERMES_WEBUI_SECURE=1` is equivalent
here and does not depend on a header.

### CSRF: `HERMES_WEBUI_TRUST_FORWARDED_HOST` and `proxy_set_header Host`

Hermes rejects state-changing requests whose `Origin` does not match the host
it believes it is serving. Behind a proxy there are two ways to make those
agree, and you want at least one:

- **`proxy_set_header Host $host;`** -- forward the public hostname. This alone
  is enough, and is why it is in the nginx block above.
- **`HERMES_WEBUI_TRUST_FORWARDED_HOST=1`** -- also honor `X-Forwarded-Host` /
  `X-Real-Host`. Useful when your proxy cannot rewrite `Host`.
- **`HERMES_WEBUI_ALLOWED_ORIGINS=https://hermes.example.com`** -- an explicit
  allowlist, as a last resort. Each entry must include the scheme.

A mismatch shows up as POSTs failing while GETs work: the page loads, the
session list appears, and sending a message returns an error.

### Client IP: `HERMES_WEBUI_TRUST_FORWARDED_FOR`

Without it, the login rate limiter sees every request as coming from the proxy
and rate-limits all users as one. Set it so `X-Forwarded-For` is honored.

> **Only enable the three `TRUST_FORWARDED_*` variables when a proxy you
> control sets those headers.** On a server reachable directly, they let a
> client claim any IP, host, or scheme it likes.

### Passkeys: forward the real `Host`

Passkey registration binds credentials to the hostname in the `Host` header
(`api/passkeys.py` derives the WebAuthn Relying Party ID from it). If the proxy
forwards `127.0.0.1`, passkeys register against `127.0.0.1` and then fail to
work from the public name. `proxy_set_header Host $host;` covers this too.

### Session lifetime: `HERMES_WEBUI_SESSION_TTL`

Already defaults to 30 days (`api/auth.py`: `SESSION_TTL = 86400 * 30`), so you
do **not** need to set this to stay logged in on a phone. Set it only to choose
a different window -- shorter for a shared machine, longer if 30 days is not
enough. The value is in seconds.

---

## Serving HTTPS without a proxy

Hermes can terminate TLS itself:

```bash
HERMES_WEBUI_TLS_CERT=/etc/letsencrypt/live/hermes.example.com/fullchain.pem
HERMES_WEBUI_TLS_KEY=/etc/letsencrypt/live/hermes.example.com/privkey.pem
HERMES_WEBUI_HOST=0.0.0.0
```

Both must be set or it falls back to plain HTTP. No `TRUST_FORWARDED_*`
variables are needed -- the server sees the TLS socket directly.

This is fine for a single-purpose box. A proxy is still the better default: it
renews certificates for you, and it lets you host anything else on the same
machine.

---

## Subpath mounts (`https://example.com/hermes/`)

Supported, with one requirement: **the proxy must strip the prefix.**

The frontend emits a `<base href>` derived from `location.pathname` and
resolves every API call relative to it (`static/index.html`, and the `api()`
wrapper in `static/workspace.js`). Mounted at `/hermes/`, the browser requests
`/hermes/api/sessions`. The server has no concept of a base path and only
answers `/api/sessions`, so the prefix has to come off in the proxy.

nginx -- note the **trailing slash on `proxy_pass`**, which is what performs
the strip:

```nginx
location /hermes/ {
    proxy_pass http://127.0.0.1:8787/;    # ← trailing slash strips /hermes/
    proxy_http_version 1.1;

    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection        "";

    proxy_buffering    off;
    proxy_cache        off;
    proxy_read_timeout 24h;
}
```

Caddy:

```caddyfile
example.com {
    handle_path /hermes/* {          # handle_path strips the prefix
        reverse_proxy 127.0.0.1:8787 {
            flush_interval -1
            transport http { read_timeout 24h }
        }
    }
}
```

Omitting the strip produces a page that loads its HTML but 404s every API call.

---

## "SSE appears to hang"

The most common failure after putting Hermes behind a proxy, and the reason
`proxy_buffering off` is called out three times on this page.

**Symptoms.** Any of these, alone or together:

- You send a message. Nothing appears for a long time, then the entire reply
  lands at once when the turn finishes.
- The reply never appears, and the request eventually times out.
- The session list does not refresh on its own.
- Approval prompts arrive late or not at all.
- Everything works over an SSH tunnel and only breaks through the proxy.

**Cause.** Hermes streams over Server-Sent Events. nginx's default
`proxy_buffering on` collects the response body and forwards it in blocks --
correct for a normal page, fatal for a stream whose entire value is arriving
incrementally. A short `proxy_read_timeout` (60s by default) causes the second
symptom: the proxy closes a stream that was legitimately idle between tokens.

These endpoints are all SSE and all affected
(full list in [`sse-streams.md`](sse-streams.md)):

```
GET /api/chat/stream
GET /api/session/stream
GET /api/sessions/events
GET /api/sessions/{id}/events
GET /api/sessions/gateway/stream
```

**Fix.** In the `location` block that proxies them:

```nginx
proxy_buffering    off;
proxy_cache        off;
proxy_read_timeout 24h;
proxy_http_version 1.1;
proxy_set_header Connection "";
```

**Confirm it is fixed.** A working stream drips one line at a time; a buffered
one prints nothing and then dumps everything at the end:

```bash
# Cookie name defaults to `hermes_session` (override:
# HERMES_WEBUI_COOKIE_NAME). Copy the value from your browser's dev tools.
curl -N -H 'Accept: text/event-stream' \
     -b 'hermes_session=<your-cookie-value>' \
     https://hermes.example.com/api/sessions/events
```

The server emits a `: keepalive` comment line every 30 seconds. On a working
stream those appear one at a time, so within a minute you should see two.
If the command sits silent and then flushes everything in a burst when you
interrupt it, buffering is still on somewhere between you and the server --
check every proxy in the chain, not just the last one.

---

## Enabling Web Push

Once HTTPS works, push is a toggle. It needs nothing installed and no
third-party account -- `api/push.py` implements VAPID (RFC 8292) and payload
encryption (RFC 8291) directly.

1. Open the WebUI over **https://** on the device you want notified.
2. **On iPhone/iPad, first add it to the Home Screen** (Share → Add to Home
   Screen) and open it from that icon. A Safari tab receives no push at all;
   this is an iOS platform limitation, not a Hermes one. Requires iOS 16.4+.
3. Settings → **Notifications** → enable **Web Push**. The browser asks for
   permission at this point, not on page load.
4. Press **Send test push**. If it arrives, the whole chain works.

You will then get a notification when an approval is waiting and when a turn
finishes, even with the browser closed.

**Optional.** RFC 8292 suggests publishing a contact address so a push service
operator can reach you. Only worth setting on a public deployment:

```bash
HERMES_WEBUI_VAPID_SUBJECT=mailto:you@example.com
```

**Back up the VAPID key.** It is generated on first use and stored at
`<state dir>/.vapid_key` (mode 0600). Its public half is embedded in every
subscription a browser has created, so replacing the file silently invalidates
all of them -- push keeps returning 403 and nothing tells you why. Include it
in your backups and carry it across upgrades and container rebuilds.

### If the toggle will not turn on

| Symptom | Cause |
|---|---|
| Toggle is disabled, or flips back to off | Page is not a secure context. Confirm the URL is `https://` and the certificate is valid. |
| Works on Android, nothing on iPhone | Opened as a Safari tab. Must be launched from the Home Screen icon. |
| Test push works, real ones never arrive | The push service dropped a stale subscription. Toggle off and on to re-subscribe. |
| Worked before an upgrade, silent after | `.vapid_key` was not preserved. Re-subscribe on each device. |

---

## Verifying it works

From the phone you intend to use, over the public URL:

- [ ] `https://` with a valid certificate, no browser warning
- [ ] Login succeeds and **survives a browser restart** (cookie was accepted)
- [ ] Send a message -- tokens appear **incrementally**, not in one block
- [ ] Session list updates on its own after a change
- [ ] Upload a file to the workspace (checks `client_max_body_size`)
- [ ] Open a workspace file and the embedded terminal
- [ ] "Add to Home Screen" is offered, and the installed app opens standalone
- [ ] Settings → Notifications → Web Push toggles **on**
- [ ] "Send test push" arrives
- [ ] Lock the phone, close the browser, trigger an approval from another
      device -- the notification still arrives

The last item is the real test. It is the one that only works over HTTPS, and
the reason this page exists.

---

## Hardening checklist

- [ ] `HERMES_WEBUI_HOST=127.0.0.1` -- the app itself should not be reachable
      except through the proxy
- [ ] Firewall allows only 22, 80, 443
- [ ] `HERMES_WEBUI_PASSWORD` set to something strong (or OIDC / trusted-header
      SSO configured)
- [ ] `TRUST_FORWARDED_*` enabled **only** because a proxy you run sets those
      headers
- [ ] `<state dir>/.vapid_key` and `~/.hermes/` included in backups
- [ ] Certificate auto-renewal tested (`certbot renew --dry-run`)

For SSO in front of the WebUI (Authelia, oauth2-proxy), see the trusted-header
auth section of [`.env.example`](../.env.example) -- and note the warning
there that `HERMES_WEBUI_TRUSTED_PROXY_CIDRS` must name your proxy's exact IP.

---

## See also

- [`remote-access.md`](remote-access.md) -- SSH tunnel and Tailscale, when you
  do not need a public hostname
- [`sse-streams.md`](sse-streams.md) -- the SSE endpoints and their contracts
- [`docker.md`](docker.md) -- container deployment
- [`troubleshooting.md`](troubleshooting.md) -- general diagnostics
