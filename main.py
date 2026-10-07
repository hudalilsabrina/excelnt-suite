#!/usr/bin/env python3
"""Excelnt Suite - CLI: factory akun Excelnt + panen API key.

Command:
  harvest [n]      Buat n akun (default 1), klaim promo, panen API key
  test             Uji semua API key tersimpan (panggil gateway)
  report           Ringkasan akun + balance
  sync             Inject API key ke 9router
  probe            Cek apakah signup Excelnt sedang aktif
"""
import argparse
import asyncio
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from rich.table import Table
from rich import box

from src import excelnt

C = Console()
ROOT = Path(__file__).resolve().parent
ACCOUNTS = ROOT / "accounts.txt"
GATEWAY = "https://excelnt.ai/v1"


def _load_accounts():
    if not ACCOUNTS.exists():
        return []
    out = []
    for line in ACCOUNTS.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) >= 3:
            out.append({"email": parts[0], "password": parts[1], "apikey": parts[2],
                        "balance": parts[3] if len(parts) > 3 else ""})
    return out


def cmd_harvest(n, promo, ref, no_proxy):
    proxies = []
    if not no_proxy:
        for f in (ROOT / "proxies_webshare.txt", ROOT / "proxies.txt"):
            if f.exists():
                proxies = [l.strip() for l in f.read_text().splitlines()
                           if l.strip() and not l.startswith("#")]
                if proxies:
                    break
    if proxies:
        C.print(f"[cyan]Rotasi {len(proxies)} proxy[/]")
    ok = 0
    for i in range(1, n + 1):
        px = proxies[(i - 1) % len(proxies)] if proxies else None
        C.print(f"[cyan]=== Akun {i}/{n} ===[/]" + (f" [dim]via {px}[/]" if px else ""))
        r = asyncio.run(excelnt.harvest_excelnt(headless=False, promo=promo, ref=ref, proxy=px))
        if r.get("ok"):
            ok += 1
        else:
            C.print(f"[yellow]  gagal: {r.get('error')} {r.get('ui_error','')[:120]}[/]")
    C.print(f"\n[bold]Selesai: {ok}/{n} sukses[/]")


def cmd_test():
    accts = _load_accounts()
    if not accts:
        C.print("[yellow]Belum ada akun.[/]")
        return
    C.print(f"[cyan]Uji {len(accts)} API key ke {GATEWAY}...[/]")
    t = Table(box=box.ROUNDED, title="Test API key")
    t.add_column("Email", style="cyan")
    t.add_column("Status")
    t.add_column("Info", style="dim")
    for a in accts:
        try:
            req = urllib.request.Request(GATEWAY + "/models",
                                         headers={"Authorization": f"Bearer {a['apikey']}"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read())
                n = len(d.get("data", []))
            t.add_row(a["email"][:28], "[green]OK[/]", f"{n} model")
        except Exception as e:
            t.add_row(a["email"][:28], "[red]FAIL[/]", str(e)[:40])
    C.print(t)


def cmd_report():
    accts = _load_accounts()
    C.print(f"[bold]Total akun: {len(accts)}[/]")
    if not accts:
        return
    t = Table(box=box.ROUNDED)
    t.add_column("#", justify="right")
    t.add_column("Email", style="cyan")
    t.add_column("API key")
    t.add_column("Balance", style="green")
    for i, a in enumerate(accts, 1):
        t.add_row(str(i), a["email"], a["apikey"][:16] + "...", a.get("balance", "-"))
    C.print(t)


def cmd_probe():
    try:
        req = urllib.request.Request(GATEWAY + "/models")
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
        C.print(f"[green]Gateway aktif — {len(d.get('data', []))} model[/]")
    except Exception as e:
        C.print(f"[red]Gateway bermasalah: {e}[/]")


def cmd_sync():
    from src import router9
    accts = _load_accounts()
    if not accts:
        C.print("[yellow]Belum ada akun.[/]")
        return
    n = 0
    for a in accts:
        try:
            router9.add_openai_provider(
                name=f"excelnt-{a['email'].split('@')[0]}",
                base_url=GATEWAY, api_key=a["apikey"])
            n += 1
            C.print(f"[green]  synced {a['email']}[/]")
        except Exception as e:
            C.print(f"[yellow]  gagal {a['email']}: {e}[/]")
    C.print(f"[bold]{n}/{len(accts)} tersinkron ke 9router[/]")


def main():
    ap = argparse.ArgumentParser(prog="excelnt", description="Excelnt Suite")
    sub = ap.add_subparsers(dest="cmd")
    h = sub.add_parser("harvest"); h.add_argument("n", nargs="?", type=int, default=1)
    h.add_argument("--promo", default=excelnt.DEFAULT_PROMO)
    h.add_argument("--ref", default="schneizel-f969")
    h.add_argument("--no-proxy", action="store_true")
    sub.add_parser("test")
    sub.add_parser("report")
    sub.add_parser("sync")
    sub.add_parser("probe")
    a = ap.parse_args()
    if a.cmd == "harvest":
        cmd_harvest(a.n, a.promo, a.ref, a.no_proxy)
    elif a.cmd == "test":
        cmd_test()
    elif a.cmd == "report":
        cmd_report()
    elif a.cmd == "sync":
        cmd_sync()
    elif a.cmd == "probe":
        cmd_probe()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
