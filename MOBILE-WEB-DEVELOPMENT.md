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
> Tanggal analisa: 2026-08-19 · Commit dasar analisa: `fc1dc3a`
> **Re-audit: 2026-08-31 · Commit: `f1a60e46`** — pengukuran ulang seluruh
> permukaan mobile di HEAD, lihat [§0.8](#08-re-audit-2026-08-31--pengukuran-ulang-di-f1a60e46).
>
> **STATUS: Fase 1, 2, dan 3 SELESAI; Fase 4 selesai sebagian; Fase 5 sebagian besar selesai.**
> **Baru ingin ringkasan cepat berbahasa sederhana?** Lompat ke
> [§0.13 Ringkasan Terbaru untuk Orang Awam](#013-ringkasan-terbaru-untuk-orang-awam-update-2026-08-31)
> — status tiap fase, urutan pekerjaan berikutnya, dan cara menjalankan di
> komputer sendiri, semuanya dengan bahasa yang mudah. Untuk detail teknis, lihat
> [§0 Status Implementasi](#0-status-implementasi) untuk ringkasan apa yang sudah
> dikerjakan, angka sebelum/sesudah yang terukur, dan apa yang masih tersisa.
> **Sisa kerja tidak lagi diurut per sprint** — [§12](#12-backlog-terurut-prioritas)
> adalah satu daftar global terurut prioritas (P0 → P4), dan urutannya berbeda
> dari §8 karena alasan yang ditulis di sana.
> **P0 sudah dikerjakan** ([§0.9](#09-p0-terlaksana-2026-08-31)): dokumentasi
> HTTPS ada di [`docs/reverse-proxy.md`](docs/reverse-proxy.md), dan pemicu push
> cron + crash sudah terpasang. **P1 selesai sebagian**
> ([§0.10](#010-p1-terlaksana-sebagian-2026-08-31)) — dua item dihentikan dengan
> alasan terukur. **P2 selesai seluruhnya**
> ([§0.11](#011-p2-terlaksana-2026-08-31)): service worker, audit a11y, dan
> vendoring PDF.js + Mermaid. **P4.2 selesai** dan **gerbang P4.1 akhirnya
> diukur** ([§0.12](#012-p4-terlaksana--dan-gerbang-p41-akhirnya-diukur-2026-08-31))
> — Lighthouse mobile **71 → 76**, terutama karena shell HTML ternyata dikirim
> **tanpa kompresi** (231 KB → 44 KB). Gerbang P4.1 terbuka (76 < 85); datanya di
> §0.12.3, keputusannya milik Anda.
> Bagian §5 dan §6 sengaja **tidak** ditulis ulang — keduanya adalah catatan
> temuan awal, dan menghapusnya akan menghilangkan alasan mengapa perbaikannya
> dibuat. Setiap temuan yang sudah diperbaiki diberi penanda di tempatnya.

---

## Daftar Isi

0. [Status Implementasi](#0-status-implementasi) ← **mulai di sini**
   · [0.8 Re-audit 2026-08-31](#08-re-audit-2026-08-31--pengukuran-ulang-di-f1a60e46)
   · [0.9 P0 terlaksana](#09-p0-terlaksana-2026-08-31)
   · [0.10 P1 terlaksana sebagian](#010-p1-terlaksana-sebagian-2026-08-31)
   · [0.11 P2 terlaksana](#011-p2-terlaksana-2026-08-31)
   · [0.12 P4 terlaksana + gerbang P4.1 diukur](#012-p4-terlaksana--dan-gerbang-p41-akhirnya-diukur-2026-08-31)
   · **[0.13 Ringkasan Terbaru untuk Orang Awam](#013-ringkasan-terbaru-untuk-orang-awam-update-2026-08-31)** ← **paling mudah dibaca**
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
12. [Backlog Terurut Prioritas](#12-backlog-terurut-prioritas) ← **apa yang dikerjakan berikutnya**

---

## 0. Status Implementasi

**Fase 1 dan Fase 2 sudah dikerjakan.** Bagian ini adalah catatan pelaksanaannya:
apa yang berubah, angka sebelum/sesudah yang benar-benar diukur, apa yang
ditemukan di luar rencana, dan apa yang **tidak** jadi dikerjakan beserta
alasannya.

Semua verifikasi dilakukan dengan membooting `server.py` sungguhan dan
me-render halaman di Chromium headless — bukan dengan membaca ulang kode.

### 0.1 Papan skor

| Item | Rencana | Status | Bukti |
|---|---|---|---|
| **1.1** Kontrak breakpoint | CSS token + konstanta JS + test sinkronisasi | ✅ **Selesai** | `--bp-phone`/`--bp-tablet`, `BP.PHONE`/`BP.TABLET`, `tests/test_breakpoint_contract.py` |
| **1.2** Panel workspace di tablet | Slide-over sampai 1024px | ✅ **Selesai** | Terbukti terbuka di 768px & 820px (sebelumnya klik tidak menghasilkan apa pun) |
| **1.3** Vendor Prism + xterm | Lokalkan, perketat CSP | ✅ **Selesai** | **0** request eksternal, **0** request gagal (sebelumnya 7 gagal per halaman) |
| **1.4** Overflow horizontal 14px | Hilangkan | ✅ **Selesai** | `scrollWidth == clientWidth` di seluruh 9 viewport |
| **1.5** Harness browser responsif | Test multi-viewport di CI | ✅ **Selesai** | `tests/browser_responsive.py`, 9 viewport, masuk workflow `browser-smoke` |
| **2.1** Kembalikan fitur mobile | Saved prompts, outline, kontrol tabel | ✅ **Selesai** (tabel: sebagian) | Keduanya kini terjangkau lewat sheet; filter tabel tetap desktop-only (disengaja) |
| **2.2** Primitif bottom sheet | Komponen sheet reusable | ✅ **Selesai** | `HermesSheet` di `boot.js` + CSS `[data-mobile-sheet]` |
| **2.3** Audit Control Center 393px | Perbaiki yang gagal | ✅ **Selesai** | 11 panel diaudit; 11 target sentuh diperbaiki di 3 panel |
| **2.4** Zoom + `viewport-fit=cover` | Izinkan zoom di browser | ✅ **Selesai** | Zoom aktif di tab, tetap terkunci di PWA terinstal |
| **2.5** Gestur swipe | Buka drawer / tutup panel | ✅ **Selesai** | Swipe-tutup ditambahkan; swipe-buka **ternyata sudah ada** di upstream |
| **2.6** Locale Bahasa Indonesia | Tambah `id` ke `LOCALES` | ✅ **Selesai** | ±150 key inti; kontrak kelengkapan dilonggarkan lewat `tests/locale_contract.py` — lihat [§0.4](#04-locale-bahasa-indonesia--selesai-kontrak-dilonggarkan) |

Lima commit: `e387df0`, `f140951`, `6512511`, `20f3f3d`, `b136ea9`.

### 0.2 Angka sebelum → sesudah (terukur)

**Panel workspace, hasil klik tombol Files:**

| Viewport | Sebelum | Sesudah |
|---|---|---|
| 393px | terbuka (w=300) | terbuka (w=300) |
| **768px** | **`display:none`, klik tidak berefek** | **terbuka (w=380)** |
| **820px** | **`display:none`, klik tidak berefek** | **terbuka (w=380)** |
| 1024px | in-flow, overflow dokumen 14px | terbuka (w=380), tanpa overflow |
| 1440px | in-flow | in-flow (tidak berubah) |

**Request eksternal saat halaman dimuat** (CDN diblokir):

| | Sebelum | Sesudah |
|---|---|---|
| Request gagal | **7** (Prism ×3, xterm ×4) | **0** |
| Request lintas-origin | 7 | **0** |
| Error konsol | 7 | **0** |

**Overflow horizontal dokumen** (`scrollWidth` vs `clientWidth`):

| Viewport | Sebelum | Sesudah |
|---|---|---|
| 375 / 393 / 640 / 641 / 768 / 820 | sama | sama |
| 1024 | 1038 (+14) | **1024** |
| 1440 | 1454 (+14) | **1440** |

**Cakupan CSP** — jsdelivr tidak lagi menjadi grant seluruh origin:

```
sebelum  script-src  … https://cdn.jsdelivr.net …
         style-src   … https://cdn.jsdelivr.net …
         worker-src  … https://cdn.jsdelivr.net
         connect-src … https://cdn.jsdelivr.net

sesudah  script-src  … https://cdn.jsdelivr.net/npm/pdfjs-dist@4.9.155/
                       https://cdn.jsdelivr.net/npm/mermaid@10.9.3/ …
         style-src   … (jsdelivr dihapus seluruhnya)
         worker-src  … kedua path di atas
         connect-src … kedua path di atas
```

**Ukuran** — `static/` bertambah ~857 KB (apparent) untuk aset yang di-vendor:
`vendor/prismjs` 570 KB (298 grammar terminifikasi) + `vendor/xterm` 287 KB.
Payload aplikasi itu sendiri tidak berubah (5.527 KB mentah / **1.415 KB gzip**)
— aset vendor dimuat sesuai kebutuhan dan kini bisa di-pre-cache service worker,
yang sebelumnya mustahil karena lintas-origin.

**Target sentuh** yang diperbaiki (semuanya < 40 px, ditemukan oleh harness dan
audit Control Center):

| Lokasi | Sebelum | Sesudah |
|---|---|---|
| Tombol saran sesi kosong (×3) | 39 px tinggi | 44 px |
| Kanban `.panel-head-btn` (×4) | 24×24 | 44×44 |
| Settings `.settings-action-btn` (×6) | 37 px tinggi | 44 px |
| Logs tombol salin | 28 px tinggi | 44 px |

### 0.3 Temuan di luar rencana

Empat hal muncul saat mengerjakan yang tidak ada di analisa awal:

1. **Perbaikan tablet nyaris rusak lagi oleh kelas bug yang sama.** Setelah
   memindahkan slide-over ke ≤1024px, panel tetap tidak muncul — ternyata
   `@media(min-width:641px){ .rightpanel{position:relative} }` (aturan untuk
   resize handle) berada **lebih akhir** di file sehingga mengalahkan
   `position:fixed`. Akibatnya panel mempertahankan kotak layout-nya sementara
   `right:calc(-1 * var(--overlay-w))` mendorongnya ke samping, **melebarkan
   dokumen 380px** alih-alih memarkirnya di luar layar. Kedua rel kini memakai
   boundary-nya masing-masing: `.sidebar` di 641px, `.rightpanel` di 1025px.
   *Pelajaran: satu breakpoint yang dipakai bersama oleh dua komponen dengan
   perilaku berbeda adalah sumber bug ini, bukan sekadar gejalanya.*

2. **PDF.js dan Mermaid juga dimuat dari CDN.** Analisa awal menyebut 7 aset;
   itu akurat untuk *page load*, tapi `ui.js` juga meng-import PDF.js
   (`4.9.155`) dan Mermaid (`10.9.3`) secara lazy saat pengguna membuka PDF atau
   merender diagram. Keduanya ~4 MB gabungan, jadi tidak ikut di-vendor;
   sebagai gantinya grant CSP-nya dipersempit ke path spesifik. Untuk deployment
   air-gapped penuh, keduanya perlu di-vendor juga — dicatat sebagai sisa kerja.

3. **Klaim saya soal sorting tabel markdown salah.** Analisa awal menyebutnya
   "fitur yang benar-benar tidak bisa dijangkau". Faktanya **sorting selalu
   berfungsi di HP** — tombol header tetap bisa di-tap; yang disembunyikan hanya
   *glyph indikator arahnya*. Sekarang glyph itu ditampilkan untuk kolom yang
   sedang tersortir saja, sehingga tidak ada biaya lebar header di keadaan
   default (yang merupakan alasan asli aturan itu ditulis). Yang benar-benar
   tidak terjangkau hanyalah input filter.

4. **`ThreadingHTTPServer` terbukti bukan hambatan.** §6.11 menyebutnya "bukan
   masalah untuk 1 pengguna" tanpa bukti. Diukur langsung: server melayani
   `index.html` **seketika (0,00 s)** sambil menahan **40 SSE stream bersamaan**.
   Yang justru kehabisan sumber daya adalah Chromium — 9 browser context
   sekaligus menghabiskan connection pool per-host, sehingga harness diubah
   memakai ulang context.

### 0.4 Locale Bahasa Indonesia — SELESAI (kontrak dilonggarkan)

**Keputusan pemilik repo: terima locale parsial.** Sebelumnya item ini terhalang
karena repo menegakkan kelengkapan locale — setiap bundle di `LOCALES` wajib
memuat setiap keluarga key. Kontrak itu kini **dilonggarkan secara eksplisit**,
bukan dilubangi diam-diam.

**Bagaimana pelonggarannya dibuat.** Satu modul, `tests/locale_contract.py`,
mendeklarasikan locale mana yang parsial beserta alasannya. Ke-24 test yang
menegakkan paritas key sekarang bertanya ke modul itu, bukan meng-hardcode kode
locale. Konsekuensinya:

- Locale yang lengkap **tetap** diikat kontrak penuh — ini bukan cara diam-diam
  berhenti merawat bahasa yang sudah dikirim.
- Menaikkan `id` menjadi lengkap kelak = **hapus satu baris** di modul itu, bukan
  menyunting 24 berkas test lagi.
- `en` tidak boleh parsial (ia target fallback semua locale), dan itu ditegakkan.

**Apa yang diterjemahkan.** ±150 key: layar pertama seutuhnya (judul, subjudul,
tiga chip saran, placeholder komposer), composer, tab navigasi, aksi sesi, mode
suara, pemilih model, halaman login (klien *dan* server), status koneksi, serta
surface mobile baru dari Fase 2 (saved prompts, outline). Sisanya — cron,
onboarding, ekstensi, ±200 string settings — **sengaja** dibiarkan fallback ke
Inggris. Menebak label Indonesia untuk alur destruktif seperti konfirmasi
menonaktifkan autentikasi lebih berbahaya daripada membiarkannya Inggris.

**Kewajiban yang tetap melekat pada locale parsial** (ditegakkan oleh
`tests/test_partial_locale_contract.py`, 7 test):

| Kewajiban | Kenapa |
|---|---|
| `_lang`, `_label`, `_speech` wajib ada | tanpa itu locale tidak muncul di picker dan salah dilafalkan |
| Wajib menerjemahkan permukaan inti | bundle yang tidak menutup composer/navigasi/login itu stub, bukan bahasa |
| Setiap key-nya harus ada di `en` | menjaga rantai fallback dan menangkap salah ketik nama key |
| Setiap pengecualian wajib beralasan | itulah yang dibaca peninjau saat menilai apakah masih layak |
| Minimal 10 locale tetap lengkap | pengecualian tidak boleh melebar jadi pensiun kontrak |

**Bug yang ditemukan saat mengerjakan.** Placeholder komposer — string paling
menonjol di layar pertama — **tidak bisa diterjemahkan oleh locale mana pun**. Ia
dirakit sebagai `'Message ' + name + '…'` di dua tempat, dan yang menang adalah
`_applyBusyComposerPlaceholder()` di `ui.js` yang menimpa nilai dari
`applyBotName()`. Sekarang jadi key ber-template (`composer_placeholder`,
`{0}` = nama bot) di kedua tempat, dan `applyLocaleToDOM()` ikut memanggil
`applyBotName()` agar berganti saat bahasa diganti. Locale lain tidak berubah
perilakunya — mereka tetap menampilkan bahasa Inggris seperti sebelumnya.

**Terverifikasi di browser sungguhan** (393px dan 1440px): locale muncul di
picker sebagai "Bahasa Indonesia", dipilih lewat handler UI asli, `<html lang>`
jadi `id-ID`, string inti tampil Indonesia, key yang tidak diterjemahkan jatuh ke
**Inggris** (bukan ke nama key), pilihan bertahan setelah reload, dan nol error
konsol.

### 0.4b Yang masih TIDAK dikerjakan

**Filter tabel markdown tetap desktop-only** — ini input teks yang dirender ke
area header tabel, dan justru itulah yang dulu membuat header sempit membungkus
berlebihan. Memberinya rumah di HP berarti membuat surface baru (sheet per
tabel), yaitu perubahan desain, bukan perbaikan. Dicatat eksplisit sebagai
kesenjangan yang disengaja di `tests/test_mobile_feature_parity.py`.

### 0.5 Test yang ditambahkan

| File | Isi |
|---|---|
| `tests/browser_responsive.py` | **Gerbang layout di browser sungguhan.** 9 viewport; memeriksa overflow horizontal, keterjangkauan panel (tombol Files harus benar-benar menampilkan panel), navigasi sidebar, target sentuh, dan error konsol. Masuk ke workflow `browser-smoke`. |
| `tests/test_breakpoint_contract.py` | Menyandingkan angka breakpoint CSS dan JS; menolak breakpoint layout ketiga. |
| `tests/test_vendored_frontend_assets.py` | Tidak boleh ada `<script src>`/`<link href>` ke origin remote; aset vendor ada, ter-pre-cache SW, dan theme swap mempertahankan cache-buster. |
| `tests/test_mobile_feature_parity.py` | Kontrak keterjangkauan + **guard atas seluruh kelasnya**: setiap `display:none` baru pada entry point fitur di media query `max-width` harus dijustifikasi di allowlist. |
| `tests/locale_contract.py` | **Sumber kebenaran tunggal** locale mana yang parsial dan mengapa. Ke-24 test paritas key bertanya ke sini alih-alih meng-hardcode kode locale. |
| `tests/test_partial_locale_contract.py` | Menjaga pengecualian itu sendiri: identitas locale, permukaan inti, rantai fallback, alasan wajib, dan bahwa minimal 10 locale tetap lengkap. |

Test lama yang mengunci perilaku lama **diperbarui, bukan dihapus**, dan sekarang
menegakkan kontrak yang sudah diperbaiki:
`test_issue5545_three_panel_layout.py` (kini melarang `.rightpanel` disembunyikan
di lebar mana pun), `test_mobile_layout.py`, `test_issue1100_prism_sri.py`,
`test_sidebar_collapse_toggle.py`, `test_theme_color_meta_bridge.py`,
`test_issue3571_saved_prompts.py`, `test_issue2124_outline_panel.py`, dan lima
test CSP.

Dua test lain diperbaiki karena **rapuh**, bukan karena kontraknya berubah:
`test_pwa_manifest_csp.py` dan `test_issue4553_mobile_transcript_overflow.py`
sama-sama memotong sejumlah karakter tetap dari sumber (1.000 dan 5.000) alih-alih
mem-parsing strukturnya, sehingga penambahan apa pun di atas target membuatnya
gagal. Yang pertama kini membangun policy CSP sungguhan lewat
`_build_csp_enforced_policy()`; yang kedua menelusuri blok media dengan
penyeimbangan kurung.

**Catatan metodologi.** Baseline regresi pertama saya cacat: `git stash` tidak
membatalkan commit, jadi perbandingannya sebenarnya melawan kode saya sendiri
dan melaporkan "0 regresi" secara keliru. Baseline yang benar memakai
`git worktree` pada commit sebelum perubahan. Setelah diperbaiki, himpunan
kegagalan sama persis dengan baseline (50 = 50; seluruhnya kegagalan environment
playwright yang memang sudah ada di sandbox ini).

### 0.6 Sisa kerja setelah Fase 1–2

> **Catatan re-audit (2026-08-31):** bagian ini ditulis sebelum Fase 3 mendarat.
> Fase 3 kini **selesai** ([§0.7](#07-fase-3--web-push-selesai)), dan seluruh sisa
> kerja — termasuk tiga item di bawah — sudah diurut ulang secara global di
> [§12](#12-backlog-terurut-prioritas). Gunakan §12 sebagai daftar kerja; bagian
> ini dipertahankan sebagai catatan waktu itu.

Fase 3–5 belum disentuh dan tetap seperti tertulis di §8. Ditambah tiga item
baru yang muncul dari pekerjaan ini:

1. ~~**Locale Bahasa Indonesia**~~ — **selesai** ([§0.4](#04-locale-bahasa-indonesia--selesai-kontrak-dilonggarkan)). Sisa: menaikkan `id` jadi locale lengkap dengan menerjemahkan cron, onboarding, ekstensi, dan settings — satu keluarga key per kali, lalu hapus entrinya dari `PARTIAL_LOCALES`.
2. **Vendor PDF.js + Mermaid** (~4 MB) — akan menghapus jsdelivr dari CSP
   sepenuhnya dan membuat deployment benar-benar air-gapped.
3. **Filter tabel markdown di HP** — butuh surface sheet per tabel.

---

### 0.7 Fase 3 — Web Push (SELESAI)

**Ini gap terbesar yang tersisa untuk rasa "seperti aplikasi Claude", dan
sekarang tertutup.** Sebelumnya notifikasi hanya dibangkitkan oleh halaman yang
masih hidup — artinya di HP sering kali justru tidak muncul saat paling
dibutuhkan, karena browser sudah dibuang dari memori saat layar mati.

#### Tanpa dependensi baru

Jalur yang biasa ditempuh adalah `pywebpush`. Saya **tidak** memakainya:
`requirements.txt` proyek ini sengaja hanya dua paket, dan alternatifnya adalah
menambah dependensi wajib ketiga atau membuatnya opsional — yang berarti fitur
ini diam-diam mati di sebagian besar instalasi.

`api/push.py` mengimplementasikan RFC 8291 (enkripsi payload) dan RFC 8292
(VAPID) langsung di atas `cryptography`, yang sudah menjadi dependensi wajib.
Primitifnya — ECDH P-256, HKDF-SHA256, AES-128-GCM, dan JWT ES256 — semuanya
sudah kelas satu di pustaka itu, jadi ini perakitan, bukan rekayasa kriptografi.

#### Bug yang ditangkap vektor uji resmi

RFC 8291 §5 menerbitkan contoh lengkap: input, kunci antara, dan ciphertext yang
diharapkan. Implementasi saya mereproduksinya **byte demi byte** — yang berarti
setiap langkah (pertukaran ECDH, dua tahap HKDF, nonce AES-GCM, header record)
benar.

Vektor itu langsung menangkap satu bug nyata: field `rs` di header adalah
**ukuran record maksimum** yang diterima penerima (4096), bukan panjang record
ini. Nilai yang salah **tetap lolos** pada uji round-trip buatan sendiri —
saya mendekripsinya kembali dengan sukses — tetapi ditolak klien sungguhan.
Tanpa vektor resmi, bug ini akan lolos ke produksi dan bermanifestasi sebagai
"push terkirim tapi tidak pernah muncul di HP".

#### Yang dibangun

| Bagian | Isi |
|---|---|
| `api/push.py` | Kunci VAPID (P-256, persisten, mode 0600), header `Authorization: vapid`, enkripsi aes128gcm, penyimpanan langganan per-profil, pengiriman + pruning |
| Route | `GET /api/push/vapid-key`, `POST/DELETE /api/push/subscribe`, `POST /api/push/test` |
| `static/sw.js` | Handler `push` dan `pushsubscriptionchange` (`notificationclick` sudah ada dan matang) |
| `static/panels.js` | Alur subscribe, toggle setting, tombol uji, deteksi iOS |
| Pemicu | **Approval menunggu** (`api/route_approvals.py`) dan **turn selesai** (`api/streaming.py`) |

#### Keputusan desain yang perlu dicatat

**Approval adalah notifikasi paling bernilai di aplikasi ini.** Turn yang selesai
bisa menunggu sampai Anda melihat HP; approval yang tidak terjawab
**menghentikan agent tanpa batas waktu** — menunggu ketukan yang tidak pernah
datang karena browser sudah dibuang. Karena itu approval memakai
`requireInteraction` (tidak hilang sendiri) dan tag terpisah, sehingga tidak
pernah tertimpa notifikasi "respons siap".

**Tidak menotifikasi dua kali.** Halaman yang hidup sudah membangkitkan
notifikasinya sendiri. Service worker karena itu **membatalkan** push bila ada
window yang sedang `visible` di halaman tujuan — pengguna sedang menatapnya, dan
notifikasi sistem untuk sesuatu yang ada di layar hanyalah kebisingan. Window
yang tersembunyi tetap menerima push, karena di sana notifikasi halaman mungkin
tidak pernah menyala (timer di-throttle, SSE ditangguhkan).

**Tidak pernah memblokir agent.** `submit_pending()` berjalan di jalur tool-guard
agent. Pengiriman melibatkan I/O jaringan ke layanan pihak ketiga yang bisa
lambat atau menggantung. Semua pemicu memakai `notify_async()` di daemon thread,
dan seluruh kegagalan tertahan di dalam `notify()`. Terukur: jalur
`submit_pending` kembali dalam **0,4 ms**.

**Izin diminta hanya saat pengguna menyalakan toggle** — tidak pernah saat
halaman dimuat. Prompt izin yang muncul tiba-tiba mayoritas ditolak, dan
penolakan itu lengket.

**Kunci VAPID harus stabil.** Kunci publiknya tertanam di setiap langganan yang
pernah dibuat browser, jadi meregenerasinya membatalkan semuanya secara diam-diam
— push terus mengembalikan 403 dan tidak ada yang tahu sampai sadar notifikasi
berhenti. Karena itu ia dipersistenkan, dan `.env.example` memperingatkan agar
file itu ikut terbawa saat upgrade.

**Langganan mati dipangkas, error sementara tidak.** 404/410 berarti langganan
sudah tidak ada — mencobanya selamanya hanya kebisingan. 5xx adalah layanan yang
sedang bermasalah, dan perangkatnya tidak boleh hilang karena itu.

#### Syarat platform (penting untuk Anda)

| Platform | Dukungan |
|---|---|
| Chrome/Edge Android | ✅ Penuh |
| Firefox Android | ✅ Penuh |
| **Safari iOS/iPadOS** | ⚠️ **Hanya untuk PWA yang di-install ke Layar Utama** (iOS 16.4+). Tab Safari biasa **tidak** menerima push |
| Desktop | ✅ Semua browser modern |
| Semua platform | ⚠️ **Wajib HTTPS** (atau localhost) — jadi Fase 0 adalah prasyarat nyata |

Syarat iOS itu **ditampilkan di UI**, bukan hanya di dokumentasi: panel setting
mendeteksi iOS yang belum ter-install dan menampilkan peringatannya, karena
toggle yang tampak bekerja tapi diam-diam tidak berfungsi adalah kegagalan yang
paling membingungkan.

#### Yang TIDAK saya verifikasi — dan tidak bisa

**Pengiriman ujung-ke-ujung ke perangkat sungguhan belum diuji.** Itu memerlukan
browser sungguhan yang terhubung ke layanan push vendor (FCM/APNs/Mozilla), dan
sandbox ini memblokir egress ke sana. Yang **sudah** terverifikasi:

- Enkripsi cocok byte-per-byte dengan vektor resmi RFC 8291
- Browser bisa mendekripsi keluaran kami (round-trip dengan kunci privat UA)
- JWT VAPID terverifikasi secara kriptografis, `aud` = origin endpoint, ES256 r‖s 64 byte
- Pengiriman terhadap **push service tiruan**: header benar, body opaque, 410 memangkas, 5xx tidak
- UI di browser sungguhan: toggle, status, tombol uji, endpoint kunci VAPID
- **Jalur gagal** di browser sungguhan: saat langganan gagal dibuat, toggle
  kembali ke posisi mati (tidak berbohong), pesan error tampil, dan **nol
  uncaught error**

Yang tersisa untuk Anda uji setelah deploy: buka Settings → aktifkan toggle →
"Kirim push uji". Kalau muncul di HP, seluruh rantai bekerja.

#### Sisa kerja di Fase 3

> **✅ SELESAI di P0.2 (2026-08-31).** Keduanya kini terpasang — cron di **dua**
> jalur penyelesaian (manual dan scheduler in-process), crash di **kedua**
> excepthook. Lihat [§0.9](#09-p0-terlaksana-2026-08-31). Paragraf di bawah
> dipertahankan sebagai catatan alasan keduanya ditunda saat itu.

Pemicu cron-selesai dan crash belum dipasang. Keduanya mudah ditambahkan sekarang
karena infrastrukturnya sudah ada (`push.notify_async()` satu panggilan), tapi
keduanya bukan yang membuat agent menggantung — approval-lah yang begitu, dan itu
sudah terpasang.

---

---

### 0.8 Re-audit 2026-08-31 — pengukuran ulang di `f1a60e46`

Analisa asli ditulis di commit `fc1dc3a`. Repo sudah bergerak jauh sejak itu
(locale ke-16 masuk, skin bertambah dari 11 jadi 20, `ui.js`/`boot.js` tumbuh).
Bagian ini adalah **pengukuran ulang permukaan mobile di HEAD sekarang**, bukan
pembacaan ulang §0.1–§0.7.

**Batas kejujuran, dulu.** Playwright/Chromium **tidak tersedia** di environment
re-audit ini (`import playwright` → `ModuleNotFoundError`). Konsekuensinya harus
eksplisit:

- Semua angka **byte, jumlah, dan isi file** di bawah ini **terukur langsung** di
  working tree — reproducible lewat Lampiran B.
- Semua klaim **layout runtime** dari §0.2 (panel terbuka di 768px, nol overflow
  di 9 viewport, target sentuh 44px) **tidak diverifikasi ulang** di commit ini.
  Gerbangnya masih terpasang — `.github/workflows/browser-smoke.yml` menjalankan
  `tests/browser_responsive.py` pada setiap PR non-docs — jadi selama CI hijau
  klaim itu masih berlaku. Tapi saya tidak menjalankannya sendiri di sini, dan
  tidak akan berpura-pura sudah.

#### Yang masih berdiri

| Klaim dari §0 | Status di `f1a60e46` | Bukti terukur sekarang |
|---|---|---|
| 0 aset runtime dari CDN saat page load | ✅ Masih | 5 `<script src>` + 4 `<link rel=stylesheet>` di `index.html`, **semuanya** `static/…` |
| CSP tidak lagi memberi grant seluruh origin jsdelivr | ✅ **Dilampaui** (P2.3) | Kedua path sisa (`pdfjs-dist@4.9.155/`, `mermaid@10.9.3/`) sudah divendor. **Nol origin CDN** di `script-src`, `worker-src`, `connect-src` — lihat [§0.11](#011-p2-terlaksana-2026-08-31) |
| Kontrak breakpoint hidup, tidak melar | ✅ Masih | `--bp-phone:640px` / `--bp-tablet:1024px` (`style.css:36-37`) ↔ `BP.PHONE`/`BP.TABLET`; `tests/test_breakpoint_contract.py` masih menolak breakpoint layout ketiga lewat allowlist kosmetik eksplisit |
| Gerbang responsif berjalan di CI | ✅ Masih | `browser-smoke.yml` → step **"Run responsive layout gate"**, 9 viewport |
| Web Push terpasang tanpa dependensi baru | ✅ Masih | `api/push.py` (19,6 KB); handler `push` + `pushsubscriptionchange` + `notificationclick` di `sw.js` (kini 520 baris setelah P2.1) |
| Locale parsial dikontrak, bukan dilubangi | ✅ Masih | `tests/locale_contract.py` → `PARTIAL_LOCALES = {"id": …}`, satu entri, beralasan |

Tidak ada regresi arsitektural. Yang bergeser adalah **angkanya**.

#### Temuan baru 1 — payload tumbuh secara struktural, dan tidak ada gerbang yang menyadarinya

Ini temuan terpenting dari re-audit.

Satu catatan metodologi lebih dulu: angka "5.527 KB mentah / 1.415 KB gzip" di
§0.2 **tidak bisa dibandingkan langsung** dengan angka di bawah — basis
perhitungannya (file mana yang dihitung, KB=1000 atau 1024) tidak tercatat di
dokumen lama, jadi selisihnya akan mengukur metode, bukan kode. Yang **bisa**
dibandingkan adalah per-file: `i18n.js` naik dari 477 → **485,3 KiB gzip**
(locale ke-16 masuk), `style.css` dari 505 → **515,5 KiB mentah** (skin 11 → 20).
Angka di bawah adalah basis baru yang akan dipakai anggaran CI di P1.0 —
ditulis lengkap agar tidak terulang.

Rincian jalur kritis **cold load** (gzip level 6, persis seperti yang dikirim
`_serve_static`; satuan KiB = 1024 byte):

| Bagian | Raw | Gzip |
|---|---:|---:|
| `index.html` | 221,0 | **42,0** |
| JS + CSS aplikasi (16 file, semua `defer`) | 5.323,0 | **1.377,8** |
| Vendor eager (Prism core+autoloader, **xterm ×3 + CSS**, KaTeX CSS, tema Prism) | 323,2 | **77,7** |
| **Total cold** | **5.867,2** | **1.497,5** |

Kontributor terbesar, gzip:

| File | Gzip (KiB) | % jalur kritis |
|---|---:|---:|
| `i18n.js` | **485,3** | 32,4% |
| `ui.js` | 273,7 | 18,3% |
| `panels.js` | 154,1 | 10,3% |
| `sessions.js` | 113,2 | 7,6% |
| `messages.js` | 111,4 | 7,4% |
| `style.css` | 99,0 | 6,6% |
| `vendor/xterm/*` (js+css) | **68,2** | 4,6% |
| `boot.js` | 52,3 | 3,5% |
| `index.html` | 42,0 | 2,8% |

Tiga hal yang tidak terlihat di analisa awal:

1. **`i18n.js` sekarang 16 locale.** `vi` masuk setelah analisa. Bundle-nya naik
   dari 477 → **485,3 KiB gzip**. Satu-satunya file yang pertumbuhannya
   struktural: setiap bahasa baru menambah ~30 KiB gzip ke **setiap** cold load,
   untuk 15 bahasa yang tidak dibaca pengguna itu.

2. **xterm dimuat eager di setiap page load — 68,2 KiB gzip.** Analisa awal
   menyebut "~300 KB xterm" sebagai angka mentah dan menaruhnya di Fase 4.3
   sebagai item ketiga. Angka gzip-nya baru terukur sekarang, dan konteksnya
   berubah: `index.html:113-115` memuat `xterm.js` + 2 addon + `xterm.css`
   dengan `defer` di `<head>` — artinya **setiap pengguna HP membayar 68,2 KiB
   untuk terminal embedded yang mayoritas tidak pernah dibuka di HP.**

3. **Tidak ada anggaran performa di CI.** `tests/` punya 1.398 file dan
   beberapa test "budget", tapi semuanya budget *runtime/query*
   (`test_5021_boot_model_redirect_budget.py`, `test_issue3928_models_budget_fallback.py`,
   …) — **nol** yang menjaga byte frontend. Tidak ada yang akan gagal kalau
   locale ke-17 atau modul 200 KB berikutnya masuk. Inilah kenapa urutan Fase 4
   di §12 saya balik: gerbangnya duluan, splitnya kemudian.

#### Temuan baru 2 — target `< 450 KB` di Fase 4.6 tidak tercapai oleh rencana Fase 4 sendiri

Saya hitung ulang proyeksi keempat item Fase 4 dengan angka gzip terukur:

| Langkah | Hemat (KiB gzip) | Sisa cold |
|---|---:|---:|
| Baseline sekarang | — | **1.497,5** |
| 4.1 Pecah `i18n.js` (muat `en` + locale aktif saja) | **−424,6** | 1.072,9 |
| 4.2 Lazy `panels.js` | −154,1 | 918,8 |
| 4.3 Lazy `terminal.js` + xterm | −75,1 | 843,7 |
| 4.4 Pecah CSS core ↔ skin | **−18,4** | **825,3** |

**Kesimpulannya: rencana Fase 4 sebagaimana tertulis mendarat di ~825 KiB, bukan
< 450 KiB.** Dua koreksi yang mengikuti:

- **4.4 jauh lebih kecil dari yang diduga.** Diukur: 97.429 dari 525.290 byte
  `style.css` berada di dalam selector `[data-skin=…]` — **18,5%**, atau ~18 KiB
  gzip. Itu item **terkecil** dari empat, bukan sebanding dengan yang lain.
  Ia turun peringkat di §12 karena itu.
- **Untuk benar-benar menembus 450 KiB perlu item kelima yang tidak ada di
  rencana:** memecah `ui.js` (273,7) + `sessions.js` (113,2) + `messages.js`
  (111,4) = 498,3 KiB yang dimuat penuh sebelum pesan pertama tampil. Itu
  refactor modul sungguhan, bukan pemisahan file, dan risikonya jauh di atas
  empat item lainnya. Saya menuliskannya sebagai **P4** yang eksplisit — dengan
  target yang jujur — alih-alih membiarkan angka 450 berdiri tanpa jalan menuju
  ke sana.

Target Fase 4 direvisi di §12: **≤ 850 KiB gzip cold** untuk P1, dan 450 KiB
dipindah ke P4 sebagai target yang butuh pekerjaan terpisah.

#### Temuan baru 3 — locale `id` jauh lebih tipis daripada yang tersirat di §0.4

§0.4 menyebut "±150 key inti" dan mencentangnya SELESAI. Terukur sekarang:

| Locale | Perkiraan key | vs `en` |
|---|---:|---:|
| `en` | 1.713 | 100% |
| `vi` | 1.827 | — |
| `cs` / `fr` / `pl` | 1.735 / 1.732 / 1.722 | ~100% |
| `pt` (terendah dari yang lengkap) | 1.524 | 89% |
| **`id`** | **163** | **9,5%** |

Angka itu tidak membatalkan keputusan di §0.4 — menolak menebak label Indonesia
untuk alur destruktif tetap benar, dan `t()` memang jatuh ke `en` per-key. Yang
perlu dikoreksi adalah **framing-nya**: `id` bukan "locale yang selesai dengan
sedikit ekor Inggris", ia **locale 9,5%** di mana pengguna Indonesia akan melihat
Inggris di hampir semua tempat kecuali layar pertama, composer, navigasi, sesi,
login, dan sheet mobile. Itu tetap keputusan yang sah untuk dikirim — tapi
"promosikan `id`" adalah pekerjaan ~1.550 key, bukan sisa-sisa. Diprioritaskan
di §12 sesuai ukuran sebenarnya.

#### Temuan baru 4 — HTTPS masih tidak terdokumentasi, dan itu sekarang memblokir fitur yang sudah dibayar

Ini yang mengubah urutan prioritas paling besar.

Saat §6.9 ditulis, "tidak ada panduan reverse proxy / TLS" berstatus 🟡 — tidak
nyaman, tapi bisa disiasati dengan SSH tunnel atau Tailscale. **Setelah Fase 3
mendarat, statusnya naik jadi pemblokir.** Web Push **mensyaratkan secure
context**: tanpa HTTPS, `PushManager.subscribe()` tidak akan pernah berhasil.
Artinya seluruh `api/push.py` — RFC 8291 + RFC 8292 yang diimplementasikan dari
nol, diverifikasi terhadap vektor uji resmi — **mati di setiap deployment yang
tidak punya TLS**. Begitu juga "Add to Home Screen" untuk iOS, yang merupakan
**satu-satunya** jalan push di iOS.

Statusnya di repo hari ini, terukur:

- `docs/remote-access.md` — **75 baris**, hanya SSH tunnel + Tailscale + laporan
  ARM64 komunitas. Nol nginx, nol Caddy, nol TLS, nol certbot.
- `README.md:447` — eksplisit mengarahkan ke SSH tunnel / Tailscale.
- `README.md:443` (modul NixOS) — eksplisit **menyerahkan** reverse proxy dan
  TLS ke "surrounding deployment module".
- `grep -rl proxy_buffering` di seluruh repo → **satu-satunya hasil adalah
  dokumen ini** (§0.5 Fase 0). Konfigurasi nginx yang benar untuk SSE ada, tapi
  hidup di roadmap, bukan di `docs/`.

Dan `proxy_buffering off` bukan detail kosmetik: tanpa itu nginx menahan stream
SSE dan aplikasi tampak menggantung — mode kegagalan pertama yang akan ditemui
setiap orang yang memasang reverse proxy sendiri.

**Karena itu "tulis `docs/reverse-proxy.md`" naik ke P0.** Ia satu-satunya item
di seluruh backlog yang (a) tidak menyentuh satu baris kode aplikasi, (b)
mengaktifkan fitur yang sudah selesai dibangun dan sekarang menganggur, dan (c)
merupakan prasyarat keras bagi separuh isi Fase 5.

#### Ringkasan re-audit

| | |
|---|---|
| Regresi arsitektural | **Nol** — semua kontrak Fase 1–3 masih ditegakkan test |
| Bug mobile terbuka di `BUGS.md` | **Nol** |
| Yang memburuk | `i18n.js` 477 → 485,3 KiB gzip (locale 15 → 16), skin 11 → 20, `ui.js`/`boot.js` tumbuh — semuanya tanpa satu pun gerbang byte |
| Yang salah di dokumen lama | Target Fase 4 `< 450 KB` tidak terjangkau rencananya sendiri; hemat CSS skin dilebih-lebihkan; `id` 9,5% bukan "selesai"; §1 masih mengatakan `id` belum ada |
| Prioritas yang berubah | **Dokumentasi HTTPS naik ke P0** (memblokir Web Push yang sudah jadi); **anggaran payload naik ke depan Fase 4**; **split CSS turun ke belakang** |

---

---

### 0.9 P0 terlaksana (2026-08-31)

P0.1 dan P0.2 dari [§12](#12-backlog-terurut-prioritas) dikerjakan. Bagian ini
mencatat apa yang berubah, apa yang **gagal verifikasi** saat dikerjakan, dan
apa yang tidak bisa saya buktikan.

#### Yang berubah

| Berkas | Perubahan |
|---|---|
| `docs/reverse-proxy.md` | **Baru** — nginx + Caddy + TLS, ketiga variabel `TRUST_FORWARDED_*`, subpath mount, diagnosis SSE, alur Web Push |
| `docs/remote-access.md` | Peringatan secure-context di atas + catatan `tailscale cert`, keduanya menaut ke dokumen baru |
| `README.md` | Bagian "Public hostname with TLS"; catatan modul NixOS kini punya tujuan rujukan |
| `MOBILE-WEB-DEVELOPMENT.md` | §0.5 **dipindahkan** ke `docs/`, bukan disalin |
| `api/push.py` | `notify_cron_complete()`, `notify_crash()`, `reset_crash_push_cooldown()`; `notify_async()` kini mengembalikan Thread |
| `api/routes.py` | Pemicu cron di jalur manual `/api/crons/run` |
| `api/profiles.py` | Pemicu cron di jalur scheduler in-process |
| `api/crash_visibility.py` | `_push_crash()` + panggilan dari kedua excepthook |
| `static/sw.js` | `requireInteraction` diperluas ke `crash` dan `cron_failed` |
| `tests/test_web_push.py` | 12 test baru; 1 test lama diperbarui mengikuti kontrak baru |

#### Tiga klaim yang gagal verifikasi saat dokumen ditulis

Saya menulis dokumen deployment lebih dulu lalu memeriksa setiap klaimnya
terhadap kode. Tiga di antaranya salah, dan semuanya jenis yang akan membuat
operator membuang waktu:

1. **"Set `HERMES_WEBUI_SESSION_TTL` supaya HP tidak logout."** Salah — ia
   **sudah** default 30 hari (`api/auth.py`: `SESSION_TTL = 86400 * 30`).
   Menyuruh orang menyetel ulang nilai default adalah cargo cult. Dikoreksi
   jadi penjelasan kapan Anda justru ingin mengubahnya.
2. **Nama cookie `hermes_webui_session`.** Itu nilai *contoh* di `.env.example`;
   default sebenarnya `hermes_session` (`api/auth.py:61`). Perintah `curl`
   diagnostik dengan nama cookie salah akan gagal autentikasi dan terlihat
   seperti masalah buffering — persis hal yang sedang didiagnosis.
3. **`event: keepalive`.** Server mengirim baris **komentar** SSE
   (`: keepalive`), bukan event bernama. Pembaca yang menunggu `event:` akan
   menyimpulkan streaming rusak padahal sehat.

*Semua contoh `bash`/`python` di Lampiran B juga dijalankan verbatim; keluarannya
cocok dengan angka di §0.8.*

#### Cakupan pemicu cron — rencananya kurang satu

Rencana menyebut satu lokasi (`api/background.py`). Diperiksa: modul itu soal
background **task**, bukan cron. Cron sebenarnya selesai di **dua** tempat, dan
keduanya dipasangi pemicu:

| Jalur | Berkas | Kapan |
|---|---|---|
| Manual "Run now" | `api/routes.py` (`finally` dari `_run_manual_cron_job`) | Pengguna menekan tombol |
| Scheduler in-process | `api/profiles.py` (`install_cron_scheduler_profile_isolation`) | Job terjadwal, **tidak ada halaman terbuka** |

Jalur kedua adalah alasan fitur ini ada: job terjadwal menyala saat tidak ada
yang menonton, jadi jalur notifikasi in-page tidak akan pernah bisa memicunya.

#### Yang TIDAK saya verifikasi

**Pengiriman push cron/crash ke perangkat sungguhan belum diuji** — batasan yang
sama persis dengan §0.7: sandbox ini memblokir egress ke FCM/APNs/Mozilla dan
tidak ada HP di sini. Yang **sudah** terverifikasi: bentuk payload, isolasi tag,
pembatasan laju, verdict default-gagal, bahwa tidak satu pun jalur bisa
melempar exception, dan bahwa keduanya memakai `notify_async` (bukan `notify`)
sehingga tidak pernah memblokir agent.

**Konfigurasi nginx/Caddy tidak dijalankan terhadap proxy sungguhan.** Ia
diturunkan dari membaca `api/auth.py`, `api/routes.py` (gerbang CSRF),
`api/passkeys.py`, dan `static/index.html` (`<base href>`), bukan dari
menjalankan nginx. Direktifnya standar dan alasannya terikat ke kode yang
dikutip, tapi Anda-lah yang akan menjalankannya pertama kali.

#### Test

`tests/test_web_push.py`: **42 lulus** (dari 30). Suite penuh: **14.954 lulus,
310 dilewati, 1 gagal** — satu-satunya kegagalan adalah
`test_5774b_atomic_config_writes.py::test_atomic_write_preserves_existing_permissions`,
yang menegakkan bit setgid `0o2664` bertahan melewati penulisan atomik. Ia
menguji `api/paths.py`, berkas yang **tidak saya sentuh**, dan gagal karena
filesystem sementara macOS membuang bit setgid. Tidak berhubungan dengan
perubahan ini dan sudah ada sebelumnya.

Ruff pada berkas yang saya ubah: nol temuan baru (`api/push.py` dan
`api/crash_visibility.py` bersih sepenuhnya; temuan lain di `routes.py` /
`profiles.py` / `test_web_push.py` semuanya di baris yang tidak saya sentuh dan
sudah ada di `HEAD`).

---

---

### 0.10 P1 terlaksana sebagian (2026-08-31)

**Cold path: 1.497,5 → 1.022,1 KiB gzip (−475,4 KiB, −31,7%).** P1.0, P1.1, dan
P1.3 selesai. **P1.2 dan P1.4 dihentikan sebelum dikerjakan** karena pengukuran
menunjukkan keduanya bukan pekerjaan yang dijelaskan rencana — rinciannya di
bawah, dan keputusannya milik Anda.

| Langkah | Rencana | Hasil | Cold path |
|---|---|---|---|
| — | baseline §0.8 | — | 1.497,5 KiB |
| **P1.0** Anggaran payload di CI | 0,5 hr | ✅ `tests/test_frontend_payload_budget.py` | — |
| **P1.1** Pecah `i18n.js` | −424,6 KiB | ✅ **−408,4 KiB** | 1.089,1 KiB |
| **P1.3** Lazy xterm | −75,1 KiB | ✅ **−67,0 KiB** | **1.022,1 KiB** |
| **P1.2** Lazy `panels.js` | −154,1 KiB | ⛔ **terhenti** — lihat di bawah | — |
| **P1.4** Pecah CSS skin | −18,4 KiB | ⛔ **terhenti** — lihat di bawah | — |

Target P1 yang direvisi (≤ 850 KiB) **tidak tercapai** — ia mengandaikan P1.2
mendarat. Tanpa P1.2, lantai dari rencana ini adalah ~1.004 KiB.

#### P1.0 — anggaran itu bekerja, dan dibuktikan bekerja

`tests/test_frontend_payload_budget.py` menurunkan daftar aset **dengan
mem-parsing `index.html`**, bukan dari daftar hardcoded. Daftar hardcoded persis
kegagalan yang ingin dicegah: seseorang menambah `<script src>`, daftar tidak
tahu, dan gerbangnya diam-diam berhenti menggambarkan halaman yang sebenarnya.

Gerbang yang tidak bisa gagal tidak berguna, jadi keduanya diuji langsung:

- Menambah ~66 KiB ke `outline.js` → gagal, pesannya menyebut
  `static/outline.js 71.1 KiB` dan `over by: 36.928 bytes`.
- Menambah `<script src="static/newmodule.js">` baru ke `index.html` → gagal,
  file baru itu **muncul di laporan** tanpa disebut di mana pun.

Ia juga menangkap konsekuensi P1.1 tanpa diminta: begitu `i18n.js` tidak lagi
dimuat, `test_every_budgeted_file_is_actually_on_the_cold_path` gagal dan
menyuruh menghapus anggaran per-filenya. Itu memang perilaku yang dirancang —
anggaran per-file yang tertinggal akan terus membatasi file yang sudah tidak
membebani cold start.

#### P1.1 — pecah `i18n.js`, dan mengapa sumbernya tidak dipindahkan

**Rencana menyebut risikonya terkecil. Itu benar untuk runtime, dan salah untuk
test:** **168 berkas test membaca `static/i18n.js` lewat path.** Memecah berkas
yang diauthor akan merusak semuanya.

Karena itu `static/i18n.js` **tetap sumber kebenaran yang disunting penerjemah**.
`scripts/split_i18n.py` menghasilkan `static/i18n/` darinya:

| Berkas | Isi | Gzip |
|---|---|---|
| `i18n/core.js` | runtime + `en` (rantai fallback) + manifest 16 bahasa | 38,8 KiB |
| `i18n/<kode>.js` × 15 | satu bahasa | 2,9–37,2 KiB |

Sebelumnya setiap pembaca mengunduh 485,3 KiB untuk 16 bahasa. Sekarang pembaca
Inggris membayar 38,8 KiB; pembaca Rusia (bundel terbesar) 76,0 KiB.

**Drift dijaga, bukan diharapkan.** Berkas hasil generate ikut di-commit — repo
ini tidak punya build step, jadi itu satu-satunya cara ia sampai ke deployment.
`tests/test_i18n_split.py::test_generated_bundles_match_the_source` menjalankan
`--check` dan gagal kalau keduanya berbeda. Tanpa itu, menambah key lalu lupa
regenerate akan **tak terlihat oleh 168 test yang membaca sumber** dan sangat
terlihat oleh pengguna.

**Empat hal yang tidak terlihat dari rencana:**

1. **`LOCALES` berhenti berarti "bahasa yang ada".** Ia kini berarti "bahasa yang
   sudah diunduh". Picker bahasa di `panels.js` meng-enumerasi
   `Object.entries(LOCALES)` — dibiarkan, ia akan menampilkan **dua** pilihan,
   dan `saveSettings()` yang jatuh ke `'en'` saat pilihan tidak ada akan
   **mereset bahasa pengguna secara diam-diam**. Itu persis bug #3539, masuk
   lewat pintu berbeda. Picker kini memakai manifest, dan
   `test_issue3539_language_dropdown_all_locales.py` diperbarui untuk menjaga
   kontraknya alih-alih ekspresi lamanya.
2. **`LOCALES[it]` bukan `LOCALES['it']`.** Generator awalnya memakai fungsi
   yang sama untuk *key* object literal dan *subscript* bracket. Tanpa kutip,
   `it:` sah sebagai key sementara `LOCALES[it]` membaca **variabel** bernama
   `it` dan melempar ReferenceError. Ditangkap oleh verifikasi ekuivalensi,
   bukan oleh mata.
3. **Urutan dokumen adalah yang menghilangkan kedipan Inggris.** Snippet di
   `index.html` berjalan saat parsing dan memakai `document.write` — pola yang
   sudah dipakai berkas itu untuk `<base href>` — sehingga bundel bahasa masuk
   **dalam urutan dokumen**: sesudah `core.js` (yang mendeklarasikan `LOCALES`),
   sebelum setiap script yang memanggil `t()`. Terverifikasi di browser: pada
   instalasi berbahasa Rusia, `t('tab_chat')` sudah `'Чат'` dan
   `<html lang>` sudah `ru-RU` pada paint pertama.
4. **Ada permintaan ganda yang tidak kelihatan.** `loadLocale()` di akhir
   `core.js` memanggil `setLocale('ru')` saat `ru.js` **belum** dieksekusi, jadi
   `loadLocaleBundle()` menyisipkan tag kedua untuk berkas yang sudah dalam
   perjalanan. Sekarang ia mengadopsi tag yang tertunda. Terverifikasi:
   `ru.js fetched exactly once`.

#### P1.3 — lazy xterm (bukan `terminal.js`)

`terminal.js` **tidak** ikut di-lazy. Ia 6,9 KiB gzip tapi punya 9 entry point
yang dipanggil berkas lain; membuat stub untuk sembilan fungsi demi 6,9 KiB
adalah risiko yang tidak dibayar. **xterm adalah 68,2 dari 75,1 KiB (91%) target
item ini**, dan ia bersih: `terminal.js` sudah punya `_xtermReady()` dan pesan
kegagalan yang layak, dan hanya ada **satu** call site (`_startComposerTerminal`,
yang sudah `async`).

xterm juga **dikeluarkan dari pre-cache service worker**. Pre-cache mengunduhnya
juga, hanya pada jadwal berbeda — itu akan membelanjakan ulang byte yang baru
saja dihemat. Tidak ada yang hilang saat offline: terminal adalah PTY hidup di
server.

#### ⛔ P1.2 — terhenti: asumsi "satu launcher" tidak berlaku

Rencana mengatakan "injeksi `<script>` sederhana + promise cache saat launcher
pertama di-tap". Diukur, `panels.js` tidak berbentuk begitu:

| Ukuran | Nilai |
|---|---|
| Fungsi top-level | 599 |
| Dipanggil dari berkas lain atau `index.html` | **101** |
| Terpasang di handler `onclick=` inline di `index.html` | **74** |
| Dipanggil `boot.js` saat startup | 17 (14 dijaga `typeof`, **3 tidak**) |

Yang tidak dijaga menutup pintunya: **`loadWorkspaceList()` dipanggil tanpa
syarat di `boot.js:3851`** saat boot, dan `switchPanel()` adalah navigasi rail
utama. Membuat `panels.js` lazy berarti membangun lapisan stub untuk 74 handler
inline plus menyelesaikan ketiga panggilan boot itu — bukan "injeksi script
sederhana", dan justru kelas perubahan yang gagal secara halus di produksi.

**Estimasi rencana (1 hari) berasal dari analisa saya sendiri di §0.8 yang tidak
pernah mengukur kopling ini.** Itu kesalahan saya, dan angkanya di atas adalah
koreksinya. Opsi, terurut dari yang saya rekomendasikan:

1. **Delegasi event, bukan stub.** Ganti 74 `onclick=` inline dengan satu
   listener terdelegasi yang memuat `panels.js` lalu memutar ulang aksinya.
   Perubahan nyata (~2–3 hari), tapi menghasilkan satu pintu masuk, bukan 74.
2. **Pecah `panels.js`, jangan di-lazy seluruhnya.** Kanban, Logs, Insights,
   Extensions adalah panel yang jelas terpisah dan jarang dibuka. Memindahkan
   ketiganya keluar mungkin menangkap sebagian besar 154 KiB tanpa menyentuh
   jalur boot.
3. **Biarkan.** 154 KiB tetap ada, cold path berhenti di ~1.004 KiB.

#### ⛔ P1.4 — terhenti: memindahkan 452 aturan melewati 1.631 aturan lain

Rencananya "`style.core.css` ↔ `style.skins.css`". Diukur:

| Ukuran | Nilai |
|---|---|
| Aturan `[data-skin=…]` top-level | 452 |
| Sebarannya di dalam berkas | byte 1,8% → 66,0% |
| Aturan **non-skin** yang berselang di antaranya | **1.631 (240 KB)** |
| Aturan skin di dalam `@media`/`@supports` | 4 |

Aturan skin bukan blok yang bisa dipotong; ia tersebar di dua pertiga berkas.
Mengekstraknya ke stylesheet yang dimuat belakangan memindahkan 452 aturan
melewati 1.631 aturan lain — **penataan ulang cascade**, di 20 tema visual, di
repo yang **tidak punya test regresi visual** untuk menangkap akibatnya.

Imbalannya **18,4 KiB — 1,8% dari 1.022 KiB sekarang**, dan hanya untuk pengguna
skin default. Itu rasio risiko/imbalan terburuk di seluruh backlog. Saya tidak
mengerjakannya bukan karena sulit, tapi karena mengubah tampilan 20 tema demi
1,8% tanpa cara memverifikasinya adalah pertukaran yang buruk.

Kalau tetap diinginkan, prasyaratnya adalah **screenshot regresi per skin**
lebih dulu — dan itu sendiri lebih besar daripada P1.4.

#### Verifikasi

| Yang diperiksa | Hasil |
|---|---|
| Ekuivalensi split ↔ monolith | **16/16 locale**: setiap key, setiap value (fungsi dibandingkan sebagai teks sumber), manifest, `t()`, label bahasa yang belum diunduh |
| Browser — muat dingin | core.js saja; **tidak ada** bundel bahasa; `LOCALES` berisi 1; manifest tahu 16; nol error konsol |
| Browser — instalasi bahasa Rusia | `ru.js` **tepat sekali**; `<html lang>=ru-RU`; `t('tab_chat')='Чат'` di paint pertama |
| Browser — ganti bahasa saat jalan | `de` diambil sesuai permintaan, `t('new_conversation')='Neuer Chat'`, pilihan tersimpan, balik ke `en` instan |
| Browser — `hermes-lang` ngawur | jatuh ke Inggris, nol uncaught error |
| Browser — xterm | tidak diambil saat muat; dimuat sesuai permintaan dengan `?v=`; panggilan kedua tidak mengambil ulang |
| `tests/browser_smoke.py` | lulus, nol error konsol |
| `tests/browser_responsive.py` | **9/9 viewport** lulus |
| Suite penuh | **15.041 lulus**, 246 dilewati, **2 gagal** — keduanya bereproduksi di pohon bersih (`test_5774b` setgid di tmpfs macOS, `test_issue6067` layout helper) |
| Ruff pada berkas baru | bersih |

> **Catatan untuk §0.8:** re-audit menyatakan klaim layout §0.2 tidak bisa
> diverifikasi ulang karena Playwright tidak ada. Playwright dipasang untuk
> pekerjaan ini, dan `tests/browser_responsive.py` kini **lulus 9/9 viewport di
> commit ini** — jadi klaim itu tidak lagi dibawa maju tanpa bukti.

### 0.11 P2 terlaksana (2026-08-31)

**Ketiga item P2 selesai.** Tidak ada yang dihentikan. Yang berubah dari rencana
adalah **isi** dua di antaranya: pengukuran menemukan tiga cacat yang tidak ada
di daftar, dan satu blocker yang akan membuat P2.3 gagal secara sunyi di
produksi.

| Item | Rencana | Hasil |
|---|---|---|
| **P2.1** Perkuat service worker | 2–3 hr | ✅ Selesai + 3 cacat pre-cache yang tidak terdaftar |
| **P2.2** Audit a11y | 2–3 hr | ✅ Selesai — **40 → 0** kontrol tanpa nama yang bisa dibacakan |
| **P2.3** Vendor PDF.js + Mermaid | 1 hr | ✅ Selesai — CSP kini **nol** origin eksternal |

**Biaya cold path: +11,6 KiB gzip** (955,1 KiB, anggaran 1.042,0 KiB). Rinciannya
di bawah; itu harga yang saya pilih dan alasannya ada.

#### P2.3 — dan `.mjs` yang akan membuatnya gagal tanpa pesan error

Divendor: `static/vendor/mermaid/10.9.3/` (3,18 MB mentah / 971 KiB gzip) dan
`static/vendor/pdfjs/4.9.155/` (1,64 MB / 487 KiB). Keduanya **tetap lazy** —
tidak ada di `index.html`, tidak ada di `SHELL_ASSETS`, dijaga oleh test.

CSP sesudahnya:

```
script-src   'self' 'unsafe-inline' https://static.cloudflareinsights.com blob:
worker-src   blob: 'self'
connect-src  'self' <loopback dev> <HERMES_WEBUI_CSP_CONNECT_EXTRA>
```

Nol `cdn.jsdelivr.net`. `tests/test_vendored_frontend_assets.py` kini melarangnya
**secara total** — di `static/*.js`, `index.html`, dan `api/helpers.py`.
Larangannya menyasar **bentuk URL** (`https://cdn.jsdelivr.net`), bukan nama
host: beberapa berkas menjelaskan *mengapa* CDN itu hilang, dan test yang
melarang menyebut namanya akan mendorong orang menghapus penjelasannya alih-alih
mempertahankan sifatnya. Pola yang sama dipakai untuk setiap larangan substring
di test-test baru; tanpanya, komentar saya sendiri yang menjatuhkannya.

**Blocker yang tidak ada di rencana.** `api/routes.py:_STATIC_MIME` tidak
mengenal `mjs`, jadi ekstensinya jatuh ke default `text/plain` — dan browser
**menolak** menjalankan ES module yang disajikan sebagai `text/plain` (strict
MIME checking, tanpa opsi override, tanpa pesan yang menyebut sebabnya). PDF.js
ships sebagai `.mjs`. Tanpa satu baris di map itu, vendoring akan "berhasil"
sepenuhnya lalu preview PDF diam-diam turun ke tautan unduh, dan konsol tidak
memberi petunjuk apa pun. Ditemukan dengan memuat berkasnya, bukan dengan
membaca kode.

Satu keputusan diubah setelah diukur: SRI hash mermaid dari CDN **dipertahankan**
karena berkas vendor ternyata byte-identik dengan salinan CDN-nya. Bahaya SRI
di sini bukan hash-nya ada, tapi hash-nya **basi** — ia gagal tertutup dan
sunyi. Jadi alih-alih menghapus atributnya,
`test_every_pinned_sri_hash_matches_the_vendored_file` **menghitung ulang**
ketiga hash (mermaid, KaTeX, js-yaml) terhadap berkas di disk.

#### P2.1 — tiga cacat pre-cache yang bukan bagian dari rencana

Rencananya "pre-cache vendor lokal yang tersisa". Saat membandingkan apa yang
`index.html` benar-benar minta dengan apa yang `sw.js` benar-benar simpan:

| Cacat | Akibat |
|---|---|
| `outline.js` + `extension_settings.js` **tidak ada** di `SHELL_ASSETS` | Keduanya `<script defer>` di setiap cold load; boot offline muncul tanpa keduanya |
| `smd.min.js` + `katex.min.css` di-pre-cache **dengan** `?v=`, halaman meminta **tanpa** | Setiap lookup miss. Lebih buruk dari tidak pre-cache: byte-nya tetap diunduh saat install lalu tidak pernah terpakai |
| `katex.min.js` di-pre-cache **dengan** `?v=`, `ui.js` meminta **tanpa** | Sama, arah berlawanan |

Tidak ada satu pun yang bisa dilihat suite lama, karena setiap assertion yang
ada memeriksa **keberadaan sebuah aturan**, bukan **kesepakatan antara dua
daftar**. `test_every_eager_cold_path_asset_is_precached` adalah bentuk umumnya:
ia menurunkan daftar permintaan dari `index.html` (termasuk `import` inline) dan
membandingkannya dengan `SHELL_ASSETS` — jadi `<script>` baru masuk kontrak sejak
saat ditulis.

Juga diperbaiki di jalan yang sama: `_vendorAssetUrl` **tidak** meng-encode ulang
token versi. `index.html` menerimanya sudah ter-percent-encode dari server
(`quote(WEBUI_VERSION, safe="")`), jadi `encodeURIComponent()` akan
men-escape ganda versi apa pun yang perlu di-escape — yang nyata adalah fallback
`"not detected"`, jadi `not%2520detected`, dan setiap entri pre-cache miss.

**Kriteria pre-cache dibuat eksplisit**, karena "vendor lokal yang tersisa"
tidak menjawab pertanyaannya: *apakah ia membuat konten yang SUDAH di-cache bisa
dibaca, atau ia butuh backend hidup?*

- **Di-cache** — KaTeX, js-yaml. Transkrip ter-cache yang penuh math atau blok
  YAML ter-render lengkap tanpa server.
- **Tidak** — xterm (terminal adalah PTY hidup), PDF.js (487 KiB), Mermaid
  (971 KiB). Terlalu berat dibelanjakan pada setiap install untuk fallback yang
  sudah turun dengan baik (tautan unduh, blok kode).
- **Tidak** — 150+ grammar Prism (1,3 MB). Blok kode tetap ter-render, hanya
  tanpa warna.

**Cache kedua, umur berbeda.** `hermes-data-v1` menyimpan hanya dua endpoint
baca — `GET …/api/sessions` dan `GET …/api/session` — dan **sengaja tidak
di-key oleh versi**: satu deploy tidak boleh menghapus satu-satunya salinan sesi
yang bisa dibaca pengguna di dalam kereta. Batas yang benar bukan versi, tapi
**identitas**, jadi ia dibersihkan saat sign-out (pesan eksplisit ke worker) dan
saat sebuah revalidasi mendapat 401/403.

Regex endpoint-nya di-anchor ke akhir path (`/(?:^|\/)api\/sessions$/`). Itu
bukan kerapian: `/api/sessions/events` dan `/api/sessions/gateway/stream` adalah
SSE, dan menyerahkan body ter-cache ke `EventSource` merusak sinkronisasi
real-time dengan cara yang terlihat seperti bug server. Diverifikasi di browser:
offline, keduanya gagal seperti seharusnya.

**Stale-while-revalidate dibuat opt-in per request, bukan global.** Ini
argumen keamanannya, dan ia mengubah rencana: menerapkan SWR ke *setiap*
`/api/sessions` berarti refetch setelah **ganti profil** dilayani dari cache —
kedipan sesi milik profil sebelumnya. Halaman mengirim `X-Hermes-Cache: swr`
pada **tepat satu** request, boot dingin sidebar, di mana alternatifnya adalah
skeleton. Setiap poll berikutnya tetap network-first.

Notifikasi ke halaman **dijaga oleh perbandingan body**, bukan dikirim setiap
kali. Tanpa itu: layani cache → beri tahu → halaman refetch → layani cache →
beri tahu → live-lock. Dengan itu, pass kedua menemukan keduanya sama dan
berhenti sendiri.

**Antrian kirim: IndexedDB, di-flush oleh halaman.** Background Sync akan jadi
jawaban yang jelas, dan Safari tidak mengimplementasikannya — sementara iOS
Safari adalah tempat paling mungkin sebuah tab Hermes berada saat offline. Jadi
`static/outbox.js` (365 baris) memakai IndexedDB (bertahan melewati crash tab dan
restart browser, tidak seperti array in-memory) dan flush dipicu halaman:
`online`, `visibilitychange`, dan saat load.

Bukan localStorage, meski antrian per-sesi yang sudah ada memakainya: ini
memegang **satu-satunya salinan** tulisan pengguna yang belum terkirim, ditulis
dari jalur kegagalan, dan localStorage sinkron, ~5 MB, serta hal pertama yang
dihapus "clear site data".

Pemicu enqueue-nya presisi, bukan dugaan: `api()` melempar `TypeError` mentah
dari `fetch` saat request tidak pernah mencapai server (sudah retry 3× dengan
backoff), dan **setiap** error HTTP yang ia lempar membawa `.status` numerik.
Jadi "TypeError tanpa status" adalah sinyal, bukan perkiraan konektivitas.
Kalau antrian **menolak** (private browsing, kuota), kodenya jatuh ke jalur error
lama yang memulihkan draft — teks pengguna harus selamat lewat salah satu jalan.

**Shell offline.** Urutannya: `'./'` yang ter-cache (aplikasi sungguhan, yang
kini boot dengan data) → `static/offline.html` → string literal, sebagai jaring
terakhir. Yang kedua ada untuk satu kasus yang tidak bisa ditutup shell: cold
start di mana `'./'` belum pernah di-cache. Ia read-only atas prinsip — setiap
tulisan butuh server, dan kontrol yang diam-diam tidak melakukan apa pun lebih
buruk daripada tidak ada kontrol — dan me-render transkrip dengan
`textContent`, bukan `innerHTML`.

#### P2.2 — 40 kontrol tanpa nama, dan satu baris yang menghapusnya

`index.html`: 206 `<button>`, 87 `aria-label`. Diukur di Chromium sungguhan,
**40 kontrol tidak punya nama yang bisa dibacakan sama sekali** — termasuk
**setiap** tab di rail kiri, **setiap** aksi di header panel, tombol dikte, dan
tombol voice mode. Di VoiceOver atau TalkBack masing-masing berbunyi, kira-kira,
"button".

Penyebabnya satu baris yang bermaksud baik. Tombol icon-only membawa
`data-tooltip` + `data-i18n-title`, dan `applyLocaleToDOM()`:

```js
el.setAttribute('data-tooltip', val);
if (el.hasAttribute('title')) el.removeAttribute('title');
```

`data-tooltip` adalah tooltip CSS — `::after` dengan `content`. Tidak ada
assistive technology yang membacanya. Dan cabang itu menghapus `title`, satu-satunya
atribut yang **bisa** dibaca, untuk mencegah tooltip native ikut menyala (#1775).
**Jadi melokalkan halaman adalah yang menghapus nama terakhirnya.**

| Sebelum | Sesudah |
|---|---|
| 40 kontrol ter-render tanpa nama | **0** |
| 87 `aria-label`, 17 terlokalkan | 148 `aria-label`, **58** terlokalkan |

Perbaikannya berlapis, sengaja:

1. **38 tombol** mendapat `aria-label` + `data-i18n-aria-label` eksplisit di
   markup — bekerja sebelum JS jalan, dan terlihat saat review.
2. **23 tombol lain** ternyata punya `aria-label` **hanya Inggris** di samping
   tooltip yang terlokalkan. Itu regresi untuk 15 dari 16 bahasa, dan lebih
   buruk dari tooltip yang digantinya, karena tooltipnya *dulu* terlokalkan.
   Semuanya kini membawa kunci yang sama dengan tooltipnya, dan sebuah test
   menolak keduanya memakai kunci berbeda.
3. **`applyLocaleToDOM` memasok `aria-label`** saat elemen tidak punya nama
   apa pun — jaring untuk tombol tooltip yang dibangun di JS, yang tidak
   terlihat test statis. Dijaga agar **tidak pernah** menimpa label yang sudah
   ada, karena `aria-label` menang atas teks: penulisan tanpa syarat akan
   membekukan label dinamis ("78% used · $0.04", nama model sekarang) di string
   generik yang basi.

Lima tombol **sengaja dikecualikan** dan alasannya ada di test: label mereka
*adalah* isinya, ditulis JS saat mereka jadi terlihat, dan `display:none`
sebelumnya. `aria-label` statis di sana adalah regresi, bukan perbaikan.

**Fokus: bukan sekadar Tab trap.** Sheet bawah sudah men-trap Tab. Di ponsel itu
tidak membeli apa pun: pengguna VoiceOver/TalkBack **tidak** menekan Tab, mereka
menyapu pohon aksesibilitas, dan handler Tab tidak bisa menghentikannya. Mereka
akan menyapu keluar dari sheet terbuka ke chat di belakangnya tanpa tanda bahwa
mereka sudah keluar.

Yang benar-benar mengurung adalah `aria-modal="true"` plus `aria-hidden` +
`inert` pada semua di luarnya. Itu sekarang satu implementasi,
`HermesA11y.isolate()`, dipakai **tiga** overlay: sheet bawah (yang punya trap
sendiri), drawer sidebar, dan slide-over workspace — **dua terakhir sebelumnya
tidak punya apa-apa**: tanpa role, tanpa aria-modal, tanpa pemindahan fokus,
tanpa Escape.

Drawer dan slide-over dipasang lewat **MutationObserver pada kelasnya**, bukan
panggilan di setiap toggle. `mobile-open` ditambahkan di **lima** tempat di
`boot.js` dan `panels.js` dan dihapus di dua; menjahit `isolate()`/`release()` ke
ketujuhnya berarti orang berikutnya yang menambah yang kedelapan mendapat drawer
yang kembali tidak aksesibel secara sunyi — persis kegagalan yang menghasilkan
keadaan ini. Kelas itu satu fakta yang disetujui CSS dan kode ini, jadi
mengamatinya menutup semua call site, termasuk yang belum ditulis. Ia juga
mengoreksi diri: kelasnya hanya diset di mode overlay, jadi di lebar tablet —
di mana sidebar in-flow dan **tidak boleh** diisolasi — observer-nya tidak
pernah menyala.

Backdrop sheet **tidak boleh** jadi `inert`: ia target tap-untuk-menutup.
Menandainya `aria-hidden` saat dibuat membuat `isolate()` melewatinya
seluruhnya — karena ia hanya menyentuh sibling yang belum tersembunyi, aturan
yang juga menjaga `release()` tidak pernah **membuka** sesuatu yang bukan
miliknya untuk dibuka.

**Live region punya lantai, bukan hanya isi.** Live region yang disuapi setiap
perubahan state lebih buruk daripada tidak ada: antrian bicara menumpuk dan
pengguna tidak bisa mendengar apa pun, termasuk yang sedang ia ketik. Jadi:
teks identik tidak pernah diulang, ada jarak minimum antar ucapan, dan **burst
di dalam jarak itu mengecil menjadi satu ucapan berisi teks terbaru** — bukan
lima ucapan berantre. Streaming diumumkan pada **transisi** `setBusy`, bukan
pada setiap panggilan. Diukur di browser: **lima** panggilan `setBusy`
menghasilkan **dua** ucapan.

**Kartu approval** sudah `role="alertdialog"` dengan `aria-labelledby` +
`aria-describedby`, dan fokus sudah dipindahkan ke tombol pertama. Dua celah:

1. `approvalCmd` — **perintah yang akan dijalankan** — tidak ada di
   `aria-describedby`. Hal paling penting untuk didengar sebelum menjawab tidak
   pernah diucapkan. Sekarang ada.
2. Saat fokus ada di composer, fokus **sengaja tidak** dirampas — merampas fokus
   di tengah kalimat adalah kegagalan aksesibilitas tersendiri. Tapi approval
   memblokir agent sampai dijawab, jadi diam juga bukan pilihan: ia diumumkan
   `assertive`. Dijaga `!sameApproval`, karena poller-nya me-render ulang
   approval yang sama tiap beberapa detik.

Dua kunci i18n yang **mati** ikut ketangkap gerbang nama: `outline_toggle` tidak
ada di **satu pun** dari 16 bundel, dan `workspace_add_title` hanya ada di `pt`.
Keduanya `data-i18n-title`, jadi chip Outline dan aksi "Add space" tidak pernah
terlokalkan di mana pun. Keduanya kini lengkap 16 bahasa.

#### Biaya, dinyatakan apa adanya

| Berkas | Delta gzip |
|---|---|
| `static/outbox.js` (baru) | +4,24 KiB |
| `static/boot.js` (`HermesA11y` + observer overlay) | +3,64 KiB |
| `static/messages.js` (enqueue offline + pengumuman approval) | +1,88 KiB |
| `static/ui.js` (`_vendorAssetUrl` + transisi busy) | +1,56 KiB |
| `static/sessions.js` (header SWR) | +0,28 KiB |
| **Total cold path** | **+11,6 KiB** |

Cold path: **955,1 KiB** gzip, anggaran `test_frontend_payload_budget.py`
1.042,0 KiB. `static/offline.html` (5,0 KiB) **tidak** di cold path — ia hanya
di-pre-cache.

`outbox.js` **harus** di cold path: ia perlu ada **sebelum** kirim pertama gagal,
dan flush-nya harus jalan saat load. Melazy-kannya berarti kirim pertama yang
gagal saat offline tidak punya tempat untuk pergi — persis kasus yang jadi alasan
ia ada. 4,2 KiB agar pesan pengguna tidak hilang adalah pertukaran yang saya
ambil dengan sadar, di dalam anggaran yang dipasang P1.0.

#### Verifikasi

Semua di bawah dijalankan, bukan disimpulkan dari kode.

| Yang diperiksa | Hasil |
|---|---|
| CSP tersaji | Nol `jsdelivr` di `script-src`/`worker-src`/`connect-src` |
| `.mjs` tersaji | `application/javascript; charset=utf-8`, `max-age=31536000, immutable` |
| Mermaid dari vendor | Diagram ter-render, `typeof mermaid === 'object'` |
| PDF.js dari vendor | Blob module import berhasil, `getDocument` ada |
| Pre-cache ↔ permintaan | 29 entri shell; 8 URL yang tadinya mismatch kini **cocok semua** |
| Cache data | `/api/sessions?...` tersimpan setelah request pertama yang dikontrol worker |
| Offline: daftar sesi | Dilayani dari cache (SWR **dan** plain) |
| Offline: varian query lain | `TypeError: Failed to fetch` — tidak ada match kunci yang salah |
| Offline: `/api/session` 404 | **Tidak** ter-cache (hanya 200 JSON) — gagal seperti seharusnya |
| Offline: `/api/projects` | Tidak diintersep — gagal |
| Offline: `/api/sessions/events` | Tidak diintersep — SSE tetap SSE |
| Offline: navigasi tanpa `'./'` | `static/offline.html`, memperlihatkan sesi ter-cache + antrian |
| Offline: navigasi dengan `'./'` | Aplikasi sungguhan boot, banner offline, **nol** pageerror |
| Outbox | `enqueue`/`list`/`count`/`clear` round-trip lewat IndexedDB |
| Nama aksesibel | **40 → 0** kontrol ter-render tanpa nama |
| Lokalisasi `aria-label` | `ja`: チャット / 設定 / 新しい会話 / アウトライン |
| Drawer sidebar | `role=dialog`, `aria-modal`, berlabel, fokus masuk, luar `inert`, Escape menutup, semua dipulihkan |
| Slide-over workspace | Sama; atribut dibersihkan saat ditutup |
| Sheet bawah | Fokus ke kontrol pertama, luar `inert`, backdrop `aria-hidden` tapi **tidak** `inert`, Escape menutup, fokus kembali ke opener |
| Live region | 5 `setBusy` → **2** ucapan |
| Kartu approval | `aria-describedby` berisi `approvalCmd`; semua tombol bernama |
| Konsol | Nol error di seluruh pengujian di atas |
| Test baru | 59 (`test_offline_shell_and_outbox.py` 31, `test_button_accessible_names.py` 28) |
| Suite penuh | **15.078 lulus**, 218 dilewati, 2 xfailed, 1 xpassed, **2 gagal** — keduanya pre-existing dan sama dengan yang dicatat §0.10 (`test_5774b` setgid di tmpfs macOS, `test_issue6067` layout helper) |

> **Satu jebakan suite yang layak dicatat.** Sebuah run yang lebih awal juga
> menggagalkan `test_static_asset_resolver::test_service_worker_and_favicon_follow_selected_static_root`,
> dan itu **bukan** regresi: `WEBUI_VERSION` membawa suffiks `-dirty-<sha1 dari
> git diff HEAD>` (`api/updates.py:_dirty_suffix`), jadi menyunting berkas apa
> pun **saat** suite berjalan mengubah token yang di-substitusikan ke `sw.js` di
> tengah jalan dan assertion byte-per-byte-nya gagal. Ia lulus di run yang
> bersih. Kalau test itu gagal sendirian, periksa dulu apakah ada yang mengedit
> working tree, sebelum mencari sebab lain.

**Delapan test lama diperbarui, dan alasannya layak dicatat** karena enam di
antaranya gagal dengan cara yang sama: **assertion-nya memindai komentar.** Test
yang melarang substring (`localStorage`, `registration.sync`, `innerHTML`,
`**Error:**`, `'./'`, `cdn.jsdelivr.net`) gagal pada prosa yang menjelaskan
*mengapa* berkasnya menghindari hal itu. Membiarkannya akan mendorong orang
berikutnya menghapus penjelasannya, bukan mempertahankan sifatnya — jadi
masing-masing sekarang memindai kode dengan komentar dibuang. Dua sisanya nyata:
`test_issue347` memakai jendela 2.200 karakter tetap yang kebetulan sudah nyaris
penuh (sekarang brace-matched), dan `test_japanese_locale` memakai regex yang
mengandaikan **tidak ada** brace antara `ja: {` dan `_label:` — yang berhenti
benar begitu sebuah key di atasnya memakai placeholder `{0}` (sekarang memakai
`extract_locale_block` yang sudah ada di berkas itu).

Satu perubahan perilaku ikut jatuh dari test yang gagal: `signOut()` sebelumnya
akan **menelan** kegagalan pembersihan lokal ke dalam `catch` miliknya dan tidak
pernah redirect. Server sudah membatalkan sesi pada titik itu, jadi kegagalan
membersihkan salinan offline tidak boleh meninggalkan pengguna di halaman yang
masih tampak masuk. Pembersihannya kini best-effort dan non-fatal.
### 0.12 P4 terlaksana — dan gerbang P4.1 akhirnya diukur (2026-08-31)

**P4.1 punya prasyarat yang tertulis di rencananya sendiri:** *"Kerjakan hanya
jika angka Lighthouse setelah P1 masih tidak dapat diterima."* Angka itu
**belum pernah diukur** — §4.6 menandainya `[belum terverifikasi]`. Jadi hal
pertama yang dikerjakan di sini adalah mengukurnya, bukan menebaknya.

Lighthouse 12 dijalankan sungguhan (preset mobile default: throttling CPU 4×,
profil jaringan 4G lambat), 3 run, nilai median:

| | Skor mobile | FCP | LCP | TBT | TTI |
|---|---:|---:|---:|---:|---:|
| Setelah P2 | **71** | 2.855 ms | 7.824 ms | 58 ms | 8.578 ms |
| Setelah perbaikan gzip | **76** | 1.956 ms | 5.952 ms | 45 ms | 7.663 ms |
| Setelah P4.2 | **75** | 1.956 ms | 6.901 ms | 43 ms | 7.806 ms |

**Gerbang P4.1 TERBUKA: 76 < 85.** Rinciannya di
[§0.12.3](#0123-p41--gerbangnya-terbuka-pekerjaannya-tidak-dikerjakan).

#### 0.12.1 Temuan terbesar sesi ini bukan bagian dari P4

Audit pertama menandai `uses-text-compression` senilai ~900 ms pada URL kosong —
yaitu **dokumen utamanya sendiri**:

```
GET /            Content-Length: 231085     (tanpa Content-Encoding)
GET /static/style.css   Content-Length: 101383   Content-Encoding: gzip
```

**Shell aplikasi dikirim tanpa kompresi sama sekali.** `_serve_static` meng-gzip
setiap aset, dan `j()` meng-gzip setiap respons JSON — tapi `t()`, yang menyajikan
`/`, `/index.html`, dan `/session/<id>`, tidak pernah mendapat perlakuan yang
sama. Jadi **item terbesar di jalur kritis adalah satu-satunya yang tidak
dikompresi siapa pun**:

| | Sebelum | Sesudah |
|---|---:|---:|
| `GET /` | 231.085 byte | **44.344 byte** |

**−188 KB (−81%) di setiap cold load** — lebih besar daripada P1.3 (−67 KiB) dan
P1.4 (−18,4 KiB) digabung, dari menyalin pola tiga baris yang sudah dipakai
`j()`. Hasil terukurnya: **+5 poin Lighthouse, FCP −899 ms, LCP −1.872 ms,
TTI −915 ms.**

Level 6, bukan 4 atau 9, dan itu diukur bukan dikira: level 9 memberi 0,2 KiB
tambahan untuk 40% CPU lebih; level 4 menghemat 1,3 ms tapi membayar 2 KiB.

**Mengapa anggaran P1.0 tidak melihatnya.** Gerbang itu mem-parsing `index.html`
untuk menemukan **aset yang dirujuknya**, dan menimbang berkas di disk — ia tidak
pernah menimbang **dokumennya sendiri**, dan tidak pernah melihat header respons.
Sebuah gerbang byte yang mengukur berkas, bukan transfer, secara struktural buta
terhadap header `Content-Encoding` yang tidak diset. Itu bukan bug di gerbangnya;
itu batas yang layak dicatat.

#### 0.12.2 P4.2 — dan koreksi terhadap "nol dari sembilan"

Rencana menyatakan: *"Nol dari sembilan item ini ada di codebase hari ini —
diverifikasi: tidak ada `startViewTransition`, `navigator.vibrate`,
`share_target`, `setAppBadge`, atau `navigator.share` di `static/`."*

Grep itu memeriksa **lima nama API**, lalu kesimpulannya digeneralisasi ke
sembilan item. **Tiga dari sembilan sudah ada**, dan ketiganya lebih lengkap dari
deskripsi rencananya:

| # | Item | Keadaan sebenarnya |
|---|---|---|
| 1 | Share Target API | ✗ tidak ada → **dibuat** |
| 2 | Web Share API | ✗ tidak ada → **dibuat** |
| 3 | Optimistic UI | ✅ **sudah ada** — `messages.js` mem-push bubble user dan me-render **sebelum** POST `/api/chat/start` |
| 4 | Skeleton screen | ✅ **sudah ada** — `showSessionListSkeleton` + `.skeleton-row`, termasuk varian reduced-motion dan jalur "skeleton jujur" untuk profil yang diketahui kosong |
| 5 | App Badging API | ✗ tidak ada → **dibuat** |
| 6 | Pull-to-refresh | ⚠️ **ada di elemen yang salah** — terpasang di `#messages`, PWA-only, label hardcoded → **dipindahkan/diperluas** |
| 7 | View Transitions API | ✗ tidak ada → **dibuat** |
| 8 | Haptic feedback | ✗ tidak ada → **dibuat** |
| 9 | Mode suara hands-free | ✅ **sudah ada** — voice mode berbasis turn (#1333): listen → send → TTS → listen, dengan fallback TTS server, preferensi voice/rate/pitch, dan recovery TTS browser |

Jadi yang dikerjakan adalah **lima yang benar-benar hilang plus satu yang salah
tempat**, bukan sembilan. Tiga yang sudah ada **tidak** diimplementasikan ulang —
dan `tests/test_native_platform_integrations.py` kini memasang pin regresi untuk
ketiganya, supaya pembacaan "P4.2 belum dimulai" di masa depan tidak menghasilkan
dua implementasi dari perilaku yang sama.

**Satu modul, `static/native.js` (397 baris, 5,1 KiB gzip).** Kelimanya adalah
"minta sesuatu ke platform lalu tangani saat ia menolak", dan kelimanya dipanggil
dari beberapa tempat. Menyebar `try{ navigator.x() }catch{}` di setiap call site
adalah cara mendapatkan lima fallback yang sedikit berbeda dan salah satunya
melempar di iOS.

**Share Target: dua jalur, satu konsumen.**

- `sw.js` menangkap POST-nya, membaca `FormData` langsung, dan menaruh teks
  **dan berkas** di cache `hermes-share-inbox`. Ini yang membuat berkas bekerja
  tanpa round-trip upload dan tanpa state di server.
- `/share-target` di server adalah fallback untuk saat tidak ada worker yang
  mengontrol halaman. Teks saja, lewat query string, dengan flag
  `share_files_dropped` — menghilangkan berkas tanpa penjelasan terlihat seperti
  kehilangan data.

Urutan pengecekan di `sw.js` load-bearing: sebuah share datang sebagai **POST yang
`mode`-nya `navigate`**, jadi cabang share-target harus diuji **sebelum** handler
navigasi, atau POST-nya diteruskan ke jaringan dan jalur worker tidak pernah
jalan. Redirect-nya **303**, bukan 302: 303 mengubah POST menjadi GET, sehingga
refresh tidak mengirim ulang share yang sama.

Dua aturan yang lebih penting dari fiturnya sendiri, keduanya dijaga test:
**tidak pernah auto-send** (share sheet itu satu tap; mengirim pesan ke agent
karena satu tap tidak bisa dibatalkan) dan **tidak pernah menimpa draft**
(ditambahkan dengan baris kosong, bukan menggantikan).

`/share-target` **CSRF-exempt**, dan itu perlu alasan bukan kelalaian: POST-nya
disintesis oleh share sheet OS, jadi tidak ada tempat token sesi bisa berasal.
Aman karena handler-nya **tidak menulis state server apa pun** — efek yang bisa
dicapai dengan memalsukannya adalah menaruh teks di composer, yang bisa dilakukan
halaman mana pun dengan menautkan ke `/?share_text=…`. Composer tidak pernah
auto-send, dan teksnya dimasukkan sebagai teks.

**View Transitions: propertinya bukan animasinya.** `viewTransition()`
membungkus update DOM yang load-bearing di `switchPanel`, jadi callback-nya
**wajib** tetap jalan saat API-nya tidak ada, saat reduced-motion aktif, saat
sudah ada transisi berjalan, dan saat tab tersembunyi. Kalau tidak, UI berhenti
merespons navigasi — kegagalan spektakuler untuk fitur kosmetik. Diverifikasi di
browser: **3 panggilan → 3 callback jalan**, yang kedua (re-entrant) benar tidak
memulai transisi tapi tetap menerapkan perubahannya.

Yang juga penting: hanya blok class-toggle sinkron yang masuk ke dalam callback.
Delapan `await loadX()` sesudahnya **di luar** — sebuah transisi menahan snapshot
visual sampai callback-nya selesai, jadi request jaringan di dalamnya akan
membekukan UI selama request itu.

**Pull-to-refresh: satu implementasi, dua scroller.** Ia lahir sebagai IIFE
anonim yang terikat ke `#messages`; rencana memintanya di **daftar sesi**. Salinan
kedua dari handler gestur 60 baris adalah cara mendapatkan dua gestur yang
berperilaku berbeda di satu layar — jadi ia difaktorkan jadi
`_attachPullToRefresh(el, {onRefresh})` dan dipanggil dua kali. Daftar sesi
**tidak** di-gate ke standalone (menarik daftar untuk menyegarkannya adalah idiom
mobile biasa di tab browser juga, dan `overscroll-behavior-y:contain` sudah
mencegah gestur itu berantai ke pull-to-refresh browser); transkrip
mempertahankan gate aslinya. Labelnya kini terlokalkan, indikatornya
`role="status"` + `aria-live` (panah berputar tidak memberi apa pun ke pembaca
layar), dan dibangun dengan panggilan DOM bukan `innerHTML` karena isinya string
terjemahan.

**Haptics di dua tap yang mengubah sesuatu**, bukan di navigasi: kirim, dan
jawab approval (`warn` untuk deny, supaya kedua hasilnya bisa dibedakan tanpa
melihat). Haptic approval **mendahului** POST-nya — buzz yang datang 400 ms
kemudian terbaca sebagai gangguan, bukan konfirmasi. Di-gate pada
`navigator.userActivation`: Chromium mencatat *"Blocked call to
navigator.vibrate…"* ke konsol, dan repo ini punya smoke test yang menuntut
konsol bersih.

**App Badge digerakkan dari satu map**, `_approvalPendingBySession`, yang
dilewati baik jalur set maupun clear — jadi badge tidak bisa menyimpang dari apa
yang aplikasi yakini sedang menunggu. Dijumlahkan lintas sesi. Handler `push` di
worker memakai `setAppBadge()` **tanpa argumen** dengan sengaja: payload-nya tidak
membawa hitungan, dan bentuk tanpa argumen adalah "unspecified number" menurut
spec — sebuah titik, bukan angka yang salah.

#### 0.12.3 P4.1 — gerbangnya terbuka, pekerjaannya **tidak** dikerjakan

76 < 85. Prasyarat rencananya terpenuhi, dan prasyarat kedua ("hanya dengan
anggaran P1.0 sudah menjaga hasilnya") juga terpenuhi. Jadi P4.1 **berwenang**
untuk dikerjakan.

**Saya tidak mengerjakannya, dan alasannya bukan waktu.** Rencananya sendiri
menilainya **1–2 minggu · risiko tinggi**, dan tiga berkas itu adalah jalur
render pesan. Refactor modul yang setengah jadi di jalur render adalah hasil
terburuk yang mungkin dari sesi ini — lebih buruk daripada tidak memulainya.

Yang bisa saya berikan adalah **datanya**, supaya keputusannya bukan tebakan.
Diukur di HEAD ini:

| Peluang tersisa (Lighthouse) | Hemat |
|---|---:|
| Reduce unused JavaScript | **2.510 ms** |
| Minify JavaScript | 900 ms |
| Eliminate render-blocking resources | 688 ms |
| Reduce unused CSS | 540 ms |

JavaScript tak terpakai, per berkas:

| Berkas | Dikirim | Tak dieksekusi saat load | % |
|---|---:|---:|---:|
| `ui.js` | 281,0 KB | 249,7 KB | **89%** |
| `panels.js` | 158,1 KB | 147,2 KB | **93%** |
| `messages.js` | 115,7 KB | 111,7 KB | **97%** |
| `sessions.js` | 115,9 KB | 88,1 KB | 76% |

**Dua catatan yang mengubah bentuk P4.1, dan tidak ada di rencana:**

1. **"Tak dieksekusi saat load" ≠ "bisa dihapus".** Sebagian besar byte itu
   berjalan nanti, saat fiturnya dipakai. Jadi imbalan nyatanya menuntut
   pemisahan **per fitur** dengan pemuatan tertunda — persis kesimpulan yang
   sudah dicapai investigasi P1.2 untuk `panels.js` (74 handler `onclick=` inline,
   101 pemanggil lintas berkas, rekomendasi: delegasi event). Angka −498,3 KiB di
   rencana adalah total byte, bukan byte yang bisa dihapus.

2. **Biaya terbesar yang tersisa mungkin bukan JavaScript.** `style.css`
   render-blocking, menyumbang 904 ms, dan **91,6% tidak terpakai saat load**
   (92.898 byte). §0.10 menolak P1.4 dengan benar sebagai kerja **byte**
   (−18,4 KiB gzip, rasio terburuk di backlog) — tapi Lighthouse mengukur biaya
   `style.css` sebagai **panjang jalur kritis**, bukan berat, dan itu framing yang
   berbeda dengan kesimpulan yang mungkin berbeda. TBT hanya 43 ms: main thread
   **bukan** hambatannya. LCP-lah, dan LCP menunggu CSS.

Rekomendasi saya, jika P4.1 dibuka: **ukur dulu efek CSS non-blocking pada LCP
sebelum menyentuh tiga berkas render pesan itu.** Ia jauh lebih murah dan
menyerang metrik yang benar-benar buruk. Itu tetap keputusan Anda; P4.1 dan P1.4
sama-sama masih terbuka dan tidak ada yang memblokirnya.

#### 0.12.4 Biaya dan verifikasi

| Berkas | Delta gzip |
|---|---|
| `static/native.js` (baru) | +5,12 KiB |
| `static/boot.js` (share drain, Web Share, PTR) | +2,22 KiB |
| `static/style.css` (view transitions, PTR) | +1,01 KiB |
| `static/messages.js` (badge, haptics) | +0,72 KiB |
| `static/ui.js` (refactor PTR) | +1,23 KiB |
| **Total P4** | **≈ +10,3 KiB** |

**Anggaran P1.0 menyala, dan itu gerbangnya bekerja:** total 1.072.251 byte
melewati 1.067.000 sebesar **5.251 byte** — praktis seluruhnya `native.js`.
Anggarannya dinaikkan ke **1.083.000** dengan alasannya ditulis di berkasnya,
persis prosedur yang diinstruksikan test itu sendiri. Headroom-nya **+1%, bukan
+2%** seperti angka aslinya: 2% dari total baru adalah 21 KiB — cukup untuk modul
seukuran `native.js` lagi mendarat tanpa terlihat, yang justru mengalahkan
tujuannya.

`native.js` dimuat **eager**, dan itu pilihan: empat dari lima kapabilitasnya
hanya dipanggil dari gestur pengguna dan akan senang di-lazy — tapi inbox Share
Target dikuras **saat boot**, karena aplikasi bisa dibuka **oleh** sebuah share,
dan menunda itu di belakang fetch berarti teks yang dibagikan datang setelah
composer sudah tampil.

Semua di bawah dijalankan, bukan disimpulkan dari kode.

| Yang diperiksa | Hasil |
|---|---|
| Lighthouse mobile, 3 run | 71 → **76** (gzip) → 75 (P4.2); selisih 76↔75 **di dalam variansi** — spread LCP 5.815–6.909 ms di dalam satu konfigurasi |
| `GET /` terkompresi | 231.085 → **44.344** byte; klien tanpa `Accept-Encoding: gzip` **tidak berubah** (231.085) |
| Manifest tersaji | `share_target` lengkap, `action` relatif (dalam scope) |
| Share Target — navigasi POST sungguhan | SW menangkap → stash → 303 → shell aplikasi → **composer berisi teks yang dibagikan** → URL dibersihkan |
| Share Target — berkas | `note.txt` (5 byte) mendarat di cache, dibaca kembali sebagai `File`, di-stage lewat `addFiles` |
| Share Target — fallback server | POST multipart → `303 ./?share_text=…&shared=1`; composer berisi teks; **tanpa** service worker |
| Share Target — POST kosong / body rusak / berkas terlampir | ketiganya **tetap 303**, tidak ada 500 |
| `viewTransition` | 3 panggilan → **3 callback jalan**; re-entrant tidak memulai transisi kedua; `data-vt` dibersihkan |
| Panel switch di bawah transisi | tasks / skills / chat ketiganya tetap `active` |
| Badge | `setBadge(3)` → ulang → `clearBadge()`, ketiganya resolve tanpa throw di tab biasa |
| Haptic tanpa dukungan | no-op, return `false` |
| `share()` tanpa dukungan | `'unsupported'`, bukan throw |
| PTR | terpasang di `#sessionList`; **tidak** di `#messages` di headless (bukan standalone — benar) |
| `tests/browser_smoke.py` | lulus, **nol** error konsol |
| `tests/browser_responsive.py` | **9/9 viewport** |
| Test baru | 41 (`tests/test_native_platform_integrations.py`) |
| Suite penuh | **15.120 lulus**, 218 dilewati, **2 gagal** — keduanya pre-existing dan sama dengan §0.10/§0.11 (`test_5774b` setgid di tmpfs macOS, `test_issue6067` layout helper) |

**Empat test lama diperbarui.** `test_sprint9::test_no_duplicate_function_definitions`
menangkap dua tabrakan nama yang saya buat sendiri: `_label` (ui.js ↔ boot.js) dan
`_init` **dua kali di boot.js** — satu dari modul a11y overlay P2, satu dari share
drain P4. Keduanya closure-scoped, jadi tidak ada tabrakan runtime; tapi seluruh
berkas ini berbagi satu global scope, gerbangnya benar tidak membedakannya, dan
pembaca yang meng-grep `function _init` juga tidak bisa. Diganti jadi
`_ptrLabel`, `_initOverlayA11y`, `_initShareDrain`.

**Tiga test lain diperbarui.** Dua gagal karena node driver mengekstrak satu
fungsi ke dalam konteks `vm` kosong, di mana referensi ke fungsi tetangga adalah
ReferenceError — diperbaiki dengan `typeof` guard yang **sudah dipakai baris di
bawahnya** (`if (typeof syncTopbar === 'function')`), yang juga menyatakan
kebenarannya: badge adalah enhancement opsional, bukan bagian dari kontrak
approval. Yang ketiga menyematkan ekspresi inline pull-to-refresh yang persis;
karena PTR kini satu factory untuk dua scroller, satu string hardcoded hanya bisa
menggambarkan salah satunya — assertion-nya diganti dengan propertinya (keduanya
menyegarkan **data**, `reload()` tetap di belakang guard-nya) dan **diperkuat**
dengan test kedua bahwa daftar sesi tidak di-gate ke standalone sementara
transkrip masih.

---

## 0.13 Ringkasan Terbaru untuk Orang Awam (Update 2026-08-31)

> **Bagian ini ditulis dengan bahasa sesederhana mungkin.** Kalau Anda hanya
> ingin tahu "sudah selesai apa saja, sisanya apa, dan bagaimana cara
> menjalankannya di komputer sendiri" — cukup baca bagian ini. Bagian-bagian di
> atas (§0.1–§0.12) adalah catatan teknis yang lebih detail.
>
> **Diverifikasi pada commit `351dcde1`** (commit paling baru saat dokumen ini
> diperbarui). Semua tanda ✅ di bawah sudah dicek langsung ke dalam kode, bukan
> sekadar disalin dari catatan lama.

### Apa itu proyek ini, singkatnya

Ini adalah **tampilan web (website) untuk Hermes Agent** — sebuah asisten AI yang
berjalan di server Anda sendiri. Dengan proyek ini, Anda bisa mengobrol dengan
agent AI lewat browser (di laptop maupun HP), bukan lewat terminal. Dibangun
dengan **Python (backend)** dan **JavaScript biasa (frontend)** — sengaja **tanpa
framework, tanpa build step** supaya ringan dan gampang dipasang.

### Sudah selesai apa saja? (dari yang paling mendasar ke yang paling canggih)

Bayangkan pengembangan ini seperti tangga bertingkat. Berikut kondisi tiap anak
tangga sekarang:

| Tahap | Isi | Status |
|---|---|---|
| **Fase 0 — Deploy dasar** | Bisa dipasang di VPS, dibuka dari HP, aman (pakai password/HTTPS) | ✅ **Kodenya siap.** Sisa satu langkah yang hanya bisa Anda lakukan sendiri: pasang di server ber-HTTPS lalu coba dari HP asli |
| **Fase 1 — Perbaiki yang rusak** | Layout tablet diperbaiki, semua file pihak ketiga (Prism, xterm) dibawa ke dalam repo (tak lagi ambil dari internet), scroll melebar dihilangkan, ada test otomatis untuk berbagai ukuran layar | ✅ **Selesai** |
| **Fase 2 — Nyaman di HP** | Semua fitur & pengaturan bisa diakses dari HP, ada panel geser dari bawah (bottom sheet), zoom diizinkan di browser, gestur usap, bahasa Indonesia ditambahkan (sebagian) | ✅ **Selesai** (kecuali 1 hal kecil: filter tabel di HP, lihat daftar sisa) |
| **Fase 3 — Notifikasi push** | Dapat notifikasi di HP walau browser sudah ditutup (misalnya saat agent butuh persetujuan atau tugas panjang selesai) | ✅ **Selesai** — dibuat tanpa menambah paket baru |
| **Fase 4 — Kecepatan** | Aplikasi jadi lebih ringan & cepat dibuka; bisa jalan sebagian tanpa internet | 🟡 **Selesai sebagian** — ukuran unduhan awal turun **31,7%** (dari ~1.497 KB jadi ~1.022 KB). Dua pekerjaan dihentikan sengaja karena risikonya lebih besar dari manfaatnya |
| **Fase 5 — Rasa seperti aplikasi asli** | Getaran saat menekan tombol, badge angka di ikon, berbagi ke aplikasi lain, animasi halus, dukungan pembaca layar (aksesibilitas) | ✅ **Sebagian besar selesai** — digabung ke dalam P2.2 (aksesibilitas) dan P4.2 (rasa native) |

**Kesimpulan gampangnya:** aplikasi ini **sudah bisa dipakai sehari-hari dari HP
dan laptop hari ini.** Yang tersisa bukan fitur dasar yang belum ada, melainkan
penghalusan (bahasa Indonesia yang lebih lengkap, sedikit optimasi kecepatan
tambahan) dan satu langkah pemasangan di server yang harus Anda kerjakan sendiri.

### Yang BELUM selesai — dan kenapa

Beberapa hal sengaja **dihentikan** setelah diukur, karena ternyata usahanya
besar tapi manfaatnya kecil, atau berisiko merusak yang sudah jalan. Ini
keputusan sadar, bukan pekerjaan yang terlupa.

| Sisa pekerjaan | Status | Kenapa belum |
|---|---|---|
| **Bahasa Indonesia belum 100% lengkap** | Belum | Baru ±163 dari 1.713 kata/frasa yang diterjemahkan (bagian inti sudah, seperti chat, login, navigasi). Sisanya (pengaturan, onboarding, cron) sengaja dibiarkan Bahasa Inggris dulu — menerjemahkan menu berbahaya seperti "matikan keamanan" secara asal justru lebih berisiko |
| **Filter tabel di HP** | Belum | Perlu membuat komponen baru. Ini penambahan fitur, bukan perbaikan, jadi ditunda sampai ada yang benar-benar membutuhkannya |
| **Memuat `panels.js` belakangan (lazy)** | ⛔ Dihentikan | Setelah diukur, bagian ini terlalu saling terkait dengan bagian lain untuk dipisah dengan aman. Menunggu keputusan pemilik proyek |
| **Memecah file CSS** | ⛔ Dihentikan | Hanya menghemat ~18 KB (1,8%) tapi berisiko merusak tampilan 20 tema. Rasio untung-rugi paling buruk |
| **Memecah file JavaScript besar** (`ui.js`, `sessions.js`, `messages.js`) | ⛔ Belum dikerjakan | Ini pekerjaan besar & berisiko tinggi (1–2 minggu). Hanya dikerjakan kalau kecepatan setelah Fase 4 masih dianggap kurang. Menunggu keputusan pemilik proyek |

### Urutan pekerjaan berikutnya (dari yang paling penting)

Kalau ingin melanjutkan proyek ini, kerjakan sesuai urutan ini:

1. **(WAJIB, hanya Anda yang bisa) Pasang di server ber-HTTPS lalu tes notifikasi
   dari HP asli.** Semua kodenya sudah siap, tapi belum pernah dites ke HP betulan
   karena butuh server dengan HTTPS. Panduannya ada di
   [`docs/reverse-proxy.md`](docs/reverse-proxy.md). Ini paling penting karena
   membuka fitur yang sudah dibangun tapi belum bisa "menyala": Web Push dan
   pemasangan aplikasi (PWA) di iPhone.

2. **Ambil keputusan soal dua pekerjaan Fase 4 yang dihentikan** (`panels.js`
   lazy dan pemecahan CSS). Datanya sudah lengkap di [§0.10](#010-p1-terlaksana-sebagian-2026-08-31);
   tinggal diputuskan: dikerjakan, dikerjakan sebagian, atau dilepas.

3. **Lengkapi terjemahan Bahasa Indonesia** (P3.1). Kerjakan bertahap: menu
   Pengaturan dulu → Onboarding → Cron → Ekstensi. Satu kelompok per sekali kerja.

4. **Filter tabel markdown di HP** (P3.2). Kerjakan kalau memang ada yang butuh.

5. **(Opsional, berisiko tinggi) Pecah file JavaScript inti** (P4.1). Hanya kalau
   kecepatan masih dirasa kurang setelah semua di atas selesai. Skor kecepatan
   (Lighthouse) saat ini **76**, target ≥ 85.

> **Catatan koreksi kecil:** di [Lampiran A](#lampiran-a--ringkasan-file-kunci)
> masih tertulis `manifest.json` "belum punya `share_target`". Itu sudah usang —
> fitur berbagi (`share_target`) **sudah ada** di `manifest.json` sejak P4.2
> selesai.

### Cara menjalankan proyek ini di komputer sendiri (langkah demi langkah)

Berikut cara paling gampang untuk mencoba aplikasi ini di laptop/PC Anda untuk
keperluan pengembangan (development). Ikuti berurutan.

**Syarat awal:**

- Sistem operasi **Linux, macOS, atau Windows lewat WSL2** (Windows asli belum
  didukung oleh `bootstrap.py`).
- **Python versi 3.11 sampai 3.13** sudah terpasang. Cek dengan: `python3 --version`
- **Git** sudah terpasang.
- **Hermes Agent** idealnya sudah terpasang di komputer yang sama. Kalau belum,
  `bootstrap.py` akan menawarkan memasangnya otomatis. (Tanpa agent, aplikasi
  tetap bisa dibuka dan tampilannya jalan, tapi tidak bisa benar-benar mengobrol
  dengan AI.)

**Langkah 1 — Ambil kodenya (clone):**

```bash
git clone https://github.com/nesquena/hermes-webui.git hermes-webui
cd hermes-webui
```

**Langkah 2 — Jalankan servernya:**

```bash
python3 bootstrap.py
```

Perintah ini otomatis melakukan banyak hal untuk Anda: mendeteksi Hermes Agent
(dan menawarkan memasangnya kalau belum ada), menyiapkan environment Python
beserta dependensinya, lalu menyalakan server web. Server berjalan di
**foreground** — artinya jendela terminal ini akan "tertahan" menampilkan log.
Untuk **menghentikannya, tekan `Ctrl-C`**.

> Alternatif: `./start.sh` — sama saja, tapi launcher ini juga otomatis mencetak
> perintah "SSH tunnel" bila Anda mengaksesnya lewat SSH.

**Langkah 3 — Buka di browser:**

Buka `http://127.0.0.1:8787` di browser Anda. Kalau ini pertama kali,
akan muncul **wizard onboarding** yang memandu Anda menyiapkan provider AI.

**Langkah 4 (opsional) — Ganti port atau izinkan akses dari HP di jaringan lokal:**

```bash
# Ganti port jadi 9000:
HERMES_WEBUI_PORT=9000 python3 bootstrap.py

# Izinkan diakses dari perangkat lain di jaringan (mis. HP) — WAJIB pasang password:
HERMES_WEBUI_HOST=0.0.0.0 HERMES_WEBUI_PASSWORD=rahasia-panjang python3 bootstrap.py
```

> ⚠️ Jangan pakai `HERMES_WEBUI_HOST=0.0.0.0` tanpa `HERMES_WEBUI_PASSWORD` —
> itu membuka aplikasi ke jaringan tanpa penjagaan.

**Menjalankan sebagai layanan latar (untuk VPS/server), bukan foreground:**

```bash
./ctl.sh start              # jalan di belakang layar, PID disimpan di ~/.hermes/webui.pid
./ctl.sh status             # lihat status: PID, uptime, port, lokasi log, /health
./ctl.sh logs --lines 100   # lihat 100 baris log terakhir
./ctl.sh restart            # restart
./ctl.sh stop               # hentikan
```

> ⚠️ `./ctl.sh stop` hanya bisa menghentikan proses yang **ia sendiri** jalankan
> (lewat `ctl.sh start`). Kalau Anda menyalakan lewat `bootstrap.py`/`start.sh`,
> hentikan dengan `Ctrl-C`, atau cari prosesnya: `lsof -i :8787` lalu `kill <PID>`.

**Menjalankan test (untuk memastikan tidak ada yang rusak):**

```bash
./scripts/test.sh                                 # jalankan seluruh test
./scripts/test.sh tests/test_mobile_layout.py -v  # jalankan satu file test saja
```

> Selalu pakai `./scripts/test.sh`, jangan `pytest` langsung. Script ini otomatis
> membuat/memakai environment `.venv`, mengunci Python ke versi 3.11–3.13, dan
> memasang dependensi test yang kurang. Menjalankan `pytest` langsung bisa gagal
> karena versi Python yang tidak cocok.

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
| **Layout tablet portrait (641–900px)** | ✅ **DIPERBAIKI** (Fase 1.2) | Panel kini terbuka sebagai slide-over di 768px & 820px — lihat [§0.2](#02-angka-sebelum--sesudah-terukur) |
| Berfungsi tanpa internet publik (VPS air-gapped) | ✅ **DIPERBAIKI** (Fase 1.3) | Prism + xterm di-vendor; 0 request eksternal saat halaman dimuat. *Sisa:* PDF.js & Mermaid masih lazy-load dari CDN |
| Notifikasi saat browser ditutup | ✅ **DIPERBAIKI** (Fase 3 + P0.2) | Web Push penuh (RFC 8291/8292) tanpa dependensi baru — lihat [§0.7](#07-fase-3--web-push-selesai). Pemicu kini lengkap: approval, turn selesai, **cron selesai**, dan **crash** ([§0.9](#09-p0-terlaksana-2026-08-31)) |
| Zoom / aksesibilitas mobile | ✅ **DIPERBAIKI** (Fase 2.4) | Zoom aktif di tab browser; tetap terkunci hanya di PWA terinstal |
| Panduan reverse proxy + TLS | ✅ **DIPERBAIKI (P0.1)** | [`docs/reverse-proxy.md`](docs/reverse-proxy.md) — nginx + Caddy + TLS, diagnosis SSE, subpath mount, alur Web Push. Tertaut dari `README.md` dan `docs/remote-access.md`. Lihat [§0.9](#09-p0-terlaksana-2026-08-31) |
| Bahasa Indonesia di UI | ⚠️ **Ada, tapi 9,5%** | Locale `id` terkirim dan bisa dipilih; terukur **163 key dari 1.713** milik `en`. Inti (layar pertama, composer, navigasi, sesi, login, sheet mobile) Indonesia; sisanya fallback ke Inggris — lihat [§0.4](#04-locale-bahasa-indonesia--selesai-kontrak-dilonggarkan) dan [§0.8](#08-re-audit-2026-08-31--pengukuran-ulang-di-f1a60e46) |
| Berat halaman | ⚠️ **Berat** | Terukur ulang di `f1a60e46`: **5.867 KiB mentah / 1.497,5 KiB gzip** cold. `i18n.js` sendiri **485,3 KiB gzip** untuk 16 bahasa yang pengguna baca satu. Belum ada gerbang byte di CI |

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

> **Catatan:** tabel di bawah adalah kondisi **sebelum** Fase 1–2. Kondisi
> sesudahnya ada di [§0.2](#02-angka-sebelum--sesudah-terukur). Ia dipertahankan
> apa adanya karena inilah bukti yang memotivasi perbaikannya.

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

### 6.1 ✅ DIPERBAIKI (Fase 1.2) — BUG: Panel workspace tidak bisa dibuka di tablet portrait (641–900px)

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

### 6.2 ✅ DIPERBAIKI SEBAGIAN (Fase 1.3) — Ketergantungan CDN eksternal (jsdelivr)

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

### 6.4 ✅ DIPERBAIKI (Fase 3) — Tidak ada Web Push — notifikasi mati saat browser ditutup

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

### 6.5 ✅ DIPERBAIKI (Fase 2.4) — Zoom dimatikan (aksesibilitas)

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

### 6.6 ✅ DIPERBAIKI (Fase 2.4) — `viewport-fit=cover` absen, padahal CSS memakai `env(safe-area-inset-*)`

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

### 6.7 ✅ DIPERBAIKI SEBAGIAN (Fase 2.1) — Fitur yang hilang di layar kecil

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

### 6.8 ✅ DIPERBAIKI (Fase 1.5) — Tidak ada test browser untuk viewport mobile

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

### 6.9 🔴 NAIK JADI PEMBLOKIR (re-audit) — Tidak ada panduan reverse proxy / TLS

> **Amandemen re-audit 2026-08-31.** Temuan ini ditulis 🟡 karena saat itu bisa
> disiasati SSH tunnel atau Tailscale. **Setelah Fase 3 mendarat, ia menjadi 🔴.**
> Web Push mensyaratkan secure context, jadi tanpa HTTPS seluruh `api/push.py`
> tidak pernah menyala — dan di iOS, "Add to Home Screen" (yang juga butuh HTTPS)
> adalah satu-satunya jalur push yang ada. Temuan ini kini memblokir fitur yang
> sudah selesai dibangun, dan menjadi item nomor satu di seluruh backlog:
> [P0.1](#p01---tulis-docsreverse-proxymd-nginx--caddy--tls--sse).
> Terukur ulang: `docs/remote-access.md` masih 75 baris tanpa satu pun kata TLS,
> dan `grep -rl proxy_buffering .` masih hanya mengembalikan dokumen ini.


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

### 6.10 ✅ DIPERBAIKI (Fase 1.4) — Overflow horizontal 14px di desktop/laptop

Terukur di 1024px dan 1440px (bukan di mobile): `document.scrollWidth` melebihi
`clientWidth` sebesar 14px. Penyebabnya `DIV.panel-actions` di dalam
`.rightpanel` — anak-anaknya (`#btnClearPreview`, `#btnWorkspacePrefs`) meluber
~190px melewati kontainer; `.rightpanel` punya `overflow:hidden` sehingga hanya
14px yang bocor ke dokumen. Dampaknya kecil, tapi ini gejala dari
`.panel-actions` yang tidak punya `flex-wrap`/`min-width:0`.

### 6.11 ✅ TERVERIFIKASI BUKAN MASALAH — Model konkurensi `ThreadingHTTPServer` + SSE

`ThreadingHTTPServer` membuat **satu thread OS per koneksi**, dan koneksi SSE
bersifat long-lived. Tidak ada cap thread eksplisit di codebase.

**Penilaian jujur:** untuk **VPS pribadi 1 pengguna** — yang persis kasus Anda —
ini **sama sekali bukan masalah**. Beberapa tab × beberapa SSE stream = puluhan
thread; Linux menanganinya dengan santai. Ini baru jadi kendala pada skenario
multi-user puluhan orang, dan itu di luar tujuan proyek ini. Saya mencatatnya
demi kelengkapan, bukan sebagai item kerja.

### 6.12 ✅ DIPERBAIKI (Fase 2.6) — Bahasa Indonesia belum tersedia

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

> **Dipindahkan ke [`docs/reverse-proxy.md`](docs/reverse-proxy.md) (P0.1, selesai).**
> Konfigurasi lengkap nginx dan Caddy tidak lagi tinggal di roadmap ini — ia
> sekarang menjadi dokumentasi operator yang sesungguhnya, tertaut dari
> `README.md` dan `docs/remote-access.md`. Menyalinnya di dua tempat berarti
> salah satunya akan basi.

Yang ada di sana, dan tidak ada di sini sebelumnya:

- Blok nginx dan Caddy lengkap, termasuk `proxy_buffering off` dan alasannya
- Mengapa `proxy_set_header Host $host` **wajib** — gerbang CSRF membandingkan
  `Origin` dengan `Host`, jadi meneruskan `127.0.0.1:8787` membuat setiap POST
  gagal sementara GET tetap jalan (mode kegagalan yang membingungkan, dan tidak
  pernah terdokumentasi sebelumnya)
- Hal yang sama berlaku untuk passkey: `api/passkeys.py` menurunkan WebAuthn RP
  ID dari header `Host`
- Ketiga variabel `TRUST_FORWARDED_*`, apa yang diperbaiki masing-masing, dan
  kenapa semuanya opt-in
- Subpath mount `/hermes/` — dengan garis bawah bahwa proxy **harus** memotong
  prefiks, karena server tidak punya konsep base path
- Bagian diagnosis **"SSE appears to hang"**: gejala, penyebab, perbaikan, dan
  satu perintah `curl -N` untuk membuktikan buffering sudah mati
- Alur mengaktifkan Web Push sampai tuntas, termasuk syarat Home Screen di iOS
  dan peringatan mem-backup `.vapid_key`

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

### FASE 1 ✅ SELESAI — Perbaiki yang rusak: tablet, CDN, overflow

> **Tujuan:** semua lebar layout berfungsi; app jalan penuh tanpa internet keluar.
>
> **Estimasi: 3–5 hari** · **Prasyarat: Fase 0**
>
> ✅ **Selesai seluruhnya.** Commit `e387df0`, `f140951`. Hasil terukur di
> [§0.2](#02-angka-sebelum--sesudah-terukur). Dua penyimpangan dari rencana:
> perbaikan tablet memerlukan pemisahan boundary `position:relative` untuk kedua
> rel (§0.3 nomor 1), dan CSP dipersempit ke path spesifik alih-alih menghapus
> jsdelivr sepenuhnya karena PDF.js + Mermaid ternyata juga dari CDN (§0.3
> nomor 2).

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

### FASE 2 ✅ SELESAI (1 item tertunda) — Paritas fitur & polesan mobile

> **Tujuan:** setiap fitur dan setting terjangkau dari HP; interaksi terasa native.
>
> **Estimasi: 1–2 minggu** · **Prasyarat: Fase 1**
>
> ✅ **Selesai, kecuali 2.6 (locale Indonesia) yang terhalang** — lihat
> [§0.4](#04-locale-bahasa-indonesia--selesai-kontrak-dilonggarkan). Commit `6512511`, `20f3f3d`,
> `b136ea9`. Catatan: swipe tepi-kiri untuk membuka sidebar **sudah ada** di
> upstream (#4660), jadi 2.5 hanya menambahkan pasangannya (swipe-tutup panel).

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

### FASE 3 ✅ SELESAI — Web Push: notifikasi saat browser ditutup

> **Tujuan:** kirim tugas panjang ke agent, kunci HP, dapat notifikasi saat selesai.
>
> **Estimasi: 1 minggu** · **Prasyarat: Fase 0 (HTTPS wajib)**
>
> **Ini adalah fase yang paling terasa "seperti aplikasi Claude".**
>
> ✅ **Selesai.** Diimplementasikan **tanpa dependensi baru** — RFC 8291 dan 8292
> ditulis langsung di atas `cryptography` yang sudah wajib. Lihat
> [§0.7](#07-fase-3--web-push-selesai) untuk catatan pelaksanaannya, termasuk
> satu bug yang ditangkap vektor uji resmi dan apa yang **tidak** bisa saya
> verifikasi di sandbox ini.

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

> **⚠️ Amandemen re-audit 2026-08-31 — target `< 450 KB` di tabel ini tidak
> terjangkau oleh rencana Fase 4 itu sendiri.** Dihitung ulang dengan angka gzip
> terukur, keempat item 4.1–4.4 mendarat di **~825 KiB**, bukan di bawah 450.
> Penyebabnya: hemat 4.4 (CSS skin) ternyata hanya ~18 KiB, bukan sebanding
> dengan yang lain, dan `ui.js` + `sessions.js` + `messages.js` (498,3 KiB gzip
> gabungan) tidak pernah masuk rencana. Lihat
> [§0.8 Temuan 2](#08-re-audit-2026-08-31--pengukuran-ulang-di-f1a60e46).
> Target yang direvisi ada di [§12 P1](#-p1--sebagian-selesai-2026-08-31--cold-start-bikin-gerbangnya-dulu-baru-potong);
> `< 450 KiB` dipindahkan ke [P4.1](#p41--pecah-modul-aplikasi-inti-uijs--sessionsjs--messagesjs---gerbang-terbuka-belum-dikerjakan)
> sebagai pekerjaan terpisah yang berisiko jauh lebih tinggi.

| Metrik | Sekarang (terukur `f1a60e46`) | Target P1 (revisi) | Target P4.1 |
|---|---|---|---|
| Transfer cold (HTML+JS+CSS+vendor eager) | **1.497,5 KiB gzip** | **≤ 850 KiB** | < 450 KiB |
| First Contentful Paint | [belum terverifikasi] | < 1,8 s | < 1,8 s |
| Time to Interactive | [belum terverifikasi] | < 2,5 s | < 2,5 s |
| Repeat visit (SW hit) | [belum terverifikasi] | < 0,8 s | < 0,8 s |
| Lighthouse Mobile Performance | **76** (diukur 2026-08-31, [§0.12](#012-p4-terlaksana--dan-gerbang-p41-akhirnya-diukur-2026-08-31)) | ≥ 85 | ≥ 85 |

*(FCP/TTI/Lighthouse tetap **[belum terverifikasi]** — butuh run pada deployment
HTTPS nyata, yaitu setelah [P0.1](#p01---tulis-docsreverse-proxymd-nginx--caddy--tls--sse).
Angka transfer terukur pasti dan direproduksi lewat Lampiran B.)*

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

## 12. Backlog Terurut Prioritas

> **Menggantikan checklist per-sprint yang lama.** Sprint 1–3 sudah selesai;
> mempertahankan penomoran sprint hanya menyembunyikan apa yang harus dikerjakan
> **berikutnya**. Daftar di bawah adalah seluruh sisa kerja, diurutkan sekali
> secara global.
>
> **Cara urutannya dibuat.** Setiap item dinilai pada empat sumbu, dengan
> tiebreak berurutan:
>
> 1. **Memblokir?** — apakah ia membuat pekerjaan yang **sudah selesai** tidak
>    bisa dipakai. Ini mengalahkan segalanya: pekerjaan yang menganggur adalah
>    biaya yang sudah dibayar tanpa imbalan.
> 2. **Bukti terukur** — apakah masalahnya punya angka (§0.8), bukan firasat.
> 3. **Rasio dampak/usaha** — dampak per hari kerja.
> 4. **Ketahanan** — apakah ia mencegah kemunduran di masa depan, atau hanya
>    memperbaiki keadaan hari ini.
>
> Sumbu 1 dan 4 adalah alasan urutan ini **berbeda** dari §8: dokumentasi HTTPS
> naik dari Fase 0 ke puncak, dan anggaran performa naik dari akhir Fase 4 ke
> awalnya.

---

### ✅ P0 — SELESAI (2026-08-31) — Memblokir fitur yang sudah selesai dibangun

**Kenapa ini P0 dan bukan yang lain:** ini satu-satunya item di seluruh backlog
yang mengaktifkan kode yang sudah ada, tanpa menulis kode aplikasi sama sekali.

> **Status: kedua item selesai.** Ringkasan pelaksanaan ada di
> [§0.9](#09-p0-terlaksana-2026-08-31), termasuk tiga klaim yang **gagal
> verifikasi** saat dokumen ditulis dan harus dikoreksi, serta keputusan desain
> di pemicu crash yang tidak terlihat dari rencana.

#### P0.1 ✅ — Tulis `docs/reverse-proxy.md` (nginx + Caddy + TLS + SSE)

| | |
|---|---|
| **Usaha** | 0,5–1 hari · **hanya dokumentasi** |
| **Memblokir** | Web Push (§0.7) · PWA install di iOS · Fase 5 seluruhnya |
| **Bukti** | `grep -rl proxy_buffering .` → hanya dokumen ini; `docs/remote-access.md` 75 baris tanpa TLS; `README.md:443,447` menyerahkan ini ke operator |
| **Prasyarat** | — |

Web Push mensyaratkan secure context. Tanpa HTTPS, seluruh `api/push.py` — RFC
8291 + RFC 8292 dari nol, terverifikasi terhadap vektor uji resmi — tidak pernah
menyala. Di iOS, "Add to Home Screen" adalah satu-satunya jalur push, dan itu
juga butuh HTTPS.

Isi minimum:

- [x] Blok nginx lengkap: TLS + `proxy_buffering off` + `proxy_read_timeout` +
      `X-Forwarded-Proto` (materi §0.5 **dipindahkan**, bukan disalin — §0.5
      sekarang hanya menunjuk ke sana)
- [x] Padanan Caddy (auto-TLS; ditaruh duluan karena jauh lebih pendek)
- [x] `HERMES_WEBUI_TRUST_FORWARDED_PROTO=1` dan kenapa cookie `Secure` bergantung padanya
- [x] Bagian **"SSE appears to hang"** — gejala, penyebab, perbaikan, plus satu
      perintah `curl -N` untuk membuktikannya
- [x] Catatan subpath mount (`/hermes/`) — nginx (`proxy_pass` dengan trailing
      slash) dan Caddy (`handle_path`)
- [x] Tautkan dari `README.md` (dua tempat) dan `docs/remote-access.md`
- [ ] **Verifikasi push dari HP sungguhan** — ini milik Anda, bukan saya; tidak
      ada perangkat atau egress ke FCM/APNs di sini. Langkahnya ada di dokumen.

**Tiga hal di luar rencana** yang masuk karena ditemukan saat membaca kode, dan
tidak satu pun terdokumentasi sebelumnya:

- **`proxy_set_header Host $host` sama kritisnya dengan `proxy_buffering off`.**
  Gerbang CSRF (`api/routes.py`) membandingkan `Origin` dengan `Host`; proxy
  yang meneruskan `127.0.0.1:8787` membuat **setiap POST gagal sementara GET
  tetap jalan** — halaman termuat, daftar sesi tampil, mengirim pesan error.
- **Passkey punya masalah yang sama.** `api/passkeys.py` menurunkan WebAuthn RP
  ID dari header `Host`, jadi `Host` yang salah mendaftarkan kredensial ke
  hostname yang salah.
- **Tailscale + HTTP polos bukan secure context.** Lalu lintasnya benar-benar
  terenkripsi WireGuard, tapi browser tidak peduli — push dan passkey tetap
  mati. `docs/remote-access.md` sekarang mengatakan ini dan menunjuk ke
  `tailscale cert`.

**Selesai bila:** operator baru bisa berangkat dari VPS kosong ke push yang
sampai di HP tanpa membaca dokumen ini.

#### P0.2 ✅ — Pemicu push yang tersisa: cron selesai + crash

| | |
|---|---|
| **Usaha** | 0,5 hari |
| **Bukti** | `grep -rn notify_async api/` → hanya `route_approvals.py:967` dan `streaming.py:12341` |
| **Prasyarat** | P0.1 untuk verifikasi ujung-ke-ujung |

Infrastrukturnya sudah ada; masing-masing satu panggilan `push.notify_async()`.
Dikelompokkan dengan P0.1 karena cron adalah **justru** kasus di mana browser
pasti tertutup — nilai push tertinggi ada di sini, dan sekarang tidak terpasang.

- [x] Pemicu cron-selesai — **dua jalur, bukan satu**: `api/routes.py` (jalur
      manual `/api/crons/run`) dan `api/profiles.py` (scheduler in-process).
      `api/background.py` yang disebut rencana ternyata soal background *task*,
      bukan cron.
- [x] Pemicu crash (`api/crash_visibility.py`) — **kedua** excepthook, thread
      dan main thread
- [x] Tag terpisah: `hermes-cron-<job_id>` dan `hermes-crash`, tidak pernah
      bertabrakan dengan `hermes-approval-*` atau `hermes-<session_id>`
- [x] Test: 12 test baru di `tests/test_web_push.py` (42 total, semuanya lulus)

**Keputusan desain yang tidak terlihat dari rencana:**

- **Crash di main thread butuh tunggu berbatas.** `notify_async` memakai daemon
  thread, dan daemon thread **tidak selamat** dari interpreter yang sedang
  teardown — push-nya dimulai lalu dibunuh di tengah jalan. `main_excepthook`
  karena itu menunggu maksimal 3 detik; `thread_excepthook` tidak menunggu sama
  sekali, karena di sana prosesnya masih hidup.
- **Crash harus dibatasi lajunya.** Exception di dalam loop panas akan mengubah
  satu bug jadi banjir notifikasi di lock screen. Satu push crash per 5 menit.
- **`requireInteraction` diperluas ke `crash` dan `cron_failed`.** Sebelumnya
  hanya `approval`. Ketiganya berarti pekerjaan berhenti dan tidak akan lanjut
  sendiri; notifikasi yang hilang sendiri saat HP tertelungkup bukan notifikasi.
  Cron yang **berhasil** tetap tidak menginterupsi.
- **Default-nya gagal, bukan berhasil.** Kedua jalur cron memulai dengan
  `success=False`, jadi exception sebelum verdict diketahui dilaporkan sebagai
  kegagalan — bukan diam-diam mengabarkan sukses.

---

### 🟠 P1 — SEBAGIAN SELESAI (2026-08-31) — Cold start: bikin gerbangnya dulu, baru potong

> **Hasil: 1.497,5 → 1.022,1 KiB gzip (−31,7%).** P1.0, P1.1, P1.3 selesai.
> **P1.2 dan P1.4 terhenti** setelah diukur — keduanya bukan pekerjaan yang
> dijelaskan rencana ini, dan keputusannya milik Anda. Lihat
> [§0.10](#010-p1-terlaksana-sebagian-2026-08-31).

**Kenapa P1 dan bukan P2:** ini satu-satunya angka yang masih buruk dan terukur
(1.497,5 KiB gzip cold — §0.8). Di 4G ini adalah selisih antara aplikasi yang
terasa hidup dan yang terasa berat.

**Kenapa urutan di dalamnya dibalik dari Fase 4:** §8 menaruh anggaran CI di
akhir. Itu salah arah. Repo baru saja menambah locale ke-16 dan 9 skin tanpa
satu pun test gagal; tanpa gerbang lebih dulu, setiap penghematan di bawah akan
tergerus diam-diam persis seperti itu.

#### P1.0 ✅ — 🎯 Anggaran payload frontend di CI — **kerjakan sebelum split apa pun**

| | |
|---|---|
| **Usaha** | 0,5 hari |
| **Hemat** | 0 KiB — **menjaga** semua penghematan di bawah |
| **Bukti** | 1.398 file test, nol yang menjaga byte frontend |

- [x] `tests/test_frontend_payload_budget.py` — **daftar aset diparse dari `index.html`**, bukan hardcoded, supaya `<script src>` baru langsung terhitung
- [x] Batas dipatok di ukuran saat itu + 2%, **sudah diturunkan dua kali** (P1.1, P1.3)
- [x] Pesan gagal menyebut file dan selisih byte — **dibuktikan gagal** pada dua simulasi (file membengkak, dan modul baru ditambahkan)
- [x] Batas per-file + batas per-bundel-bahasa + guard bahwa anggaran usang ikut dihapus saat file jadi lazy

#### P1.1 ✅ — 🎯 Pecah `i18n.js` per locale — **penghematan terbesar, risiko terkecil**

| | |
|---|---|
| **Usaha** | 1–2 hari |
| **Hemat** | **−424,6 KiB gzip (−28% cold path)** |
| **Bukti** | 485,3 KiB gzip = 32,4% jalur kritis untuk 16 bahasa; pengguna membaca satu |

Lebih besar daripada P1.2 + P1.3 + P1.4 digabung. Risikonya kecil karena locale
aktif sudah ada di `localStorage` sebelum paint pertama, dan `_serve_static`
sudah melayani aset ber-fingerprint dengan `max-age=31536000, immutable` +
ETag — infrastrukturnya tidak perlu dibangun.

- [x] `scripts/split_i18n.py` → `static/i18n/<kode>.js` (2,9–37,2 KiB gzip)
- [x] `static/i18n/core.js` = runtime + `en` + **manifest 16 bahasa**
- [x] Locale aktif dimuat **dalam urutan dokumen** lewat `document.write` di `index.html` — bukan `boot.js`, yang berjalan terlalu lambat untuk paint pertama
- [x] `sw.js` pre-cache **hanya `core`** — service worker tidak bisa membaca `localStorage`, jadi ia tidak bisa tahu bahasa mana
- [x] **`static/i18n.js` tetap sumber kebenaran** — 168 berkas test membacanya lewat path; berkas hasil generate dijaga `--check`
- [x] Turunkan batas P1.0 (1.565.000 → 1.140.000 byte)

#### P1.2 ⛔ TERHENTI — Lazy-load `panels.js`

> **Diukur, lalu dihentikan.** 101 dari 599 fungsi `panels.js` dipanggil dari
> luar, 74 terpasang di `onclick=` inline, dan `loadWorkspaceList()` dipanggil
> **tanpa syarat saat boot**. Asumsi "satu launcher" di bawah tidak berlaku, dan
> estimasi 1 hari berasal dari analisa saya yang tidak mengukur kopling ini.
> Tiga opsi beserta rekomendasi ada di
> [§0.10](#010-p1-terlaksana-sebagian-2026-08-31).

| | |
|---|---|
| **Usaha** | 1 hari |
| **Hemat** | **−154,1 KiB gzip** |

Control Center jarang dibuka pada kunjungan pertama. Injeksi `<script>` +
promise cache saat launcher pertama di-tap; tidak butuh bundler.

- [ ] Loader + promise cache (klik kedua tidak memuat ulang)
- [ ] Indikator memuat pada tap pertama
- [ ] Push subscribe UI hidup di `panels.js` — pastikan setting push tetap terjangkau
- [ ] Turunkan batas P1.0

#### P1.3 ✅ — Lazy-load xterm (`terminal.js` sengaja tetap eager)

| | |
|---|---|
| **Usaha** | 0,5 hari |
| **Hemat** | **−75,1 KiB gzip** (xterm 68,2 + `terminal.js` 6,9) |
| **Bukti** | `index.html:113-115` memuat xterm eager di `<head>` |

Naik di atas P1.4 (dari urutan §8 yang menaruh CSS lebih dulu) karena hematnya
**4× lebih besar** dan usahanya lebih kecil — xterm hanya perlu dipindahkan dari
`<head>` ke pembuka panel terminal.

- [x] `xterm.js`, kedua addon, dan `xterm.css` dimuat oleh `_loadXterm()` di `terminal.js`, dipicu satu-satunya call site `_startComposerTerminal()`
- [x] xterm **dikeluarkan dari pre-cache SW** — pre-cache membelanjakan ulang byte yang baru dihemat; terminal butuh PTY hidup, jadi offline tidak kehilangan apa pun
- [ ] ~~`terminal.js` ikut lazy~~ — **tidak dikerjakan dengan sengaja**: 6,9 KiB gzip dengan 9 entry point eksternal; xterm sendiri sudah 91% dari target item ini
- [x] `tests/test_vendored_frontend_assets.py` dipecah jadi kontrak **eager** vs **lazy** — keduanya tetap lokal dan ber-`?v=`, hanya waktunya berbeda
- [x] Turunkan batas P1.0 (1.140.000 → 1.067.000 byte)

#### P1.4 ⛔ TERHENTI — Pecah CSS core ↔ skin

> **Diukur, lalu dihentikan.** 452 aturan skin tersebar di 1,8%–66% berkas,
> dengan **1.631 aturan non-skin (240 KB) berselang di antaranya**. Memisahkannya
> menata ulang cascade di 20 tema, di repo tanpa test regresi visual — demi
> **18,4 KiB (1,8%)**, rasio risiko/imbalan terburuk di backlog. Lihat
> [§0.10](#010-p1-terlaksana-sebagian-2026-08-31).

| | |
|---|---|
| **Usaha** | 1 hari |
| **Hemat** | **−18,4 KiB gzip** — jauh lebih kecil dari dugaan §8 |
| **Bukti** | 97.429 / 525.290 byte `style.css` di dalam `[data-skin=…]` = 18,5% |

Turun ke posisi terakhir di P1. §8 menyiratkan ini sebanding dengan yang lain;
diukur, ia yang terkecil. Tetap dikerjakan — 20 skin akan terus bertambah dan
`style.css` render-blocking — tapi tidak sebelum tiga item di atas.

- [ ] `style.core.css` (render-blocking) ↔ `style.skins.css` (hanya bila `data-skin` ≠ default)
- [ ] Cegah FOUC saat skin non-default dipulihkan dari `localStorage`
- [ ] Turunkan batas P1.0

> **Target P1 (direvisi, jujur):** **≤ 850 KiB gzip cold** — dari 1.497,5.
> Target `< 450 KiB` di §4.6 **tidak terjangkau** oleh keempat item ini; lihat
> §0.8 Temuan 2. Ia dipindahkan ke P4.1.
>
> **Hasil nyata: 1.022,1 KiB.** Target ≤ 850 KiB mengandaikan P1.2 mendarat;
> tanpa P1.2 lantai rencana ini adalah ~1.004 KiB. Yang sudah dicapai adalah
> **−475,4 KiB (−31,7%)** — 68% dari total penghematan yang direncanakan, dari
> dua item yang risikonya paling kecil.

---

### ✅ P2 — Menyelesaikan yang sudah setengah jalan — **SELESAI**

Semua item di sini punya infrastruktur yang sudah berdiri. Rasio dampak/usaha
tinggi, tapi tidak ada yang memblokir dan tidak ada yang punya angka buruk.

> **Ketiganya selesai (2026-08-31).** Catatan pelaksanaan, angka terukur, dan
> empat temuan yang tidak ada di daftar ini:
> [§0.11](#011-p2-terlaksana-2026-08-31).

#### P2.1 — Perkuat service worker — ✅ selesai

| | |
|---|---|
| **Usaha** | 2–3 hari |
| **Bukti** | `sw.js` 292 baris; halaman offline = literal `'<h2>You are offline</h2>'` |

- [x] Shell offline sungguhan (sesi terakhir yang di-cache, read-only) alih-alih string itu — `static/offline.html`; aplikasi ter-cache didahulukan karena ia kini boot dengan data
- [x] Stale-while-revalidate untuk `GET /api/sessions` — **opt-in per request** (`X-Hermes-Cache: swr`), hanya boot dingin: SWR global akan mengedipkan sesi profil sebelumnya setelah ganti profil
- [x] Antrian kirim di IndexedDB, di-flush saat online — `static/outbox.js`, dipicu halaman (`online` + `visibilitychange` + load), tanpa Background Sync
- [x] Pre-cache vendor lokal yang tersisa setelah P1.3 — **plus tiga cacat pre-cache** yang tidak terdaftar: dua berkas cold-path hilang dari `SHELL_ASSETS`, dan tiga URL yang `?v=`-nya tidak cocok dengan yang diminta halaman

#### P2.2 — Audit a11y: VoiceOver (iOS) + TalkBack (Android) — ✅ selesai

| | |
|---|---|
| **Usaha** | 2–3 hari |
| **Bukti** | `index.html`: 206 `<button>`, 87 `aria-label` |
| **Hasil** | **40 → 0** kontrol ter-render tanpa nama yang bisa dibacakan; 148 `aria-label`, 58 terlokalkan |

**Dinaikkan dari Fase 5 ke P2.** §8 menaruhnya bersama haptics dan pull-to-refresh
sebagai "polesan native-feel". Itu salah kategori: aksesibilitas adalah
kebenaran, bukan poles, dan aplikasi ini dipenuhi tombol icon-only — pola yang
paling sering menghasilkan tombol tanpa nama yang bisa dibacakan.

- [x] Setiap tombol icon-only punya nama yang bisa dibacakan — penyebabnya `applyLocaleToDOM` menghapus `title` dari tombol yang hanya berlabel `data-tooltip`: **melokalkan halaman** yang menghapus nama terakhirnya
- [x] Urutan fokus pada drawer, sheet, dan slide-over; fokus terperangkap di dalam sheet terbuka — satu `HermesA11y.isolate()` untuk ketiganya: `aria-modal` + `aria-hidden` + `inert`, bukan hanya Tab trap (yang tidak berarti apa-apa saat pengguna menyapu, bukan menekan Tab)
- [x] Live region mengumumkan streaming tanpa membanjiri — teks identik tidak diulang, ada lantai antar ucapan, burst mengecil ke satu ucapan terbaru. Diukur: 5 `setBusy` → 2 ucapan
- [x] Kartu approval terbaca dan bisa ditindaklanjuti tanpa melihat layar — `approvalCmd` masuk `aria-describedby` (perintahnya sebelumnya tidak pernah diucapkan); diumumkan `assertive` saat fokus sengaja tidak dirampas dari composer
- [x] Test statis: setiap `<button>` tanpa teks wajib punya `aria-label` — `tests/test_button_accessible_names.py` (28 test), dan `data-tooltip` **tidak** dihitung

#### P2.3 — Vendor PDF.js + Mermaid → hapus jsdelivr dari CSP — ✅ selesai

| | |
|---|---|
| **Usaha** | 1 hari · +~4 MB di repo |
| **Bukti** | `api/helpers.py:103-104` — dua path jsdelivr tersisa |
| **Nyata** | +4,8 MB mentah (Mermaid 3,18 MB + PDF.js 1,64 MB) |

Keduanya lazy, jadi **tidak** memengaruhi cold start — nilainya adalah deployment
air-gapped sungguhan dan CSP tanpa origin eksternal sama sekali.

- [x] Vendor keduanya di bawah `static/vendor/` — SRI hash CDN dipertahankan (berkasnya byte-identik) dan sebuah test kini **menghitung ulang** ketiga hash terhadap disk, karena bahayanya bukan hash-nya ada tapi hash-nya basi
- [x] Hapus jsdelivr dari `script-src`, `worker-src`, `connect-src` — nol origin CDN di seluruh policy
- [x] `tests/test_vendored_frontend_assets.py` melarang jsdelivr sepenuhnya — menyasar bentuk URL, bukan nama host, agar penjelasan *mengapa* CDN-nya hilang tidak jadi hal pertama yang dihapus orang untuk melewati gerbangnya
- [x] Muat lazy (jangan pernah masuk jalur kritis) — dijaga test; **satu blocker tak terdaftar**: `.mjs` tidak ada di `_STATIC_MIME`, dan browser menolak ES module yang disajikan `text/plain` tanpa pesan apa pun

---

### 🟢 P3 — Kesenjangan paritas yang diketahui dan disengaja

Semuanya sudah didokumentasikan sebagai keputusan sadar. Dikerjakan saat ada
permintaan nyata, bukan karena ada di daftar.

#### P3.1 — Promosikan locale `id` dari 9,5% ke lengkap

| | |
|---|---|
| **Usaha** | **~1.550 key** — per keluarga key, berkali-kali |
| **Bukti** | `id` = 163 key vs `en` 1.713 (§0.8 Temuan 3) |

Urutan berdasarkan seberapa sering permukaannya disentuh: **settings → onboarding
→ cron → ekstensi**. Alur destruktif (mematikan autentikasi, hapus sesi) terakhir
dan wajib ditinjau penutur, bukan mesin — itu alasan asli `PARTIAL_LOCALES` ada.

- [ ] Satu keluarga key per PR
- [ ] Hapus entri `id` dari `PARTIAL_LOCALES` hanya setelah penutur meninjau seluruh bundle
- [ ] Setelah P1.1, ini juga **tidak lagi menambah byte** ke pengguna non-Indonesia

#### P3.2 — Filter tabel markdown di HP

| | |
|---|---|
| **Usaha** | 1–2 hari |
| **Status** | Kesenjangan yang disengaja, tercatat di `tests/test_mobile_feature_parity.py` |

Butuh surface sheet per tabel — ini perubahan desain, bukan perbaikan. Primitif
`HermesSheet` dari Fase 2.2 sudah ada, jadi biayanya kini lebih rendah dari saat
keputusan ini dibuat.

---

### ⚪ P4 — Rasa native & refactor besar

#### P4.1 — Pecah modul aplikasi inti (`ui.js` / `sessions.js` / `messages.js`) — ⛔ **gerbang terbuka, belum dikerjakan**

| | |
|---|---|
| **Usaha** | **1–2 minggu · risiko tinggi** |
| **Hemat** | hingga −498,3 KiB gzip — satu-satunya jalan ke target `< 450 KiB` |
| **Gerbang** | **Lighthouse mobile = 76, target ≥ 85 → terbuka** (diukur 2026-08-31) |

Dipisahkan dari P1 dengan sengaja: tiga file ini adalah jalur render pesan, dan
memecahnya adalah refactor modul, bukan pemisahan file. Kerjakan **hanya** jika
angka Lighthouse setelah P1 masih tidak dapat diterima — dan hanya dengan
anggaran P1.0 sudah menjaga hasilnya.

> **Prasyaratnya kini terukur, bukan lagi `[belum terverifikasi]`.** Keduanya
> terpenuhi: skornya 76 (< 85) dan anggaran P1.0 terpasang. Pekerjaannya tetap
> **tidak** dikerjakan — refactor setengah jadi di jalur render pesan lebih buruk
> daripada tidak memulainya. Data untuk memutuskannya, termasuk dua hal yang
> mengubah bentuk item ini (byte "tak dieksekusi" ≠ byte yang bisa dihapus; dan
> biaya terbesar yang tersisa mungkin `style.css` render-blocking, bukan JS), ada
> di [§0.12.3](#0123-p41--gerbangnya-terbuka-pekerjaannya-tidak-dikerjakan).

#### P4.2 — Native-feel, diurutkan menurut apa yang benar-benar terasa — ✅ **selesai**

Diurutkan ulang dari daftar datar §8:

> **Catatan pelaksanaan:**
> [§0.12.2](#0122-p42--dan-koreksi-terhadap-nol-dari-sembilan). **Tiga dari
> sembilan ternyata sudah ada** — footnote di bawah hanya meng-grep lima nama API
> lalu menggeneralisasi. Yang dikerjakan: lima yang benar-benar hilang, plus satu
> yang terpasang di elemen yang salah.

1. [x] **Share Target API** di manifest — **dibuat.** `sw.js` menangkap POST-nya (teks **dan berkas**, tanpa state server); `/share-target` di server adalah fallback teks-saja untuk saat tak ada worker yang mengontrol. Tidak pernah auto-send, tidak pernah menimpa draft
2. [x] **Web Share API** — **dibuat.** Link share dan ekspor Markdown lewat share sheet OS, dengan clipboard/download tetap sebagai fallback; `canShareFiles()` ditanya sebelum membangun `File`
3. [x] **Optimistic UI** — ✅ **sudah ada sebelum sesi ini.** `messages.js` mem-push bubble user dan me-render sebelum POST `/api/chat/start`
4. [x] **Skeleton screen** — ✅ **sudah ada sebelum sesi ini.** `showSessionListSkeleton` + `.skeleton-row`, dengan varian reduced-motion
5. [x] **App Badging API** — **dibuat.** Digerakkan dari `_approvalPendingBySession` (satu map, dijumlahkan lintas sesi); handler `push` memakai `setAppBadge()` tanpa argumen karena payload tidak membawa hitungan
6. [x] **Pull-to-refresh** pada daftar sesi — **dipindahkan ke elemen yang benar.** Sebelumnya terpasang di `#messages` dan PWA-only. Kini satu factory untuk dua scroller; daftar sesi tidak di-gate standalone, label terlokalkan, indikator `role="status"`
7. [x] **View Transitions API** — **dibuat.** Membungkus swap sinkron `switchPanel`; delapan `await loadX()` sengaja **di luar** callback-nya. Callback selalu jalan meski transisinya tidak
8. [x] **Haptic feedback** — **dibuat.** Kirim + jawab approval saja; di-gate pada `navigator.userActivation` supaya Chromium tidak mencatat "Blocked call to navigator.vibrate" ke konsol
9. [x] **Mode suara hands-free** — ✅ **sudah ada sebelum sesi ini.** Voice mode berbasis turn (#1333): listen → send → TTS → listen, dengan fallback TTS server

*~~Nol dari sembilan item ini ada di codebase hari ini — diverifikasi: tidak ada
`startViewTransition`, `navigator.vibrate`, `share_target`, `setAppBadge`, atau
`navigator.share` di `static/`.~~*
**Klaim itu salah.** Grep-nya memeriksa lima nama API lalu kesimpulannya
digeneralisasi ke sembilan item; **#3, #4, dan #9 sudah ada**, ketiganya lebih
lengkap dari deskripsi di daftar ini. `tests/test_native_platform_integrations.py`
memasang pin regresi untuk ketiganya supaya tidak ada yang membangunnya dua kali.

---

### Fase 0 — deployment (tetap berlaku, tidak berubah)

Ini bukan sisa pekerjaan pengembangan; ini yang Anda lakukan untuk memakai apa
yang sudah ada. Tanpa ubah kode, 1–2 hari.

- [ ] Provision VPS, ufw hanya 22/80/443, SSH key-only
- [ ] Install hermes-agent + hermes-webui
- [ ] `.env`: `HOST=127.0.0.1`, `PASSWORD=…`, `TRUST_FORWARDED_PROTO=1`, `SESSION_TTL=2592000`
- [ ] systemd unit + `systemctl enable --now`
- [ ] nginx/Caddy + certbot — **`proxy_buffering off` untuk SSE** *(P0.1 menjadikan langkah ini bisa diikuti)*
- [ ] Verifikasi checklist §0.6 dari HP sungguhan
- [ ] Add to Home Screen *(prasyarat push di iOS)*
- [ ] Backup harian `~/.hermes/` dan `~/workspace/`

---

### Ringkasan urutan

| # | Item | Usaha | Dampak |
|---|---|---|---|
| ~~**P0.1**~~ | ~~`docs/reverse-proxy.md`~~ | ✅ **selesai** | Mengaktifkan Web Push + PWA iOS yang sudah dibangun |
| ~~**P0.2**~~ | ~~Pemicu push cron + crash~~ | ✅ **selesai** | Menutup Fase 3 |
| ~~**P1.0**~~ | ~~Anggaran payload di CI~~ | ✅ **selesai** | Menjaga semua di bawahnya |
| ~~**P1.1**~~ | ~~Pecah `i18n.js`~~ | ✅ **selesai** | **−408,4 KiB** |
| **P1.2** | Lazy `panels.js` | ⛔ **terhenti** | −154,1 KiB — butuh keputusan Anda |
| ~~**P1.3**~~ | ~~Lazy xterm~~ | ✅ **selesai** | −67,0 KiB |
| **P1.4** | Pecah CSS core ↔ skin | ⛔ **terhenti** | −18,4 KiB — rasio terburuk di backlog |
| ~~**P2.1**~~ | ~~Perkuat service worker~~ | ✅ **selesai** | Offline sungguhan: daftar sesi + transkrip ter-cache, antrian kirim |
| ~~**P2.2**~~ | ~~Audit a11y~~ | ✅ **selesai** | 40 → 0 kontrol tanpa nama; 3 overlay jadi dialog modal |
| ~~**P2.3**~~ | ~~Vendor PDF.js + Mermaid~~ | ✅ **selesai** | Air-gapped penuh; CSP nol origin eksternal |
| **P3.1** | Promosikan locale `id` | ~1.550 key | Paritas bahasa |
| **P3.2** | Filter tabel di HP | 1–2 hr | Paritas fitur |
| **P4.1** | Pecah modul inti | ⛔ **gerbang terbuka** (76 < 85) | Jalan ke < 450 KiB — keputusan Anda, data di §0.12.3 |
| ~~**P4.2**~~ | ~~Native-feel ×9~~ | ✅ **selesai** | 5 dibuat, 1 dipindahkan, 3 ternyata sudah ada |

**P0 selesai** ([§0.9](#09-p0-terlaksana-2026-08-31)). Yang tersisa dari P0
adalah satu langkah yang hanya bisa Anda lakukan: deploy di belakang HTTPS lalu
tekan "Kirim push uji" dari HP.

**P1 selesai sebagian** ([§0.10](#010-p1-terlaksana-sebagian-2026-08-31)):
cold path **1.497,5 → 1.022,1 KiB (−31,7%)**, dijaga oleh anggaran di CI.

**Dua keputusan menunggu Anda** sebelum P1 bisa ditutup — keduanya sudah diukur,
bukan diperkirakan: apakah P1.2 dikerjakan lewat delegasi event (~2–3 hari),
dipecah sebagian, atau dilepas; dan apakah P1.4 layak dikerjakan sama sekali
mengingat imbalan 1,8%-nya menuntut test regresi visual lebih dulu.

**P2 selesai seluruhnya** ([§0.11](#011-p2-terlaksana-2026-08-31)): +11,6 KiB
gzip di cold path (955,1 KiB, anggaran 1.042,0), 59 test baru, dan CSP tanpa
origin eksternal sama sekali.

**Sisa backlog kini P3 dan P4** — semuanya kesenjangan yang disengaja atau
refactor besar, tidak ada yang memblokir. Dua keputusan P1 di atas masih
menunggu Anda; keduanya tidak memblokir P3/P4.

---

## Lampiran A — Ringkasan File Kunci

> Ukuran di-refresh pada re-audit `f1a60e46` (2026-08-31). Satuan KiB = 1024 byte;
> kolom gzip memakai level 6, sama seperti yang dikirim `_serve_static`.

| File | Mentah | Gzip | Peran |
|---|---:|---:|---|
| `server.py` | 29,1 KB | — | Entry point, `ThreadingHTTPServer`, TLS, isolasi jaringan mode test |
| `bootstrap.py` | 28,1 KB | — | Discovery agent, ensure dependency, launcher |
| `ctl.sh` | 30,5 KB | — | Lifecycle daemon (start/stop/status/logs/restart) |
| `api/routes.py` | 1,21 MB | — | Static serving (gzip -6 + ETag + `immutable`); SSE dispatch |
| `api/streaming.py` | 637 KB | — | Eksekusi agent, streaming SSE, `Last-Event-ID`, **pemicu push turn-selesai** |
| `api/auth.py` | 46 KB | — | PBKDF2, sesi, rate limit, trusted-header, cookie |
| `api/helpers.py` | 53 KB | — | Template CSP — **nol origin CDN** setelah [P2.3](#p23--vendor-pdfjs--mermaid--hapus-jsdelivr-dari-csp---selesai); gzip, util respons |
| `api/config.py` | 481 KB | — | Konfigurasi, discovery model/provider |
| `api/push.py` | **19,6 KB** | — | **Fase 3** — VAPID (RFC 8292) + aes128gcm (RFC 8291) di atas `cryptography` |
| `api/route_approvals.py` | — | — | **Pemicu push paling bernilai** — approval menunggu (`:967`) |
| `static/index.html` | 221,0 KB | **42,0** | Template shell tunggal; 5 `<script src>` + 4 `<link>`, semuanya lokal |
| `static/i18n.js` | 1.746,8 KB | **485,3** | **16 locale** — 32,4% jalur kritis; target [P1.1](#p11----pecah-i18njs-per-locale--penghematan-terbesar-risiko-terkecil) |
| `static/ui.js` | 1.020,7 KB | 273,7 | Helper DOM, render markdown, kartu tool, context ring; lazy-import PDF.js + Mermaid |
| `static/panels.js` | 634,5 KB | 154,1 | Control Center + UI langganan push; target [P1.2](#p12--terhenti--lazy-load-panelsjs) |
| `static/style.css` | 515,5 KB | 99,0 | Layout, 74 `@media` (6,8% byte), 6 `@container`, **20 skin** (18,5% byte) |
| `static/sessions.js` | 436,8 KB | 113,2 | Daftar/CRUD sesi; kandidat [P4.1](#p41--pecah-modul-aplikasi-inti-uijs--sessionsjs--messagesjs---gerbang-terbuka-belum-dikerjakan) |
| `static/messages.js` | 435,6 KB | 111,4 | Render transkrip; kandidat [P4.1](#p41--pecah-modul-aplikasi-inti-uijs--sessionsjs--messagesjs---gerbang-terbuka-belum-dikerjakan) |
| `static/boot.js` | 185,5 KB | 56,0 | **Navigasi mobile**, `BP.PHONE`/`BP.TABLET`, keyboard inset, tema/skin, bfcache, `HermesSheet`, **`HermesA11y`** (isolasi modal + live region) |
| `static/terminal.js` | 27,0 KB | 6,9 | Terminal embedded; target [P1.3](#p13---lazy-load-xterm-terminaljs-sengaja-tetap-eager) |
| `static/sw.js` | **21,6 KB** | — | Service worker: pre-cache shell (29 entri), **cache data read-only** (`hermes-data-v1`, 2 endpoint), SWR opt-in, fallback offline berlapis, `push`, `pushsubscriptionchange`, `notificationclick` |
| `static/outbox.js` | **12,0 KB** | **4,2** | **Baru (P2.1)** — antrian kirim IndexedDB; flush dipicu halaman karena Safari tidak punya Background Sync |
| `static/offline.html` | **15,2 KB** | 5,0 | **Baru (P2.1)** — shell offline read-only; membaca `hermes-data-v1` + antrian, nol request eksternal, nol dependensi bundel aplikasi |
| `static/vendor/mermaid/10.9.3/` | 3,18 MB | 971 | **Baru (P2.3)** — lazy, tidak di-pre-cache |
| `static/vendor/pdfjs/4.9.155/` | 1,64 MB | 487 | **Baru (P2.3)** — lazy; `.mjs` butuh entri `_STATIC_MIME` atau browser menolaknya tanpa pesan |
| `static/manifest.json` | 1,2 KB | — | Manifest PWA — kini **sudah punya `share_target`** (dibuat di [P4.2](#p42--native-feel-diurutkan-menurut-apa-yang-benar-benar-terasa---selesai)) |
| `tests/test_mobile_layout.py` | — | Regresi mobile statis (breakpoint, markup, overflow) |
| `tests/browser_responsive.py` | — | **Baru (Fase 1.5)** — gerbang layout di browser sungguhan, 9 viewport |
| `tests/test_breakpoint_contract.py` | — | **Baru (Fase 1.1)** — menyandingkan breakpoint CSS ↔ JS |
| `tests/test_vendored_frontend_assets.py` | — | **Fase 1.3**, diperluas [P2.3](#p23--vendor-pdfjs--mermaid--hapus-jsdelivr-dari-csp---selesai) — larangan CDN **total** + verifikasi ulang setiap SRI hash terhadap disk |
| `tests/test_offline_shell_and_outbox.py` | — | **Baru (P2.1)** — 31 test: kesepakatan `index.html` ↔ `SHELL_ASSETS`, batas cache API, SWR opt-in, shell offline, antrian kirim |
| `tests/test_button_accessible_names.py` | — | **Baru (P2.2)** — 28 test: setiap `<button>` tanpa teks wajib punya nama yang bisa dibacakan (`data-tooltip` **tidak** dihitung), semantik modal, lantai live region, kartu approval |
| `tests/test_mobile_feature_parity.py` | — | **Baru (Fase 2.1/2.2)** — kontrak keterjangkauan fitur di HP |
| `static/vendor/prismjs/1.29.0/` | 1,33 MB | Prism core + autoloader (5,6 KiB gz eager), 298 grammar (lazy), 2 tema |
| `static/vendor/xterm/5.3.0/` | 300 KB | **68,2 KiB gzip dimuat eager di setiap page load** — target [P1.3](#p13---lazy-load-xterm-terminaljs-sengaja-tetap-eager) |
| `static/vendor/katex/0.16.22/` | 1,43 MB | CSS-nya (3,5 KiB gz) eager; font & JS lazy |
| `.github/workflows/browser-smoke.yml` | — | Menjalankan `browser_smoke.py` **dan** gerbang responsif 9 viewport pada tiap PR non-docs |
| `tests/locale_contract.py` | — | Sumber kebenaran `PARTIAL_LOCALES` — satu entri: `id` |
| `docs/UIUX-GUIDE.md` | — | Kebijakan desain, termasuk aturan responsif |
| `docs/remote-access.md` | **75 baris** | SSH tunnel, Tailscale, ARM64. **Nol TLS / nginx / Caddy** — celah [P0.1](#p01---tulis-docsreverse-proxymd-nginx--caddy--tls--sse) |
| `docs/reverse-proxy.md` | **belum ada** | [P0.1](#p01---tulis-docsreverse-proxymd-nginx--caddy--tls--sse) — prasyarat HTTPS untuk Web Push |

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

# 5. Jalankan gerbang responsif yang ditambahkan di Fase 1.5.
#    Ia membooting server-nya sendiri di port acak dengan state dir sementara.
python tests/browser_responsive.py
#    Di lingkungan yang Chromium-nya tidak cocok dengan versi playwright:
HERMES_WEBUI_CHROMIUM=/path/ke/chromium python tests/browser_responsive.py

# 6. Buktikan tidak ada aset yang dimuat dari CDN saat halaman dibuka.
#    Blokir egress lalu muat halaman: requestfailed harus 0 (sebelum Fase 1.3
#    ada 7 kegagalan per halaman di setiap viewport).
python -m pytest tests/test_vendored_frontend_assets.py -q
```

### B.1 — Angka payload §0.8 (basis anggaran P1.0)

Ini yang menghasilkan tabel cold-load di §0.8. Daftar filenya sengaja ditulis
eksplisit, bukan diambil dari glob: yang diukur adalah **apa yang benar-benar
dirujuk `index.html`**, dan glob akan diam-diam menghitung file yatim.

```bash
python3 - <<'EOF'
import gzip, os
crit = ["static/i18n.js", "static/icons.js", "static/assistant_turn_anchors.js",
        "static/ui.js", "static/workspace.js", "static/terminal.js",
        "static/sessions.js", "static/commands.js", "static/messages.js",
        "static/extension_settings.js", "static/panels.js", "static/onboarding.js",
        "static/boot.js", "static/outline.js", "static/style.css",
        "static/pwa-startup.js"]
vend = ["static/vendor/prismjs/1.29.0/components/prism-core.min.js",
        "static/vendor/prismjs/1.29.0/plugins/autoloader/prism-autoloader.min.js",
        "static/vendor/xterm/5.3.0/xterm.js",
        "static/vendor/xterm/5.3.0/xterm-addon-fit.js",
        "static/vendor/xterm/5.3.0/xterm-addon-web-links.js",
        "static/vendor/xterm/5.3.0/xterm.css",
        "static/vendor/katex/0.16.22/katex.min.css",
        "static/vendor/prismjs/1.29.0/themes/prism-tomorrow.min.css"]
# compresslevel=6 matches _serve_static in api/routes.py — not the default 9.
gz  = lambda p: len(gzip.compress(open(p, "rb").read(), 6))
kib = lambda n: n / 1024
for name, group in (("app js+css", crit), ("vendor eager", vend),
                    ("index.html", ["static/index.html"])):
    print(f"{name:14} raw={kib(sum(map(os.path.getsize, group))):9.1f} KiB"
          f"  gz={kib(sum(map(gz, group))):9.1f} KiB")
allf = crit + vend + ["static/index.html"]
print(f"{'TOTAL COLD':14} raw={kib(sum(map(os.path.getsize, allf))):9.1f} KiB"
      f"  gz={kib(sum(map(gz, allf))):9.1f} KiB")
for f in sorted(allf, key=gz, reverse=True)[:8]:
    print(f"  {f:52} gz={kib(gz(f)):8.1f} KiB")
EOF
```

### B.2 — Cakupan `id` dan porsi CSS skin (§0.8 Temuan 2 & 3)

```bash
# Perkiraan jumlah key per locale — "id" harus muncul jauh di bawah yang lain.
python3 - <<'EOF'
import re
lines = open("static/i18n.js", encoding="utf-8").read().split("\n")
marks = [(i, re.match(r"^_lang:\s*'([^']+)'", l.strip()).group(1))
         for i, l in enumerate(lines) if l.strip().startswith("_lang:")]
marks.append((len(lines), None))
for (start, code), (end, _) in zip(marks, marks[1:]):
    block = "\n".join(lines[start:end])
    n = len(re.findall(r"^\s{2,4}[A-Za-z_][A-Za-z0-9_]*\s*:", block, re.M))
    print(f"{code:8} approx_keys={n}")
EOF

# Berapa banyak style.css yang hanya melayani skin non-default.
python3 - <<'EOF'
import re
css = open("static/style.css", encoding="utf-8").read()
def rules(text, off=0):
    i = start = 0; out = []
    while i < len(text):
        if text[i] == "{":
            d, j = 1, i + 1
            while j < len(text) and d:
                d += (text[j] == "{") - (text[j] == "}"); j += 1
            out.append((start + off, j + off, text[start:i])); i = start = j
        else:
            i += 1
    return out
skin = 0
for s, e, sel in rules(css):
    if "data-skin" in sel:
        skin += e - s
    elif sel.strip().startswith(("@media", "@supports")):
        b = css.index("{", s) + 1
        skin += sum(e2 - s2 for s2, e2, sel2 in rules(css[b:e - 1], b) if "data-skin" in sel2)
print(f"skin CSS: {skin} / {len(css)} byte = {skin / len(css) * 100:.1f}%")
EOF
```

### B.3 — Yang tidak bisa diukur ulang di re-audit ini

`tests/browser_responsive.py` dan `tests/browser_smoke.py` butuh Playwright +
Chromium. Keduanya **tidak tersedia** di environment re-audit 2026-08-31, jadi
seluruh klaim layout runtime di §0.2 dibawa maju **tanpa verifikasi ulang** di
`f1a60e46`. Gerbangnya tetap berjalan di CI pada setiap PR non-docs
(`.github/workflows/browser-smoke.yml`), yang berarti klaim itu masih ditegakkan
— tapi oleh CI, bukan oleh dokumen ini. Untuk memverifikasinya sendiri:

```bash
pip install playwright && python -m playwright install --with-deps chromium
python tests/browser_responsive.py
```
