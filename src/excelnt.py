"""Excelnt engine - buat akun Excelnt + klaim promo + panen API key.

Alur (semua terbukti):
  1. buat inbox tempik
  2. buka https://excelnt.ai/signup?ref=... via patchright
  3. isi email -> Continue
  4. isi Full name + Password + Promo code (OMG26)
  5. Create account -> klaim promo ($600 balance, plan Power)
  6. POST /api/keys  (header x-excelnt-client: vscode) -> secret sk_live_...
  7. simpan ke accounts.txt

Sumber mail: https://github.com/hirotomasato/tempik
"""
import asyncio
import json
import random
import re
import string
from typing import Any, Dict, Optional

from rich.console import Console

from .tempmail import TempikClient
from .inboxstore import save as save_inbox

C = Console()

SIGNUP_URL = "https://excelnt.ai/signup?ref=schneizel-f969"
API_KEYS_URL = "https://excelnt.ai/api/keys"
DEFAULT_PROMO = "OMG26"
# header khusus agar server mengizinkan pembuatan key dari luar extension
VSCODE_HEADERS = {"Content-Type": "application/json", "x-excelnt-client": "vscode"}

GIVEN = ["Arya", "Bima", "Citra", "Dewi", "Eka", "Fajar", "Gita", "Hadi", "Indra",
         "Joko", "Kartika", "Lestari", "Maya", "Nanda", "Oscar", "Putri", "Rina",
         "Sari", "Tono", "Umar", "Vina", "Wahyu", "Yudi", "Zahra"]
FAMILY = ["Mustika", "Pratama", "Saputra", "Wijaya", "Nugroho", "Hidayat", "Kusuma",
          "Ramadhan", "Setiawan", "Permana", "Handoko", "Siregar", "Simbolon",
          "Halim", "Firdaus", "Maulana"]


def _rand_password(n: int = 14) -> str:
    core = "".join(random.choices(string.ascii_letters + string.digits, k=n))
    return f"Xy{core}!7"


async def harvest_excelnt(headless: bool = False, promo: str = DEFAULT_PROMO,
                          ref: str = "schneizel-f969", verbose: bool = True,
                          proxy: Optional[str] = None) -> Dict[str, Any]:
    """Buat 1 akun Excelnt + klaim promo + panen API key.

    Return dict {ok, email, password, apikey, plan, balance, error, ...}
    """
    from patchright.async_api import async_playwright

    out: Dict[str, Any] = {"site": "excelnt", "ok": False}
    tc = TempikClient()
    email = tc.create_inbox()
    save_inbox("excelnt", email, tc.session_id, "")
    pwd = _rand_password()
    gn, fn = random.choice(GIVEN), random.choice(FAMILY)
    name = f"{gn} {fn}"
    out.update(email=email, password=pwd, name=name, promo=promo)
    if verbose:
        C.print(f"[cyan]excelnt[/] inbox: {email} | promo {promo}")

    async with async_playwright() as pw:
        launch_kw = {"headless": headless}
        if proxy:
            launch_kw["proxy"] = _parse_proxy(proxy)
        browser = await pw.chromium.launch(**launch_kw)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        try:
            url = SIGNUP_URL if not ref else f"https://excelnt.ai/signup?ref={ref}"
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4000)

            # 1. email -> Continue
            await page.fill("input[type=email]", email, timeout=10000)
            await page.wait_for_timeout(500)
            await _click(page, r"continue with email")
            await page.wait_for_timeout(4000)

            # 2. klik "Have a promo code?" agar field promo muncul
            await _click(page, r"have a promo code")
            await page.wait_for_timeout(1500)

            # 3. isi name, password, promo
            await page.fill("input[name=name]", name, timeout=8000)
            await page.fill("input[name=password]", pwd, timeout=8000)
            try:
                await page.fill("input[name=promo]", promo, timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(800)

            # 4. Create account
            await _click(page, r"create account")
            await page.wait_for_timeout(9000)

            body = await page.evaluate("document.body.innerText")
            out["body_snapshot"] = body[:400]

            # deteksi sukses + promo
            if "account is ready" in body.lower() or "dashboard" in body.lower():
                out["ok"] = True
                m = re.search(r"\$([\d,]+\.\d{2})\s*added", body)
                if m:
                    out["balance"] = "$" + m.group(1)
                pm = re.search(r"PROMO CODE\s+(\S+)", body)
                if pm:
                    out["promo_applied"] = pm.group(1)
                if verbose:
                    C.print(f"[green]  akun jadi[/]" +
                            (f" | balance {out.get('balance')}" if out.get("balance") else ""))
            else:
                err = await _ui_error(page)
                out["error"] = "signup-failed"
                out["ui_error"] = err[:200]
                if verbose:
                    C.print(f"[yellow]  gagal signup: {err[:150]}[/]")
                return out

            # 5. panen API key via endpoint internal (header vscode)
            key = await _create_key_via_page(ctx, name="main")
            if key:
                out["apikey"] = key
                if verbose:
                    C.print(f"[green]  API key: {key[:18]}...{key[-6:]}[/]")
                _append_account(email, pwd, key, out.get("balance", ""))
            else:
                out["error"] = "no-apikey"
                if verbose:
                    C.print("[yellow]  gagal ambil API key[/]")
            return out
        except Exception as e:
            out["error"] = str(e)[:180]
            return out
        finally:
            try:
                await ctx.close()
                await browser.close()
            except Exception:
                pass


async def _create_key_via_page(ctx, name: str = "main") -> Optional[str]:
    """Buat API key lewat halaman (session cookie) + header x-excelnt-client.

    Hanya cara ini yang lolos 'desktop_only' dari server.
    """
    page = await ctx.new_page()
    try:
        await page.goto("https://excelnt.ai/dashboard", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        script = """async (args) => {
            const r = await fetch('https://excelnt.ai/api/keys', {
                method: 'POST', credentials: 'include',
                headers: {'Content-Type':'application/json','x-excelnt-client':'vscode'},
                body: JSON.stringify({name: args.name})
            });
            const j = await r.json();
            return JSON.stringify({status: r.status, secret: j.secret || '', created: j.created || null});
        }"""
        res = await page.evaluate(script, {"name": name})
        d = json.loads(res)
        return d.get("secret") or None
    except Exception:
        return None
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def _click(page, rx: str):
    """Klik elemen pertama yang teksnya cocok regex."""
    await page.evaluate(
        """(re) => { const r=new RegExp(re,'i');
            const b=[...document.querySelectorAll('button,a,div[role=button],span')].find(x=>r.test((x.innerText||'').trim()));
            if(b) b.click(); }""", rx)


async def _ui_error(page) -> str:
    return await page.evaluate(
        """() => [...document.querySelectorAll('[class*=error],[role=alert],[class*=Error],[class*=alert]')]
                 .map(e=>e.innerText).filter(Boolean).join(' | ')""")


def _parse_proxy(proxy: str) -> Dict[str, Any]:
    from urllib.parse import urlparse
    u = urlparse(proxy)
    scheme = u.scheme or "http"
    d: Dict[str, Any] = {"server": f"{scheme}://{u.hostname}:{u.port}"}
    if u.username:
        d["username"] = u.username
    if u.password:
        d["password"] = u.password
    return d


def _append_account(email: str, password: str, apikey: str, balance: str = ""):
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "accounts.txt"
    with open(p, "a") as f:
        f.write(f"{email}:{password}:{apikey}:{balance}\n")
