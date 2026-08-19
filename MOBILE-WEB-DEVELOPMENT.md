# Mobile Web Development — Analisa Codebase & Roadmap Refactor

> **Dokumen ini menjawab:** codebase apa ini, dibangun dengan tech stack apa, cara
> menjalankannya, apakah **sudah** bisa dideploy di VPS dan dipakai nyaman dari
> browser smartphone di semua mode layout — dan kalau belum sepenuhnya, apa
> strategi teknis serta fase-fase pengembangannya (mulai Fase 0 / MVP).
>
> **Metodologi:** analisa statis seluruh repo + **pengukuran empiris**. Server
> (`server.py`) benar-benar dibooting di environment ini, lalu dimuat dengan
> Chromium headless (Playwright) pada 5 viewport berbeda. Semua angka di dokumen
> ini adalah hasil pengukuran nyata, bukan estimasi. Bagian yang tidak bisa
> diverifikasi langsung ditandai eksplisit dengan **[belum terverifikasi]**.
>
> Tanggal analisa: 2026-08-19 · Commit dasar: `fc1dc3a`

---

## Daftar Isi

1. [Ringkasan Eksekutif — Jawaban Jujur](#1-ringkasan-eksekutif--jawaban-jujur)
2. [Codebase Ini Apa?](#2-codebase-ini-apa)
3. [Tech Stack](#3-tech-stack)
4. [Cara Menjalankan](#4-cara-menjalankan)
5. [Status Responsif Saat Ini — Bukti Pengukuran](#5-status-responsif-saat-ini--bukti-pengukuran)
6. [Analisa Gap: Apa yang Masih Kurang](#6-analisa-gap-apa-yang-masih-kurang)
7. [Strategi & Konsep Teknis Target](#7-strategi--konsep-teknis-target)
8. [Fase Pengembangan (Fase 0 → Fase 5)](#8-fase-pengembangan-fase-0--fase-5)
9. [Blueprint Deployment VPS](#9-blueprint-deployment-vps)
10. [Strategi Testing](#10-strategi-testing)
11. [Risiko, Trade-off, dan Non-Goals](#11-risiko-trade-off-dan-non-goals)
12. [Checklist Ringkas](#12-checklist-ringkas)

---

## 1. Ringkasan Eksekutif — Jawaban Jujur

### Pertanyaan: "Apakah bisa dideploy di VPS dan dibuka di browser smartphone secara user friendly dan responsive?"

**Jawaban singkat: YA, sudah bisa hari ini — untuk smartphone dan desktop.
TIDAK sepenuhnya untuk tablet portrait.** Ini bukan proyek yang perlu "dibangun
ulang agar mobile"; mobile sudah menjadi warga kelas satu di codebase ini. Yang
dibutuhkan adalah **penyempurnaan terarah**, bukan refactor besar.

Rincian jujurnya:

| Aspek | Status | Bukti |
|---|---|---|
| Deploy di VPS | ✅ **Sudah bisa** | `Dockerfile` + 3 varian compose, `ctl.sh` daemon, Nix flake + modul NixOS, `HERMES_WEBUI_HOST=0.0.0.0`, TLS opsional bawaan |
| Auth untuk paparan publik | ✅ **Matang** | PBKDF2-SHA256 600k iterasi, rate limiter login, cookie HttpOnly+SameSite=Lax+Secure, OIDC, passkey/WebAuthn, trusted-header proxy auth |
| Layout smartphone (≤640px) | ✅ **Sangat baik** | Drawer sidebar off-canvas, slide-over panel file, composer icon-only, target sentuh 44px, `100dvh`, `visualViewport` keyboard inset |
| PWA / "add to home screen" | ✅ **Ada** | `manifest.json` (standalone, portrait, shortcuts, maskable icon) + service worker pre-cache app shell |
| Layout desktop | ✅ **Baik** | Tiga panel, container queries, resize handle |
| **Layout tablet portrait (641–900px)** | ❌ **Ada bug nyata** | Panel workspace/file **tidak bisa dibuka sama sekali** — terverifikasi di 768px & 820px |
| Berfungsi tanpa internet publik (VPS air-gapped) | ⚠️ **Tidak** | 7 aset (Prism.js, xterm.js) di-load dari `cdn.jsdelivr.net` — terverifikasi gagal saat CDN diblokir |
| Notifikasi saat browser ditutup | ❌ **Belum ada** | Hanya `Notification` API + `showNotification` saat tab hidup; **tidak ada Web Push/VAPID** |
| Zoom / aksesibilitas mobile | ⚠️ **Sengaja dimatikan** | `user-scalable=no, maximum-scale=1` — melanggar WCAG 2.1 SC 1.4.4, dikunci oleh test |
| Panduan reverse proxy + TLS | ❌ **Tidak ada** | README eksplisit menyerahkan ini ke operator; hanya SSH tunnel & Tailscale yang didokumentasikan |
| Bahasa Indonesia di UI | ❌ **Belum ada** | 15 locale tersedia (`en, it, ja, ru, es, de, zh, zh-Hant, pt, ko, fr, cs, tr, pl, vi`) — tanpa `id` |
| Berat halaman | ⚠️ **Berat** | 5,5 MB mentah / **1,4 MB gzip**; `i18n.js` sendiri 477 KB gzip berisi 15 bahasa sekaligus |

### Kesimpulan praktis untuk Anda

Kalau tujuannya adalah **"deploy di VPS, buka dari HP, pakai semua fitur"** —
Anda bisa melakukannya **minggu ini** dengan Fase 0 (deployment hardening,
±1–2 hari kerja) tanpa menyentuh satu baris pun kode aplikasi. Fase 1–2
memperbaiki bug tablet dan menghilangkan ketergantungan CDN. Fase 3–5 adalah
yang mengubahnya dari "web app responsif yang bagus" menjadi terasa **seperti
aplikasi Claude di HP** (push notification, transisi native-feel, offline shell,
performa cold-start).

---

## 2. Codebase Ini Apa?

**Hermes WebUI** adalah **antarmuka web self-hosted untuk [Hermes Agent](https://hermes-agent.nousresearch.com/)**
— sebuah AI agent otonom yang berjalan persisten di server Anda, punya memori
lintas sesi, cron job terjadwal, sistem skill yang menulis dirinya sendiri, dan
akses lewat 10+ platform messaging.

WebUI ini adalah **lapisan presentasi**, bukan agent-nya. Ia memberi paritas
~1:1 dengan pengalaman Hermes CLI, tapi lewat browser.

### Bentuk aplikasinya

- **Layout tiga panel**: sidebar kiri (sesi + navigasi rail), tengah (chat),
  kanan (workspace file browser).
- **Composer footer** memuat kontrol model, profil, workspace, dan context ring
  (indikator token) — selalu terlihat saat mengetik.
- **Hermes Control Center** (launcher di bawah sidebar) menampung semua setting:
  cron, skills, memory, profiles, providers, kanban, insights, extensions.

### Skala repo (angka nyata)

| Komponen | Ukuran |
|---|---|
| `api/` (68 modul Python) | ~4,6 MB kode |
| `api/routes.py` | 1,23 MB — **223 route path eksak + 11 prefix** |
| `api/streaming.py` | 615 KB — mesin SSE + eksekusi agent |
| `api/config.py` / `api/models.py` | 481 KB / 485 KB |
| `static/` (17 file JS + 1 CSS) | 5,5 MB mentah |
| `static/ui.js` | 1,018 KB |
| `static/i18n.js` | 1,722 KB (15 bahasa) |
| `static/style.css` | 505 KB |
| `tests/` | **1.385 file test** |
| `CHANGELOG.md` | 1,95 MB |

Ini adalah proyek yang **sangat aktif dan matang** — bukan prototipe. Ada
`ARCHITECTURE.md` (85 KB), `TESTING.md` (78 KB), `ROADMAP.md`, `DESIGN.md`,
`docs/UIUX-GUIDE.md`, RFC directory, dan daftar kontributor yang panjang.

### Ketergantungan penting yang harus dipahami

WebUI **mengimpor modul internal Hermes Agent secara langsung** (`api/config.py`,
`api/providers.py`, `api/streaming.py`). README menyatakan eksplisit:

> "Running pinned older/newer combinations is **untested and unsupported**"

→ **Implikasi deployment:** WebUI dan hermes-agent harus di-upgrade sebagai
pasangan. Pin kedua versi bersamaan; jangan `latest` di satu sisi dan tag tetap
di sisi lain. (Pekerjaan pemisahan boundary dilacak di issue #1925 / #2491.)

---

## 3. Tech Stack

### Backend

| Lapisan | Teknologi | Catatan |
|---|---|---|
| HTTP server | **`http.server.ThreadingHTTPServer` (stdlib Python)** | Bukan Flask/FastAPI/Django. Tanpa framework, tanpa ASGI, tanpa uvicorn |
| Handler | `BaseHTTPRequestHandler`, `protocol_version = "HTTP/1.1"` | Thread per koneksi, `daemon_threads = True` |
| Bahasa | Python ≥ 3.11 (CI: 3.11–3.13) | |
| Dependensi runtime | **Hanya 2**: `pyyaml>=6.0`, `cryptography>=42.0` | Opsional: `edge-tts`, `psutil`, `python-docx`, `openpyxl`, `python-pptx` |
| Streaming | **Server-Sent Events (SSE)** | Dengan dukungan `Last-Event-ID` untuk resume koneksi terputus |
| Auth | PBKDF2-HMAC-SHA256 600.000 iterasi, session cookie, rate limiter, OIDC, WebAuthn/passkeys, trusted-header | `api/auth.py` (47 KB), `api/auth_oidc.py`, `api/passkeys.py` |
| TLS | Opsional bawaan (`ssl.PROTOCOL_TLS_SERVER`, min TLS 1.2) via `HERMES_WEBUI_TLS_CERT/KEY` | |
| Keamanan HTTP | CSP ketat, `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'` | `api/helpers.py` |
| Static serving | Cache in-memory + gzip level 6 + weak ETag + `Cache-Control: immutable` untuk URL ber-fingerprint | `_serve_static()` di `api/routes.py:17041` |
| MCP | `mcp_server.py` (25 KB) — expose WebUI sebagai MCP server | |
| Penyimpanan | Filesystem `~/.hermes/webui/` + SQLite (sesi terpadu) | `api/webui_session_db.py` |

### Frontend

| Lapisan | Teknologi | Catatan |
|---|---|---|
| Framework | **Tidak ada.** Vanilla JS klasik (bukan ES module) | Tanpa React/Vue/Svelte, **tanpa bundler, tanpa build step** |
| Styling | Satu file CSS 505 KB dengan CSS custom properties | Tema (`light`/`dark`/`system`) × skin (11 skin: `default`, `ares`, `mono`, `slate`, `poseidon`, `sisyphus`, `charizard`, `sienna`, `catppuccin`, `nous`, `geist-contrast`) |
| Layout modern | Flexbox, **CSS Container Queries** (6 blok `@container`), `100dvh`, `env(safe-area-inset-*)`, `content-visibility` | |
| Markdown | `smd.min.js` (streaming markdown, di-vendor lokal) | |
| Math | KaTeX 0.16.22 (di-vendor lokal di `static/vendor/katex/`) | |
| Syntax highlight | **Prism.js 1.29 — dari CDN jsdelivr** ⚠️ | |
| Terminal | **xterm.js 5.3 + addon fit/web-links — dari CDN jsdelivr** ⚠️ | |
| YAML | `js-yaml` (di-vendor lokal) | |
| i18n | `i18n.js`, 15 locale hardcoded dalam satu objek `LOCALES` | |
| PWA | `manifest.json` + `sw.js` (pre-cache app shell, tanpa cache API) | |
| Voice | Web Speech API (input) + Edge TTS server-side (output, opsional) | |

### Tooling & Packaging

| Area | Teknologi |
|---|---|
| Lint Python | **Ruff** — ruleset kurasi `E9`, `F`, `B`, di-scope hanya ke baris yang berubah (`scripts/ruff_lint.py`) |
| Lint JS | **ESLint 10** — *bukan* build step; hanya guard runtime-error atas `static/*.js` |
| Test | pytest + `pytest-timeout` + `pytest-asyncio` + `pytest-shard` — 1.385 file test |
| Test browser | Playwright + Chromium — 3 skrip (`tests/browser_smoke.py`, `browser_conversation_lifecycle.py`, `browser_historical_transcript_hydration.py`) |
| Build metadata | `pyproject.toml` + setuptools-scm; entry point `hermes-webui = bootstrap:main` |
| Container | `Dockerfile` (python:3.12-slim, SQLite dikompilasi ulang ke 3.53 karena bug WAL-reset) |
| Deklaratif | `flake.nix` + modul NixOS |
| CI | GitHub Actions: ruff + pytest ter-shard, browser smoke, Docker smoke, build multi-arch + GitHub Release saat tag |

---

## 4. Cara Menjalankan

### 4.1 Prasyarat

**Hermes Agent harus terpasang di host yang sama.** WebUI mengimpor modulnya
langsung. `bootstrap.py` akan mendeteksi agent di lokasi-lokasi ini:

```
$HERMES_WEBUI_AGENT_DIR
$HERMES_HOME/hermes-agent
../hermes-agent            (sibling dari repo ini)
~/.hermes/hermes-agent
~/hermes-agent
/usr/local/lib/hermes-agent
```

Kalau tidak ketemu, bootstrap menawarkan menjalankan installer resmi
(`https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh`).

> **Catatan terukur:** server **tetap boot** tanpa hermes-agent (saya sudah
> membuktikannya — HTTP 200, UI ter-render penuh), tapi dalam mode degraded:
> tidak bisa menjalankan turn agent.

### 4.2 Jalankan lokal (paling sederhana)

```bash
git clone https://github.com/nesquena/hermes-webui.git hermes-webui
cd hermes-webui
python3 bootstrap.py          # foreground; hentikan dengan Ctrl-C
# atau
./start.sh                    # launcher shell, mencetak perintah SSH tunnel bila via SSH
```

Buka `http://127.0.0.1:8787`.

### 4.3 Sebagai daemon (untuk VPS / homelab)

```bash
./ctl.sh start                        # background, PID di ~/.hermes/webui.pid
./ctl.sh status                       # PID, uptime, host/port, path log, /health
./ctl.sh logs --lines 100             # tail ~/.hermes/webui.log
./ctl.sh restart
./ctl.sh stop                         # SIGTERM lalu SIGKILL

HERMES_WEBUI_HOST=0.0.0.0 ./ctl.sh start   # override inline
```

> ⚠️ **Penting:** `./ctl.sh stop` **hanya** bisa menghentikan proses yang ia
> jalankan sendiri (hanya `ctl.sh start` yang menulis PID file). Untuk
> `bootstrap.py`/`start.sh`, cari PID via `lsof -i :8787` lalu `kill`.

### 4.4 Docker

```bash
cp .env.docker.example .env    # isi HERMES_WEBUI_PASSWORD dsb.
docker compose up -d
# http://localhost:8787
```

Tiga varian tersedia:

| File | Isi |
|---|---|
| `docker-compose.yml` | 1 kontainer — WebUI menjalankan agent in-process (**disarankan**) |
| `docker-compose.two-container.yml` | agent + webui terpisah |
| `docker-compose.three-container.yml` | agent + webui + dashboard |

> ⚠️ **Batasan terdokumentasi (#681):** pada setup dua kontainer, tool yang
> dipicu dari WebUI berjalan di **kontainer WebUI**, bukan kontainer agent.

### 4.5 Nix / NixOS

```bash
nix run .#hermes-webui
```
Modul NixOS tersedia di `flake.nix`. README menyatakan konfigurasi reverse proxy
dan TLS **sengaja diserahkan** ke modul deployment Anda sendiri.

### 4.6 Environment variable kunci

| Variabel | Default | Fungsi |
|---|---|---|
| `HERMES_WEBUI_HOST` | `127.0.0.1` | Bind address. **Wajib `0.0.0.0` untuk akses dari luar** |
| `HERMES_WEBUI_PORT` | `8787` | Port |
| `HERMES_WEBUI_PASSWORD` | — | Aktifkan password auth. **Wajib bila host ≠ 127.0.0.1** |
| `HERMES_WEBUI_STATE_DIR` | `~/.hermes/webui` | Sesi, workspace, settings |
| `HERMES_WEBUI_DEFAULT_WORKSPACE` | — | Workspace awal |
| `HERMES_WEBUI_TLS_CERT` / `_TLS_KEY` | — | TLS langsung tanpa reverse proxy |
| `HERMES_WEBUI_SESSION_TTL` | — | Umur cookie sesi (clamp 60 dtk – 1 thn) |
| `HERMES_WEBUI_TRUST_FORWARDED_PROTO` | `0` | Percayai `X-Forwarded-Proto: https` — **wajib `1` di belakang reverse proxy** agar cookie `Secure` terpasang |
| `HERMES_WEBUI_TRUST_FORWARDED_FOR` | `0` | Percayai `X-Forwarded-For` (untuk rate limiter per-IP) |
| `HERMES_WEBUI_TRUSTED_PROXY_CIDRS` | — | Whitelist CIDR proxy |
| `HERMES_WEBUI_TRUSTED_AUTH_HEADER` | — | SSO via header (Authelia/Cloudflare Access/oauth2-proxy) |
| `HERMES_WEBUI_ALLOWED_ORIGINS` | — | Whitelist CORS |
| `HERMES_WEBUI_CSP_CONNECT_EXTRA` | — | Perlebar `connect-src` CSP |
| `HERMES_WEBUI_PASSKEY` | — | Feature flag passkey/WebAuthn |

### 4.7 Menjalankan test

```bash
./scripts/test.sh                              # seluruh suite
./scripts/test.sh tests/test_mobile_layout.py -v
npm run lint:runtime                           # ESLint guard atas static/*.js
python tests/browser_smoke.py                  # butuh playwright + chromium
```

---

## 5. Status Responsif Saat Ini — Bukti Pengukuran

Saya membooting `server.py` sungguhan lalu memuatnya di Chromium headless pada
lima viewport. Berikut hasil mentahnya.

### 5.1 Matriks hasil

| Viewport | Overflow horizontal | Sidebar | Panel Workspace | Hamburger | Tombol Files diklik → | Target sentuh <40px |
|---|---|---|---|---|---|---|
| **375×667** (iPhone SE) | ❌ tidak ada | drawer off-canvas | slide-over | ✅ | — | 17 |
| **393×852** (iPhone 14 Pro) | ❌ tidak ada | drawer off-canvas | slide-over | ✅ | ✅ **terbuka** (w=300, left=93) | 17 |
| **768×1024** (iPad portrait) | ❌ tidak ada | in-flow | ⛔ `display:none` | ✅ | ❌ **tidak terjadi apa-apa** | 19 |
| **820×1180** (iPad Air portrait) | ❌ tidak ada | in-flow | ⛔ `display:none` | ✅ | ❌ **tidak terjadi apa-apa** | — |
| **1024×768** (iPad landscape) | ⚠️ 14 px | in-flow | ✅ terlihat | — | ✅ terbuka (w=278) | 34 |
| **1440×900** (desktop) | ⚠️ 14 px | in-flow | ✅ terlihat | — | ✅ terbuka (w=300) | 34 |

### 5.2 Yang sudah bagus (dan patut diapresiasi)

Layout telepon **bukan afterthought**. `docs/UIUX-GUIDE.md` menuliskannya
sebagai kebijakan, dan implementasinya nyata:

- **Sidebar off-canvas** — `position:fixed; width:100vw; transform:translateX(-100%)`
  dengan transisi 250 ms, plus backdrop dan *edge guard* 24 px untuk gestur swipe.
- **Slide-over panel file** dari kanan (`min(300px, 100vw)`).
- **Target sentuh 44 px** — ada 30 deklarasi eksplisit `min-height:44px`/`min-width:44px`.
- **`100dvh`** dipakai (bukan `100vh`) — dikunci oleh test `test_100dvh_viewport_height`.
- **Kompensasi keyboard virtual** — `_syncKeyboardBottomInset()` membaca
  `window.visualViewport`, menghitung `--keyboard-bottom-inset`, dan **secara
  benar mengabaikan state pinch-zoom** (`vv.scale != 1`) agar tidak salah baca.
- **Guard reflow PWA** (#3976) — toggle class satu frame untuk memaksa repaint
  setelah geometri viewport berubah.
- **`overflow-x: clip` bukan `hidden`** pada `.layout` dan `.messages-inner`,
  dengan komentar 10 baris yang menjelaskan bahwa `hidden` memaksa `overflow-y`
  jadi scroll container sehingga `min-height:auto` runtuh ke 0 dan transkrip
  jadi tidak bisa di-scroll (bug #4856). Ini level pemahaman CSS yang tinggi.
- **`touch-action: pan-y`**, `overscroll-behavior-y: contain`,
  `-webkit-overflow-scrolling: touch` pada scroller transkrip.
- **`content-visibility: auto`** pada baris user (dengan pengecualian untuk
  segmen assistant yang sedang streaming — bug #5637).
- **Composer adaptif** — di ≤640px chip model/profil/workspace jadi icon-only
  44×44, dan yang tidak muat dipindahkan ke `.composer-mobile-config-panel`.
  Ada juga *fit-based collapse* di JS yang mengukur overflow nyata
  (`.composer-footer.cf-icons`), bukan sekadar breakpoint.
- **PWA lengkap** — manifest standalone/portrait + shortcut "New chat" + ikon
  maskable, service worker yang **sengaja tidak** meng-cache `./` maupun aset
  login (agar submit password tidak gagal karena respons basi).
- **SSE tahan jaringan buruk** — dukungan `Last-Event-ID` + `after_seq`, penting
  di jaringan seluler yang sering putus.

### 5.3 Cakupan CSS responsif — angka

```
Total style.css              : 515.529 byte
Byte di dalam @media         :  31.290 byte  (6,1%)
Jumlah blok @media           :  71
Blok terbesar (max-width:640px): 10.972 byte, ~93 rule
```

Breakpoint yang dipakai, terurut:
`340, 420, 520, 560, 600, 640, 700, 768, 900, 1400, 1600, 1800` px
— plus `(pointer:coarse)`, `(hover:none)`, `(hover:hover)`,
`(prefers-reduced-motion)`, `(display-mode:standalone)`.

**Interpretasi jujur:** 6,1% itu *bukan* pertanda buruk — sebagian besar layout
memakai flexbox intrinsik dan container query yang memang tidak butuh media
query. Tapi **12 breakpoint yang tersebar tanpa token** adalah utang teknis
nyata: itulah akar bug tablet di §6.1. Tidak ada satu pun sumber kebenaran
tentang "apa itu phone / tablet / desktop".

---

## 6. Analisa Gap: Apa yang Masih Kurang

Diurutkan dari dampak tertinggi.

### 6.1 🔴 BUG: Panel workspace tidak bisa dibuka di tablet portrait (641–900px)

**Bukti terukur.** Pada 768px dan 820px: tombol `.composer-workspace-files-btn`
terlihat dan bisa diklik, tapi setelah diklik `.rightpanel` tetap
`display:none`. Di 393px, klik yang sama menghasilkan `OPEN w=300 left=93`.

**Akar masalah** (`static/style.css`):

```css
/* baris ~2817 — aturan dasar */
.rightpanel{ width:300px; display:flex; ... }

/* baris ~3001 — menang karena lebih akhir di file */
@media(max-width:900px){
  .rightpanel{ display:none }               /* ← disembunyikan di 641–900px */
  .workspace-toggle-btn,.mobile-files-btn{ display:inline-flex!important; }
}

/* baris ~3059–3097 — HANYA berlaku ≤640px */
@media(max-width:640px){
  .rightpanel{ display:flex!important; position:fixed; right:-300px; ... }
  .rightpanel.mobile-open{ right:0!important; }   /* ← satu-satunya di file */
}
```

`.rightpanel.mobile-open` hanya muncul **sekali** di seluruh CSS, di dalam blok
`≤640px`. Sementara `boot.js` memakai `_isCompactWorkspaceViewport()` =
`max-width: 900px` sebagai definisi "compact". **JS pikir 641–900px itu mobile;
CSS pikir bukan.** Hasilnya: JS menambahkan class `mobile-open`, tapi tidak ada
aturan CSS yang menanggapinya di band itu.

**Dampak:** di iPad portrait, iPad mini, tablet Android, dan jendela browser
desktop yang di-split-screen — **file browser hilang total tanpa jalan alternatif**.

### 6.2 🔴 Ketergantungan CDN eksternal (jsdelivr)

**Bukti terukur.** Saat memuat halaman di environment tanpa akses jsdelivr,
**7 request gagal** di *setiap* viewport:

```
prismjs@1.29.0/components/prism-core.min.js
prismjs@1.29.0/plugins/autoloader/prism-autoloader.min.js
prismjs@1.29.0/themes/prism-tomorrow.min.css
xterm@5.3.0/lib/xterm.js
xterm@5.3.0/css/xterm.css
xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js
xterm-addon-web-links@0.9.0/lib/xterm-addon-web-links.js
```

CSP-nya pun sudah mengizinkan `https://cdn.jsdelivr.net` di `script-src`,
`style-src`, dan `worker-src` — jadi ini desain yang disengaja, bukan kelalaian.

**Dampak:**
- Syntax highlighting mati dan terminal embedded tidak bisa jalan pada VPS
  air-gapped / di balik firewall keluar yang ketat.
- Round-trip TLS tambahan ke host pihak ketiga di jaringan seluler — biaya
  latensi nyata pada koneksi 4G Indonesia.
- Service worker **tidak bisa** meng-cache-nya (lintas origin), jadi mode
  offline PWA otomatis pincang.
- Permukaan supply-chain: satu origin eksternal yang dipercaya penuh menjalankan
  skrip di halaman ter-autentikasi.

Ironisnya, KaTeX, js-yaml, dan smd sudah di-vendor lokal di `static/vendor/` —
polanya sudah ada, tinggal diterapkan ke dua sisanya.

### 6.3 🟠 Payload awal berat untuk perangkat mobile

Terukur (gzip level 6, sama seperti yang dikirim server):

| File | Mentah | Gzip |
|---|---|---|
| `i18n.js` | 1.722 KB | **477 KB** |
| `ui.js` | 1.018 KB | 272 KB |
| `panels.js` | 625 KB | 151 KB |
| `sessions.js` | 436 KB | 112 KB |
| `messages.js` | 434 KB | 110 KB |
| `style.css` | 505 KB | 95 KB |
| `boot.js` | 172 KB | 48 KB |
| `index.html` | 216 KB | 41 KB |
| lain-lain | ~500 KB | ~126 KB |
| **TOTAL** | **5.494 KB** | **1.399 KB** |

Semua 15 skrip di-load dengan `defer` (bagus — non-blocking), dan service worker
sudah pre-cache app shell (kunjungan berikutnya jauh lebih ringan).
**Tapi cold start di HP kelas menengah harus mem-parse + meng-eksekusi ~5,5 MB
JavaScript.** Parsing JS adalah biaya CPU, dan gzip tidak menolongnya sama sekali.

**Target termudah: `i18n.js` — 477 KB gzip untuk 15 bahasa, padahal user
memakai satu.** Memecahnya per-locale langsung menghemat **~440 KB gzip (31%
dari total payload)** tanpa menyentuh arsitektur.

### 6.4 🟠 Tidak ada Web Push — notifikasi mati saat browser ditutup

Yang ada saat ini (`static/messages.js:9155–9213`):
- `Notification.requestPermission()`
- `new Notification(...)`
- `registration.showNotification(...)`

Yang **tidak ada** di seluruh repo: `PushManager`, `pushsubscriptionchange`,
VAPID, endpoint subscription server-side.

**Konsekuensi:** semua notifikasi hanya berfungsi selama tab/PWA masih hidup di
memori. Kalau Anda mengirim tugas panjang ke agent lalu menutup browser dan
mengunci HP, **Anda tidak akan diberi tahu saat selesai** — Anda harus membuka
kembali dan mengecek manual.

Ini adalah **satu-satunya gap paling penting** untuk mencapai rasa "seperti
aplikasi Claude di HP". Agent yang berjalan lama tanpa notifikasi asinkron
kehilangan sebagian besar nilainya di mobile.

### 6.5 🟠 Zoom dimatikan (aksesibilitas)

```html
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
```

Dikunci oleh `tests/test_mobile_layout.py::test_viewport_disables_page_zoom_for_native_pwa_shell`.
Rasionalnya (dari docstring test): mencegah PWA terinstal "rubber-band into
browser-style page zoom".

**Masalahnya:** meta tag ini berlaku untuk **semua** konteks, termasuk tab
browser biasa — bukan hanya PWA terinstal. Pengguna dengan penglihatan terbatas
tidak bisa pinch-zoom untuk membaca output kode. Ini melanggar **WCAG 2.1 SC
1.4.4 (Resize Text, Level AA)**.

Solusi yang benar: `user-scalable=yes` sebagai default, lalu matikan zoom
**hanya di mode standalone** lewat JS yang menulis ulang meta tag saat
`matchMedia('(display-mode: standalone)').matches` bernilai true.

### 6.6 🟡 `viewport-fit=cover` absen, padahal CSS memakai `env(safe-area-inset-*)`

CSS punya 7 pemakaian `env(safe-area-inset-*)`:
```css
padding-left: max(10px, env(safe-area-inset-left, 0));
--app-titlebar-safe-top: env(safe-area-inset-top, ...);
```

Tapi `viewport-fit=cover` **tidak ada** di HTML — dan ketidakhadirannya juga
dikunci oleh test (`assert 'viewport-fit=cover' not in HTML`).

**Fakta spesifikasi:** tanpa `viewport-fit=cover`, `env(safe-area-inset-*)`
selalu bernilai **0** di browser. Jadi seluruh `max(10px, env(...))` di atas
selalu jatuh ke fallback `10px`, dan variabel safe-area tidak pernah aktif di
mode browser biasa.

Konsekuensinya kelihatan **di landscape pada HP bernotch/Dynamic Island**:
sisi kiri/kanan konten bisa tertutup cutout kamera. Di PWA terinstal, ini
sebagian tertutupi oleh `apple-mobile-web-app-status-bar-style: black-translucent`,
tapi hanya untuk iOS, hanya untuk sisi atas, dan hanya saat terinstal.

Ini adalah **keputusan sadar dengan trade-off yang terdokumentasi**, bukan bug —
tapi trade-off-nya patut ditinjau ulang untuk penggunaan landscape.

### 6.7 🟡 Fitur yang hilang di layar kecil

Dari audit `display:none` di dalam blok `@media (max-width: …)`:

| Fitur | Hilang di | Ada alternatif? |
|---|---|---|
| `#btnSavedPrompts` (Saved prompts) | ≤640px | ❌ **Tidak** — komentar CSS: "desktop-only affordance" |
| `#outlineToggleBtn` + `#outlinePanelWrapper` | ≤900px | ❌ Tidak |
| `.markdown-table-sort-indicator`, `.markdown-table-filter` | ≤640px | ❌ Tidak |
| `.topbar-meta` | ≤640px | ⚠️ Sebagian (di drawer) |
| `.ctx-indicator-wrap` | ≤640px | ✅ Ya (composer mobile config panel) |
| chip model/reasoning/toolsets | ≤640px | ✅ Ya (composer mobile config panel) |
| `.rightpanel` | ≤900px | ✅ ≤640 · ❌ **641–900** (lihat §6.1) |
| `.approval-kbd` | ≤640px | ✅ N/A (hint keyboard) |

Anda meminta **"mengakses semua fitur dan pengaturan via browser smartphone"**.
Tiga item pertama di tabel itu adalah **fitur yang benar-benar tidak bisa
dijangkau** dari HP saat ini.

### 6.8 🟡 Tidak ada test browser untuk viewport mobile

`tests/browser_smoke.py` memuat halaman di Chromium headless dan gagal bila ada
console error — bagus, tapi:

```bash
$ grep -n 'viewport|is_mobile|device' tests/browser_*.py
(tidak ada hasil)
```

Semua browser test berjalan di viewport default desktop. Sementara **1.385 test**
mobile sebagian besar adalah **assertion statis terhadap teks CSS/JS** —
misalnya `assert re.search(r'\.messages\{[^}]*touch-action:\s*pan-y', CSS)`.

Test seperti itu memverifikasi "aturan CSS ini tertulis", bukan "elemen ini
benar-benar terlihat dan bisa diklik di 768px". **Inilah persis sebabnya bug
§6.1 lolos**: kedua aturan CSS-nya ada dan valid; yang salah adalah interaksi
kaskadenya pada lebar tertentu — sesuatu yang hanya browser sungguhan bisa lihat.

### 6.9 🟡 Tidak ada panduan reverse proxy / TLS

README menyatakan eksplisit:
> "Keep reverse proxy and TLS configuration in your surrounding deployment
> module because those details are deployment-specific."

Yang didokumentasikan hanya SSH tunnel dan Tailscale. Untuk **VPS dengan domain
publik**, tidak ada satu pun contoh konfigurasi nginx/Caddy — padahal:

- **SSE butuh konfigurasi khusus**: `proxy_buffering off`, `X-Accel-Buffering: no`,
  `proxy_read_timeout` panjang. Tanpa ini, streaming chat **akan tersendat atau
  terputus** di belakang nginx default. Ini jebakan klasik yang akan langsung
  Anda temui.
- Passkey/WebAuthn **mensyaratkan HTTPS** (kecuali di localhost).
- Cookie `Secure` hanya terpasang bila `HERMES_WEBUI_TRUST_FORWARDED_PROTO=1`.

**Kabar baik:** wrapper `api()` di `static/workspace.js:1` sudah menangani
sub-path dengan benar —
`const rel = path.startsWith('/') ? path.slice(1) : path;` lalu resolve relatif
ke `document.baseURI`. Komentarnya bahkan menyebut "supports subpath mounts".
Jadi mount di `https://domain.com/hermes/` **bisa berfungsi** selama proxy
menghapus prefix. Sisi server tidak punya `BASE_PATH`/`SCRIPT_NAME`, jadi proxy
**wajib** melakukan strip.

### 6.10 🟡 Overflow horizontal 14px di desktop/laptop

Terukur di 1024px dan 1440px (bukan di mobile): `document.scrollWidth` melebihi
`clientWidth` sebesar 14px. Penyebabnya `DIV.panel-actions` di dalam
`.rightpanel` — anak-anaknya (`#btnClearPreview`, `#btnWorkspacePrefs`) meluber
~190px melewati kontainer; `.rightpanel` punya `overflow:hidden` sehingga hanya
14px yang bocor ke dokumen. Dampaknya kecil, tapi ini gejala dari
`.panel-actions` yang tidak punya `flex-wrap`/`min-width:0`.

### 6.11 🟢 Model konkurensi `ThreadingHTTPServer` + SSE

`ThreadingHTTPServer` membuat **satu thread OS per koneksi**, dan koneksi SSE
bersifat long-lived. Tidak ada cap thread eksplisit di codebase.

**Penilaian jujur:** untuk **VPS pribadi 1 pengguna** — yang persis kasus Anda —
ini **sama sekali bukan masalah**. Beberapa tab × beberapa SSE stream = puluhan
thread; Linux menanganinya dengan santai. Ini baru jadi kendala pada skenario
multi-user puluhan orang, dan itu di luar tujuan proyek ini. Saya mencatatnya
demi kelengkapan, bukan sebagai item kerja.

### 6.12 🟢 Bahasa Indonesia belum tersedia

15 locale: `en, it, ja, ru, es, de, zh, zh-Hant, pt, ko, fr, cs, tr, pl, vi`.
Tidak ada `id`. Relevan langsung dengan tujuan "user friendly" Anda, dan
menambahkannya adalah pekerjaan data murni — tanpa risiko arsitektural.

---

## 7. Strategi & Konsep Teknis Target

### 7.1 Prinsip pemandu

1. **Jangan rewrite. Ini codebase matang dengan 1.385 test.** Menukar vanilla JS
   ke React akan membuang ribuan jam kerja dan memperkenalkan build step yang
   secara eksplisit ditolak proyek ini (`package.json`: *"NOT a build step —
   the app remains pure Python + vanilla JS with no bundler"*). Hormati batasan
   itu; ia adalah alasan proyek ini bisa di-deploy hanya dengan `python3 bootstrap.py`.

2. **Perbaiki dulu yang rusak, baru tambah yang baru.** Bug tablet (§6.1) adalah
   ~15 baris CSS. Itu memberi keuntungan lebih besar per jam kerja dibanding
   fitur apa pun.

3. **Satu sumber kebenaran untuk breakpoint.** 12 breakpoint tersebar tanpa
   token adalah akar bug §6.1. Wajib ada kontrak tunggal yang dipakai CSS *dan* JS.

4. **Progressive enhancement, bukan mobile-only.** Setiap perbaikan harus tetap
   menjaga desktop utuh. Test regresi desktop harus tetap hijau.

5. **Ukur, jangan tebak.** Setiap fase punya kriteria penerimaan yang bisa
   diverifikasi di browser sungguhan, bukan lewat assertion teks CSS.

### 7.2 Kontrak breakpoint (fondasi seluruh pekerjaan)

Definisikan **satu** kontrak, dipakai bersama oleh CSS dan JS:

```css
/* static/style.css — di :root, paling atas file */
:root{
  --bp-phone:      640px;   /* ≤640  : satu kolom, drawer, slide-over        */
  --bp-tablet:     1024px;  /* 641–1024 : dua kolom, panel kanan slide-over  */
  --bp-desktop:    1025px;  /* ≥1025 : tiga kolom penuh                      */
}
```

CSS custom property tidak bisa dipakai langsung di `@media`, jadi pasangkan
dengan konstanta JS yang **diuji agar selalu sinkron**:

```js
// static/boot.js
const BP = Object.freeze({ PHONE: 640, TABLET: 1024 });
const isPhone   = () => matchMedia(`(max-width:${BP.PHONE}px)`).matches;
const isTablet  = () => matchMedia(`(min-width:${BP.PHONE + 1}px) and (max-width:${BP.TABLET}px)`).matches;
const isDesktop = () => matchMedia(`(min-width:${BP.TABLET + 1}px)`).matches;
const isCompact = () => !isDesktop();   // phone ATAU tablet → chrome overlay
```

Lalu satu test yang mem-parse kedua file dan memastikan angkanya identik. Test
inilah yang akan mencegah bug §6.1 terulang.

### 7.3 Arsitektur layout target

```
┌──────────────────────────────────────────────────────────────────┐
│ PHONE  ≤640px                                                    │
│  ┌────────────────────────────┐                                  │
│  │ Titlebar [☰]  Judul  [+][⟳]│  52px                            │
│  ├────────────────────────────┤                                  │
│  │                            │                                  │
│  │   Transkrip (1 kolom)      │  100dvh - titlebar - composer     │
│  │                            │                                  │
│  ├────────────────────────────┤                                  │
│  │ Composer (chip icon-only)  │  + --keyboard-bottom-inset        │
│  └────────────────────────────┘                                  │
│  Sidebar  → drawer kiri (100vw, transform)                        │
│  Workspace→ slide-over kanan (min(300px,100vw))                   │
├──────────────────────────────────────────────────────────────────┤
│ TABLET 641–1024px    ← BAND YANG DIPERBAIKI DI FASE 1            │
│  ┌──────┬─────────────────────┐                                  │
│  │ Side │  Transkrip          │  Sidebar in-flow (280–320px)     │
│  │ bar  │                     │  Workspace → slide-over kanan    │
│  │      │  Composer           │  (LEBAR: min(380px, 60vw))       │
│  └──────┴─────────────────────┘                                  │
├──────────────────────────────────────────────────────────────────┤
│ DESKTOP ≥1025px                                                  │
│  ┌──────┬───────────────┬─────┐  Tiga panel in-flow              │
│  │ Side │  Transkrip    │ Wor │  keduanya bisa di-collapse       │
│  │ bar  │  Composer     │ ksp │                                  │
│  └──────┴───────────────┴─────┘                                  │
└──────────────────────────────────────────────────────────────────┘
```

Perubahan kuncinya: **band tablet memakai chrome overlay yang sama dengan phone
untuk panel kanan**, tapi mempertahankan sidebar in-flow. Ini menghilangkan
"tanah tak bertuan" antara 641–900px sekaligus memperbaiki §6.1.

### 7.4 Konsep "terasa seperti aplikasi Claude di HP"

Yang membuat sebuah web app terasa native di HP, terurut menurut dampak:

| # | Elemen | Status di Hermes | Fase |
|---|---|---|---|
| 1 | Instalasi ke home screen, buka fullscreen | ✅ Sudah ada | — |
| 2 | Cold start cepat, tanpa layar putih | ⚠️ 1,4 MB gzip | 4 |
| 3 | **Notifikasi saat app ditutup** | ❌ Belum ada | 3 |
| 4 | Scroll 60 fps, tanpa jank | ✅ Sudah baik | — |
| 5 | Komposer stabil saat keyboard muncul | ✅ Sudah baik | — |
| 6 | Bottom sheet, bukan modal desktop | ⚠️ Sebagian | 2 |
| 7 | Gestur swipe (buka drawer, kembali) | ⚠️ Ada edge guard, belum penuh | 2 |
| 8 | Shell offline + banner koneksi | ⚠️ SW ada, CDN merusaknya | 1, 4 |
| 9 | Semua fitur terjangkau | ⚠️ 3 fitur hilang | 2 |
| 10 | Bahasa pengguna | ❌ Belum ada `id` | 2 |
| 11 | Haptic feedback (`navigator.vibrate`) | ❌ Belum ada | 5 |
| 12 | Transisi halaman (View Transitions API) | ❌ Belum ada | 5 |

---

## 8. Fase Pengembangan (Fase 0 → Fase 5)

Setiap fase bisa dirilis mandiri. Estimasi untuk satu pengembang yang sudah
paham codebase.

---

### FASE 0 — MVP: Deploy di VPS, akses dari HP, aman

> **Tujuan:** akhir fase ini, Anda membuka `https://hermes.domain-anda.com` dari
> Chrome/Safari di HP, login, mengobrol dengan agent, dan meng-install-nya ke
> home screen.
>
> **Kode aplikasi yang diubah: NOL.** Ini murni kerja deployment.
>
> **Estimasi: 1–2 hari** · **Prasyarat: tidak ada**

#### 0.1 Siapkan VPS

- Ubuntu 22.04/24.04 LTS, minimal **2 vCPU / 4 GB RAM / 40 GB SSD**
  (agent + model client + WebUI; laporan komunitas #2364 menyebut footprint
  lokal ~1,7 GB di ARM64 dengan inferensi cloud).
- Buat user non-root, aktifkan SSH key-only, matikan password login.
- `ufw`: izinkan hanya 22, 80, 443. **Jangan pernah** buka 8787 ke publik.
- Arahkan DNS A record → IP VPS.

#### 0.2 Install Hermes Agent + WebUI

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
git clone https://github.com/nesquena/hermes-webui.git ~/hermes-webui
cd ~/hermes-webui && python3 bootstrap.py --foreground --no-browser   # verifikasi sekali
```

#### 0.3 Konfigurasi environment

```bash
# ~/hermes-webui/.env
HERMES_WEBUI_HOST=127.0.0.1                 # ← tetap loopback; nginx yang menghadap publik
HERMES_WEBUI_PORT=8787
HERMES_WEBUI_PASSWORD=<passphrase-panjang-acak>
HERMES_WEBUI_STATE_DIR=/home/hermes/.hermes/webui
HERMES_WEBUI_TRUST_FORWARDED_PROTO=1        # ← WAJIB, agar cookie Secure terpasang
HERMES_WEBUI_TRUST_FORWARDED_FOR=1          # ← agar rate limiter melihat IP asli
HERMES_WEBUI_TRUSTED_PROXY_CIDRS=127.0.0.1/32
HERMES_WEBUI_SESSION_TTL=2592000            # 30 hari — agar tidak login ulang terus di HP
```

> **Kenapa `HERMES_WEBUI_HOST=127.0.0.1` dan bukan `0.0.0.0`?** Dengan reverse
> proxy, port 8787 tidak perlu terekspos sama sekali. Ini menghilangkan seluruh
> kelas serangan "seseorang menemukan port 8787 Anda". Dokumentasi resmi
> menyarankan `0.0.0.0` karena mengasumsikan Tailscale; untuk VPS publik,
> loopback + proxy lebih aman.

#### 0.4 systemd unit

```ini
# /etc/systemd/system/hermes-webui.service
[Unit]
Description=Hermes WebUI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=hermes
WorkingDirectory=/home/hermes/hermes-webui
EnvironmentFile=/home/hermes/hermes-webui/.env
ExecStart=/usr/bin/python3 bootstrap.py --foreground --no-browser
Restart=always
RestartSec=5
# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=/home/hermes/.hermes /home/hermes/workspace

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now hermes-webui
```

#### 0.5 nginx + TLS — **konfigurasi SSE adalah bagian kritisnya**

```nginx
server {
    listen 443 ssl http2;
    server_name hermes.domain-anda.com;

    ssl_certificate     /etc/letsencrypt/live/hermes.domain-anda.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/hermes.domain-anda.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 100M;          # upload file ke workspace

    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_http_version 1.1;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;   # ← dibaca oleh api/auth.py
        proxy_set_header Connection        "";        # ← keep-alive untuk SSE

        # ═══ WAJIB UNTUK SSE ═══
        # Tanpa tiga baris ini, streaming chat akan tersendat atau mati.
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 24h;
        # ═══════════════════════
    }
}

server {
    listen 80;
    server_name hermes.domain-anda.com;
    return 301 https://$host$request_uri;
}
```

Alternatif Caddy (buffering-off adalah default-nya, jadi jauh lebih ringkas):

```caddyfile
hermes.domain-anda.com {
    reverse_proxy 127.0.0.1:8787 {
        flush_interval -1        # streaming tanpa buffer
        transport http { read_timeout 24h }
    }
}
```

```bash
sudo certbot --nginx -d hermes.domain-anda.com   # bila memakai nginx
```

#### 0.6 Verifikasi dari HP

Checklist penerimaan Fase 0:

- [ ] `https://hermes.domain-anda.com` memuat halaman login di Chrome Android & Safari iOS
- [ ] Login berhasil; refresh halaman **tidak** meminta login ulang (cookie `Secure` terpasang)
- [ ] Kirim pesan → **token muncul streaming karakter-per-karakter**, tidak muncul sekaligus di akhir *(ini tes SSE-nya)*
- [ ] Kunci HP 30 detik, buka lagi → stream lanjut atau pulih otomatis (`Last-Event-ID`)
- [ ] "Add to Home Screen" → app terbuka fullscreen tanpa address bar
- [ ] Rotate ke landscape → tidak ada horizontal scroll
- [ ] Buka drawer sidebar (☰) → sesi bisa dipilih
- [ ] Buka Control Center → panel settings bisa di-scroll dan diubah
- [ ] `curl -I https://…` menunjukkan header `Content-Security-Policy` dan `Strict-Transport-Security`

> **Hasil Fase 0:** Anda **sudah punya** yang Anda minta untuk penggunaan
> smartphone sehari-hari. Fase berikutnya adalah menutup gap, bukan
> mengaktifkan kapabilitas dasar.

---

### FASE 1 — Perbaiki yang rusak: tablet, CDN, overflow

> **Tujuan:** semua lebar layout berfungsi; app jalan penuh tanpa internet keluar.
>
> **Estimasi: 3–5 hari** · **Prasyarat: Fase 0**

#### 1.1 Tetapkan kontrak breakpoint (§7.2)

- Tambah blok token di `:root` `static/style.css`.
- Tambah `const BP` + helper di `static/boot.js`; ganti pemanggilan
  `matchMedia` yang tersebar (10 di `boot.js`, 13 di `ui.js`) agar memakai helper.
- **Test baru** `tests/test_breakpoint_contract.py`: parse angka dari CSS dan JS,
  assert identik; assert tidak ada breakpoint layout baru di luar himpunan
  `{640, 1024}` (kecuali penyesuaian kosmetik `≤420`, `≤520` yang di-allowlist).

#### 1.2 🔴 Perbaiki panel workspace di band tablet

Ubah cakupan aturan slide-over dari `≤640px` menjadi `≤1024px`:

```css
/* Naikkan seluruh blok slide-over .rightpanel dari @media(max-width:640px)
   ke @media(max-width:1024px), dengan lebar yang responsif: */
@media (max-width: 1024px){
  .rightpanel{
    display:flex !important;
    position:fixed; top:0; bottom:0; z-index:200;
    --overlay-w: min(380px, 88vw);          /* phone: hampir penuh; tablet: 380px */
    width: var(--overlay-w) !important;
    right: calc(-1 * var(--overlay-w)) !important;
    transition: right .25s ease;
    padding-top: var(--app-titlebar-safe-top);
    box-sizing:border-box;
  }
  .rightpanel.mobile-open{ right:0 !important; box-shadow:-4px 0 24px rgba(0,0,0,.4) !important; }
  .rightpanel .resize-handle{ display:none; }
}
@media (max-width: 640px){
  .rightpanel{ --overlay-w: min(300px, 100vw); }   /* override khusus phone */
}
```

Lalu **hapus** `.rightpanel{display:none}` dari blok `@media(max-width:900px)`
(aturan inilah penyebabnya) dan sesuaikan `_isCompactWorkspaceViewport()` agar
memakai `BP.TABLET`.

**Kriteria penerimaan:** test Playwright pada 768px dan 820px — klik tombol
Files → `.rightpanel` punya `left < viewportWidth` dan `width > 0`.

#### 1.3 🔴 Vendor Prism.js dan xterm.js secara lokal

```
static/vendor/prismjs/1.29.0/prism-core.min.js
static/vendor/prismjs/1.29.0/prism-autoloader.min.js
static/vendor/prismjs/1.29.0/components/*.min.js      ← autoloader butuh direktori ini
static/vendor/prismjs/1.29.0/themes/prism-tomorrow.min.css
static/vendor/xterm/5.3.0/xterm.js
static/vendor/xterm/5.3.0/xterm.css
static/vendor/xterm/5.3.0/xterm-addon-fit.js
static/vendor/xterm/5.3.0/xterm-addon-web-links.js
```

- Ganti 7 tag `<script>`/`<link>` di `static/index.html`.
- Set `Prism.plugins.autoloader.languages_path` ke path lokal.
- **Perketat CSP** — hapus `https://cdn.jsdelivr.net` dari `script-src`,
  `style-src`, dan `worker-src` di `api/helpers.py`. Ini keuntungan keamanan
  gratis yang menyertainya.
- Tambahkan aset baru ke `SHELL_ASSETS` di `static/sw.js` agar ikut ter-cache offline.
- **Test:** boot server dengan network egress diblokir, muat halaman,
  assert `requestfailed` = 0 dan `Prism` serta `Terminal` terdefinisi di `window`.

Biaya: ~+400 KB mentah di `static/`, tapi **nol** request lintas origin dan
langsung ter-cache service worker.

#### 1.4 Perbaiki overflow horizontal 14px (§6.10)

Beri `.panel-actions` `min-width:0; flex-wrap:wrap;` dan `flex-shrink` yang
benar pada tombol-tombolnya.
**Kriteria penerimaan:** `document.scrollWidth === document.clientWidth` di
375/393/768/820/1024/1440.

#### 1.5 Tambahkan harness test browser responsif

`tests/browser_responsive.py` — parametrik atas 6 viewport, memeriksa:
overflow horizontal = 0, panel kunci bisa dijangkau, tidak ada console error,
tidak ada target sentuh interaktif < 40px di viewport phone.
Jalankan di CI bersama `browser_smoke.py`.

**Ini adalah item bernilai tertinggi di seluruh dokumen** — ia mencegah seluruh
kelas bug §6.1 muncul lagi.

---

### FASE 2 — Paritas fitur & polesan mobile

> **Tujuan:** setiap fitur dan setting terjangkau dari HP; interaksi terasa native.
>
> **Estimasi: 1–2 minggu** · **Prasyarat: Fase 1**

#### 2.1 Kembalikan fitur yang hilang (§6.7)

| Fitur | Rencana |
|---|---|
| **Saved prompts** | Pindahkan ke bottom sheet yang dipicu dari tombol `+` di composer mobile (bukan popup desktop) |
| **Outline panel** | Ubah jadi bottom sheet "Jump to…" dengan daftar heading, dipicu dari long-press judul titlebar (gestur long-press sudah ada: `.app-titlebar-title.long-pressing`) |
| **Sort/filter tabel markdown** | Ganti indikator hover jadi header tabel yang bisa di-tap; kontrol filter jadi baris chip di atas tabel yang bisa di-scroll |

#### 2.2 Komponen bottom sheet

Bangun **satu** primitif `bottom-sheet` yang dipakai ulang untuk semua overlay
mobile (menu, picker, panel config, konfirmasi):

- Muncul dari bawah, ada handle drag, tutup dengan swipe-down atau tap backdrop.
- Fokus terperangkap di dalamnya (a11y), Escape menutup, mengembalikan fokus.
- Menghormati `--keyboard-bottom-inset` dan `env(safe-area-inset-bottom)`.
- Tinggi maksimum `min(85dvh, content)`; body-nya yang scroll, bukan halaman.
- Di ≥1025px komponen yang sama me-render sebagai popover/modal desktop —
  satu komponen, dua presentasi.

#### 2.3 Audit Control Center di viewport phone

Buka setiap panel (Cron, Skills, Memory, Profiles, Providers, Kanban, Insights,
Settings, Extensions) di 393px dan verifikasi: tanpa overflow horizontal, semua
input ≥44px, dropdown tidak terpotong, tombol simpan selalu terjangkau tanpa
scroll horizontal. Perbaiki yang gagal.

#### 2.4 Perbaiki zoom & safe-area (§6.5, §6.6)

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

```js
// static/pwa-startup.js — matikan zoom HANYA di PWA terinstal
if (matchMedia('(display-mode: standalone), (display-mode: fullscreen)').matches
    || navigator.standalone) {
  document.querySelector('meta[name=viewport]')
    .setAttribute('content',
      'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover');
}
```

Perbarui dua test yang mengunci perilaku lama
(`test_viewport_disables_page_zoom_for_native_pwa_shell`,
`test_pwa_safe_area_top_stays_scoped_to_installed_modes`) agar mengunci
perilaku baru: browser boleh zoom, PWA tidak.

Lalu audit landscape di 844×390 dengan safe-area inset yang disimulasikan —
pastikan tidak ada konten di bawah cutout.

#### 2.5 Gestur

- Swipe dari tepi kiri → buka drawer sidebar (edge guard 24px sudah ada).
- Swipe kanan pada slide-over workspace → tutup.
- Hormati `prefers-reduced-motion` (blok CSS-nya sudah ada).
- **Jangan** bajak swipe-back native browser di iOS — itu merusak ekspektasi pengguna.

#### 2.6 Tambahkan locale Bahasa Indonesia

Tambah entri `id` di `LOCALES` (`static/i18n.js`). Ini menambah ~115 KB mentah;
Fase 4 akan mengembalikannya dengan pemecahan per-locale.

---

### FASE 3 — Web Push: notifikasi saat browser ditutup

> **Tujuan:** kirim tugas panjang ke agent, kunci HP, dapat notifikasi saat selesai.
>
> **Estimasi: 1 minggu** · **Prasyarat: Fase 0 (HTTPS wajib)**
>
> **Ini adalah fase yang paling terasa "seperti aplikasi Claude".**

#### 3.1 Sisi server

Dependensi baru: `py-vapid` + `pywebpush` (atau implementasi VAPID manual
dengan `cryptography` yang sudah menjadi dependensi — menghindari paket baru).

```
POST   /api/push/subscribe      { endpoint, keys:{p256dh, auth} }  → simpan per sesi auth
DELETE /api/push/subscribe      → hapus
GET    /api/push/vapid-key      → public key (base64url)
```

Penyimpanan: `~/.hermes/webui/push_subscriptions.json`, mode 0600, di-scope per
profil. Kunci VAPID di-generate saat startup pertama seperti pola `_load_key()`
yang sudah dipakai `api/auth.py` untuk `.pbkdf2_key`.

Titik pemicu (semuanya sudah punya hook internal):
- Turn agent selesai (`api/streaming.py`)
- Cron job selesai / gagal
- Approval tool menunggu keputusan pengguna ← **paling berharga**; tanpa ini
  agent bisa menggantung tanpa batas menunggu tap yang tidak pernah datang
- Agent crash / error

#### 3.2 Sisi klien

```js
// static/sw.js
self.addEventListener('push', (e) => {
  const d = e.data.json();
  e.waitUntil(self.registration.showNotification(d.title, {
    body: d.body, icon: '/static/favicon-192.png', badge: '/static/favicon-32.png',
    tag: d.sessionId, renotify: false, data: { url: d.url },
    actions: d.actions || []          // mis. Approve / Deny untuk approval tool
  }));
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(clients.matchAll({type:'window', includeUncontrolled:true}).then(ws => {
    const w = ws.find(w => w.url.includes(e.notification.data.url));
    return w ? w.focus() : clients.openWindow(e.notification.data.url);
  }));
});
```

UI: toggle di Control Center → Settings → Notifications, dengan pemilihan
per-jenis event. Minta izin **saat pengguna menyalakan toggle**, bukan saat
halaman dimuat (prompt izin yang muncul tiba-tiba adalah anti-pattern dan
sebagian besar ditolak).

#### 3.3 Catatan platform yang harus jujur disampaikan

| Platform | Dukungan Web Push |
|---|---|
| Chrome/Edge Android | ✅ Penuh, sejak lama |
| Firefox Android | ✅ Penuh |
| **Safari iOS/iPadOS** | ⚠️ **Hanya untuk PWA yang di-install ke home screen** (iOS 16.4+). Tab Safari biasa **tidak** menerima push |
| Desktop | ✅ Semua browser modern |

→ Pada iOS, dokumentasi harus menyatakan: **"Add to Home Screen" adalah syarat,
bukan opsional**, agar notifikasi bekerja.

---

### FASE 4 — Performa: cold start & offline

> **Tujuan:** buka app di jaringan 4G, siap dipakai < 2,5 detik; shell tetap
> tampil saat offline.
>
> **Estimasi: 1–2 minggu** · **Prasyarat: Fase 1**

#### 4.1 🎯 Pecah `i18n.js` per locale — **penghematan terbesar, risiko terkecil**

Sekarang: satu file 1,7 MB / 477 KB gzip berisi 16 bahasa (setelah `id`).

Rencana:
1. Script build (`scripts/split_i18n.py`) memecah `LOCALES` jadi
   `static/i18n/<kode>.js`, masing-masing ~110 KB mentah / ~32 KB gzip.
2. `static/i18n/core.js` berisi loader + locale `en` sebagai fallback.
3. `boot.js` memuat locale aktif secara dinamis sebelum render pertama
   (locale sudah tersimpan di `localStorage`, jadi diketahui sebelum paint).
4. Endpoint `/api/i18n/<locale>` melayaninya dengan header `immutable` yang sudah ada.

**Dampak terukur: −445 KB gzip = −32% total payload.** Ini lebih besar daripada
semua optimasi lain digabung.

#### 4.2 Pecah `panels.js` (151 KB gzip) jadi lazy

Control Center jarang dibuka pada kunjungan pertama. Muat `panels.js` saat
launcher pertama kali di-tap, bukan di boot. Injeksi `<script>` sederhana +
promise cache; tidak butuh bundler.
**Penghematan: −151 KB gzip dari jalur kritis.**

#### 4.3 Pecah `terminal.js` + xterm jadi lazy

Terminal embedded (26 KB + ~300 KB xterm setelah di-vendor) hanya dimuat saat
panel terminal dibuka. Terminal juga jarang dipakai di HP.

#### 4.4 Susun ulang CSS

`style.css` 505 KB / 95 KB gzip memuat 11 skin sekaligus. Pecah:
- `style.core.css` — layout + tema default (render-blocking)
- `style.skins.css` — 10 skin non-default (dimuat hanya bila `data-skin` ≠ default)

#### 4.5 Perkuat service worker

- Pre-cache seluruh shell termasuk vendor yang sudah lokal (Fase 1.3).
- Halaman offline dengan sesi terakhir yang di-cache (read-only) alih-alih
  error jaringan.
- Strategi stale-while-revalidate untuk `GET /api/sessions` agar daftar sesi
  muncul instan saat dibuka kembali.
- Background Sync untuk pesan yang dikirim saat offline
  *(catatan: Background Sync belum didukung Safari — sediakan fallback antrian
  di IndexedDB yang di-flush saat online kembali).*

#### 4.6 Target yang bisa diukur

| Metrik | Sekarang (estimasi 4G) | Target |
|---|---|---|
| Transfer JS+CSS (cold) | ~1.400 KB gzip | **< 450 KB** |
| First Contentful Paint | — | < 1,8 s |
| Time to Interactive | — | < 2,5 s |
| Repeat visit (SW hit) | — | < 0,8 s |
| Lighthouse Mobile Performance | — | ≥ 85 |

*(Nilai "sekarang" untuk FCP/TTI ditandai **[belum terverifikasi]** — perlu run
Lighthouse pada deployment nyata. Angka transfer sudah terukur pasti.)*

---

### FASE 5 — Polesan native-feel

> **Tujuan:** perbedaan dengan aplikasi native jadi sulit dirasakan.
>
> **Estimasi: 1–2 minggu** · **Prasyarat: Fase 2, 3, 4**

- **View Transitions API** untuk perpindahan sesi dan buka/tutup panel
  (progressive enhancement — browser yang belum mendukung tetap normal).
- **Haptic feedback** — `navigator.vibrate(10)` pada tap tombol kirim, buka
  drawer, dan aksi approve/deny (Android; iOS mengabaikannya dengan aman).
- **Pull-to-refresh** pada daftar sesi, dengan `overscroll-behavior` yang benar
  agar tidak bentrok dengan pull-to-refresh native browser.
- **Skeleton screen** saat memuat sesi, menggantikan spinner.
- **Optimistic UI** — pesan pengguna muncul instan sebelum server mengonfirmasi.
- **Share Target API** di manifest — bagikan teks/gambar dari app lain langsung
  ke sesi Hermes. Ini fitur "app-like" yang sangat terasa di Android.
- **Web Share API** untuk mengekspor sesi ke app lain.
- **Kontrol suara** — tombol mic sudah ada (Web Speech API); tambah mode
  hands-free penuh dengan TTS untuk respons (Edge TTS sudah ada di server).
- **App Badging API** — jumlah approval yang menunggu di ikon home screen.
- **Audit a11y penuh** — VoiceOver (iOS) & TalkBack (Android): urutan fokus,
  label ARIA pada tombol icon-only, pengumuman live region saat streaming.

---

## 9. Blueprint Deployment VPS

### 9.1 Topologi yang direkomendasikan

```
                     Internet
                        │
                        ▼
        ┌───────────────────────────────┐
        │  ufw: hanya 22/80/443         │
        ├───────────────────────────────┤
        │  nginx / Caddy                │
        │  • TLS (Let's Encrypt)        │
        │  • proxy_buffering off  ← SSE │
        │  • X-Forwarded-Proto          │
        │  • HSTS                       │
        └───────────────┬───────────────┘
                        │ 127.0.0.1:8787  (tidak terekspos)
        ┌───────────────▼───────────────┐
        │  hermes-webui.service         │
        │  ThreadingHTTPServer          │
        │  password / OIDC / passkey    │
        └───────────────┬───────────────┘
                        │ import langsung
        ┌───────────────▼───────────────┐
        │  Hermes Agent                 │
        │  ~/.hermes/  (state, memory)  │
        │  workspace/                   │
        └───────────────────────────────┘
```

### 9.2 Lapisan keamanan (pilih sesuai kebutuhan)

| Lapisan | Kapan dipakai | Konfigurasi |
|---|---|---|
| Password app-level | **Minimum mutlak** | `HERMES_WEBUI_PASSWORD` |
| TLS | **Wajib** untuk domain publik | certbot / Caddy otomatis |
| Passkey / WebAuthn | Login satu-tap dari HP (Face ID / sidik jari) | `HERMES_WEBUI_PASSKEY=1` + HTTPS |
| OIDC | Sudah punya SSO | `api/auth_oidc.py` |
| Trusted-header (Authelia / Cloudflare Access / oauth2-proxy) | Keamanan maksimum | `HERMES_WEBUI_TRUSTED_AUTH_HEADER` + `TRUSTED_PROXY_CIDRS` |
| Tailscale (tanpa port publik) | **Paling aman, paling mudah** | `HERMES_WEBUI_HOST=0.0.0.0` di tailnet saja |
| fail2ban di log nginx | Bonus | rate limiter app-level sudah ada |

> **Rekomendasi saya untuk penggunaan pribadi:** **Tailscale + password**. Tidak
> ada port publik sama sekali, tidak perlu mengurus sertifikat, dan HP Anda
> tetap bisa mengaksesnya dari mana pun. Trade-off-nya: harus menjalankan
> Tailscale di HP, dan **Web Push (Fase 3) butuh HTTPS** — Tailscale
> menyediakannya lewat MagicDNS + `tailscale cert`, jadi ini tetap tercapai.
> Kalau Anda ingin akses tanpa VPN sama sekali, pakai domain publik + nginx +
> passkey.

### 9.3 Backup

```bash
# Yang wajib di-backup
~/.hermes/webui/      # sesi, settings, project, workspace terakhir
~/.hermes/            # memori agent, skill, cron, kredensial profil
~/workspace/          # file kerja Anda
```

Snapshot harian ke object storage; enkripsi — direktori ini berisi API key
provider.

### 9.4 Operasional

```bash
systemctl status hermes-webui
journalctl -u hermes-webui -f
curl -s localhost:8787/health
./ctl.sh status              # bila memakai ctl.sh alih-alih systemd
```

Health check `/health` cocok dipakai untuk uptime monitor eksternal.

---

## 10. Strategi Testing

### 10.1 Yang sudah ada

| Jenis | Cakupan | Kekuatan | Keterbatasan |
|---|---|---|---|
| pytest (1.385 file) | API, sesi, streaming, auth, workspace | Sangat luas | Test mobile sebagian besar **assertion teks CSS/JS**, bukan perilaku |
| ESLint runtime guard | `static/*.js` | Menangkap kelas bug "brick" (const reassign, tabrakan nama) | Bukan test perilaku |
| Ruff (line-scoped) | Python baru/berubah | Zero-noise pada kode lama | — |
| `browser_smoke.py` | Muat halaman, nol console error | Menangkap bug runtime nyata | **Hanya viewport desktop** |

### 10.2 Yang harus ditambahkan

**A. Harness responsif Playwright** (Fase 1.5) — parametrik atas
`[375×667, 393×852, 768×1024, 820×1180, 1024×768, 1440×900]`:

```python
INVARIANTS = [
    "document.scrollWidth <= document.clientWidth + 1",     # tanpa overflow horizontal
    "panel workspace terjangkau (tombol diklik → terlihat)",
    "sidebar terjangkau",
    "composer terlihat & tidak tertutup",
    "Control Center bisa dibuka & di-scroll",
    "nol console error",
    "nol target sentuh interaktif < 40px  (hanya viewport phone)",
]
```

**B. Regresi visual** — screenshot per viewport per tema, bandingkan dengan
baseline, toleransi 0,5%. Simpan baseline di `docs/ui-ux/evidence/` (direktori
sudah ada).

**C. Test kontrak breakpoint** (Fase 1.1) — parse CSS dan JS, assert angkanya
identik. Ini yang mencegah §6.1 terulang.

**D. Test build offline** — boot dengan egress diblokir, assert nol
`requestfailed` (Fase 1.3).

**E. Anggaran performa di CI** — gagalkan build bila total gzip aset kritis
melebihi ambang (mis. 500 KB setelah Fase 4).

### 10.3 Matriks perangkat manual

Minimal sebelum merilis perubahan mobile:

| Perangkat | Browser | Yang diperiksa |
|---|---|---|
| Android mid-range | Chrome | Perilaku keyboard, drawer, streaming |
| iPhone (bernotch) | Safari | Safe area, PWA standalone, `100dvh` |
| iPhone | Safari PWA terinstal | Push (Fase 3), status bar |
| iPad portrait | Safari | **Band tablet — bug §6.1** |
| Desktop | Chrome DevTools device mode | Regresi cepat |

---

## 11. Risiko, Trade-off, dan Non-Goals

### 11.1 Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| **Mengubah breakpoint merusak layout desktop** | Tinggi | Regresi visual sebelum/sesudah di semua viewport; Fase 1 sebagai unit yang bisa di-rollback |
| **Test yang mengunci perilaku lama** (viewport meta, `viewport-fit`) | Sedang | Test tersebut memang harus diperbarui — perbarui bersamaan dengan perubahan kode dan jelaskan alasannya di commit |
| **Codebase bergerak cepat** (1.385 test, rilis harian) | Sedang | Kerjakan per fase kecil; rebase sering; jangan biarkan branch panjang |
| **Coupling WebUI ↔ Agent** | Sedang | Pin kedua versi; upgrade berpasangan; ini di luar kendali dokumen ini |
| **Vendoring CDN menambah ~400 KB di repo** | Rendah | Sudah ada preseden (`static/vendor/katex/` 1,4 MB) |
| **Push notification bocor konten sensitif ke lock screen** | Sedang | Default: judul generik ("Hermes selesai"), isi detail opsional; jadikan setting |
| **Splitting i18n merusak fallback bahasa** | Rendah | Selalu muat `en` sebagai fallback; test setiap locale |

### 11.2 Trade-off yang eksplisit

1. **Tanpa framework/bundler.** Keputusan proyek yang tegas. Ini berarti tidak
   ada tree-shaking, tidak ada code-splitting otomatis, tidak ada
   komponen-per-file. Semua optimasi Fase 4 harus dilakukan manual. **Saya
   merekomendasikan menghormati batasan ini** — deployability tanpa build step
   adalah fitur nyata, bukan kekurangan.

2. **Vendoring vs CDN.** Vendoring menambah ukuran repo dan menghilangkan
   pembaruan otomatis, tapi memberi kemandirian offline, CSP lebih ketat, dan
   latensi lebih rendah. Untuk aplikasi self-hosted, vendoring hampir selalu
   jawaban yang benar.

3. **Zoom.** Mengizinkan zoom (WCAG) sedikit merusak kemurnian PWA. Deteksi
   `display-mode` menyelesaikan keduanya; kompleksitas tambahannya kecil.

### 11.3 Non-goals

- ❌ Menulis ulang frontend dengan React/Vue/Svelte
- ❌ Memperkenalkan bundler atau build step
- ❌ Membuat aplikasi native (React Native / Capacitor) — PWA sudah cukup
- ❌ Multi-tenancy / dukungan puluhan pengguna bersamaan
- ❌ Mengganti `ThreadingHTTPServer` dengan ASGI (tidak perlu di skala pribadi)
- ❌ Menyentuh internal Hermes Agent

---

## 12. Checklist Ringkas

### Sekarang juga (Fase 0 — 1–2 hari, tanpa ubah kode)

- [ ] Provision VPS, ufw hanya 22/80/443, SSH key-only
- [ ] Install hermes-agent + hermes-webui
- [ ] `.env`: `HOST=127.0.0.1`, `PASSWORD=…`, `TRUST_FORWARDED_PROTO=1`, `SESSION_TTL=2592000`
- [ ] systemd unit + `systemctl enable --now`
- [ ] nginx/Caddy + certbot — **`proxy_buffering off` untuk SSE**
- [ ] Verifikasi 9 poin checklist §0.6 dari HP sungguhan
- [ ] Add to Home Screen
- [ ] Backup harian `~/.hermes/` dan `~/workspace/`

### Sprint 1 (Fase 1 — 3–5 hari)

- [ ] Kontrak breakpoint di CSS + JS + test sinkronisasi
- [ ] 🔴 Perbaiki panel workspace di 641–1024px
- [ ] 🔴 Vendor Prism.js + xterm.js; perketat CSP
- [ ] Perbaiki overflow horizontal 14px
- [ ] Harness `tests/browser_responsive.py` di CI

### Sprint 2 (Fase 2 — 1–2 minggu)

- [ ] Komponen bottom sheet
- [ ] Kembalikan saved prompts, outline, kontrol tabel di mobile
- [ ] Audit Control Center di 393px
- [ ] Perbaiki zoom + `viewport-fit=cover`
- [ ] Gestur swipe
- [ ] Locale `id`

### Sprint 3 (Fase 3 — 1 minggu)

- [ ] VAPID + endpoint subscribe/unsubscribe
- [ ] Handler `push` + `notificationclick` di service worker
- [ ] Pemicu: turn selesai, cron selesai, **approval menunggu**, crash
- [ ] UI setting notifikasi per-event
- [ ] Dokumentasikan syarat "Add to Home Screen" untuk iOS

### Sprint 4 (Fase 4 — 1–2 minggu)

- [ ] Pecah `i18n.js` per locale (**−445 KB gzip**)
- [ ] Lazy-load `panels.js` (−151 KB)
- [ ] Lazy-load `terminal.js` + xterm
- [ ] Pecah CSS core vs skin
- [ ] Perkuat service worker (offline shell, SWR, antrian kirim)
- [ ] Anggaran performa di CI

### Sprint 5 (Fase 5 — 1–2 minggu)

- [ ] View Transitions, haptics, pull-to-refresh, skeleton, optimistic UI
- [ ] Share Target + Web Share
- [ ] App Badging
- [ ] Audit a11y VoiceOver/TalkBack

---

## Lampiran A — Ringkasan File Kunci

| File | Ukuran | Peran |
|---|---|---|
| `server.py` | 30 KB | Entry point, `ThreadingHTTPServer`, TLS, isolasi jaringan mode test |
| `bootstrap.py` | 29 KB | Discovery agent, ensure dependency, launcher |
| `ctl.sh` | 31 KB | Lifecycle daemon (start/stop/status/logs/restart) |
| `api/routes.py` | 1,23 MB | 223 route eksak + 11 prefix; static serving; SSE dispatch |
| `api/streaming.py` | 615 KB | Eksekusi agent, streaming SSE, `Last-Event-ID` |
| `api/auth.py` | 47 KB | PBKDF2, sesi, rate limit, trusted-header, cookie |
| `api/helpers.py` | 53 KB | Template CSP, gzip, util respons |
| `api/config.py` | 481 KB | Konfigurasi, discovery model/provider |
| `static/index.html` | 216 KB | Template shell tunggal |
| `static/style.css` | 505 KB | Seluruh CSS: layout, 71 `@media`, 6 `@container`, 11 skin |
| `static/ui.js` | 1,018 KB | Helper DOM, render markdown, kartu tool, context ring |
| `static/boot.js` | 172 KB | **Navigasi mobile**, keyboard inset, tema/skin, bfcache |
| `static/i18n.js` | 1,722 KB | 15 locale |
| `static/sw.js` | 8,5 KB | Service worker, pre-cache shell |
| `static/manifest.json` | 1,2 KB | Manifest PWA |
| `tests/test_mobile_layout.py` | — | Regresi mobile statis (breakpoint, markup, overflow) |
| `docs/UIUX-GUIDE.md` | — | Kebijakan desain, termasuk aturan responsif |
| `docs/remote-access.md` | 75 baris | SSH tunnel, Tailscale, laporan komunitas ARM64 |

## Lampiran B — Cara Mereproduksi Pengukuran

```bash
# 1. Boot server dengan state terisolasi
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install pyyaml cryptography playwright
HERMES_WEBUI_STATE_DIR=/tmp/state HERMES_WEBUI_HOST=127.0.0.1 \
HERMES_WEBUI_PORT=8791 HERMES_WEBUI_SKIP_ONBOARDING=1 \
  /tmp/venv/bin/python server.py &

# 2. Ukur payload gzip persis seperti yang dikirim server (level 6)
cd static && for f in *.js style.css index.html; do
  echo "$f raw=$(stat -c%s $f) gz=$(gzip -6 -c $f | wc -c)"; done

# 3. Ukur cakupan CSS responsif
python3 - <<'EOF'
import re
css = open('static/style.css', encoding='utf-8').read()
total = 0
for m in re.finditer(r'@media[^{]*\{', css):
    d, i = 0, m.end()-1
    while i < len(css):
        d += (css[i] == '{') - (css[i] == '}')
        if d == 0: break
        i += 1
    total += i - m.end() + 1
print(f"{total} / {len(css)} byte = {total/len(css)*100:.1f}% di dalam @media")
EOF

# 4. Probe multi-viewport dengan Playwright — lihat §5.1 untuk invariannya
```
