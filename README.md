# Excelnt Suite

Factory akun **Excelnt** + panen **API key** otomatis. Signup → klaim promo
**OMG26** ($600 balance, plan **Power**) → ambil API key `sk_live_...`.

## Cara kerja

```
1. buat inbox temp-mail (tempik)
2. buka https://excelnt.ai/signup?ref=<ref>   (WAJIB pakai ref utk trial Power)
3. isi email → Continue
4. isi Full name + Password + Promo code (OMG26)
5. Create account  → promo diterapkan ($600 balance, plan Power)
6. POST /api/keys  (header x-excelnt-client: vscode) → secret sk_live_...
7. simpan ke accounts.txt
```

## Kenapa butuh header `x-excelnt-client: vscode`?

Server Excelnt membalas `403 desktop_only` untuk pembuatan key dari web
(*"Key creation is available in the VS Code extension."*). Extension resmi
memakai header **`x-excelnt-client: vscode`**; dengan header itu (dan session
cookie yang sudah login) endpoint `POST /api/keys` mengembalikan `secret`.

## Instalasi

```bash
python3 -m venv .venv
.venv/bin/pip install rich requests patchright
.venv/bin/patchright install chromium

cp config.example.toml config.toml   # isi endpoint tempmail Anda
```

## Command

```bash
./run.sh harvest 1            # buat 1 akun (klaim promo + panen key)
./run.sh harvest 5            # buat 5 akun
./run.sh harvest 1 --no-proxy # tanpa proxy
./run.sh test                 # uji semua API key ke gateway
./run.sh report               # ringkasan akun + balance
./run.sh probe                # cek gateway hidup
./run.sh sync                 # inject API key ke 9router
```

Batch dengan rotasi proxy:

```bash
.venv/bin/python batch.py 10 --proxy-file proxies.txt --delay 15
```

## Format akun (`accounts.txt`)

```
email:password:apikey:balance
```

## Gateway

OpenAI-compatible: `https://excelnt.ai/v1`

```bash
curl https://excelnt.ai/v1/chat/completions \
  -H "Authorization: Bearer sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-6-astra","messages":[{"role":"user","content":"hi"}]}'
```

Model contoh: `gpt-6-astra`, `claude-opus-5`, `gpt-5.6-luna`, dll (41 model).

## ⚠️ Catatan

- **Limit per-network**: setelah beberapa akun dari IP/jaringan yang sama,
  server membalas *"Too many accounts have already been registered from your
  network."* Gunakan rotasi proxy (residensial) atau tunggu.
- **Backend bisa overload**: gateway kadang membalas
  `server_overloaded` — coba lagi nanti (bukan masalah key).
- **Promo OMG26**: $600 balance / 5 jam + $4.200 / minggu, plan Power 1 bulan.
  Kode promo bisa berubah/expired kapan saja.
- Pakai proxy residensial (bukan datacenter) untuk hasil terbaik.

## Atribusi

Sumber kode temp-mail: **[hirotomasato/tempik](https://github.com/hirotomasato/tempik)**
(lihat `src/tempmail.py`).

## Struktur

```
main.py            # CLI
batch.py           # batch runner + rotasi proxy
src/excelnt.py     # engine: signup + promo + panen API key
src/tempmail.py    # client temp-mail (tempik)
src/inboxstore.py  # riwayat inbox
src/router9.py     # sync ke 9router
config.example.toml
```

## Disclaimer

Untuk penggunaan pribadi/edukasi. Hormati Terms of Service Excelnt. Promo dan
trial adalah kebijakan mereka dan dapat berubah.
