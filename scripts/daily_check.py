"""
Tony daily check — exchange-native data only.

Primary:   Hyperliquid (perp mark + funding + OI — deep derivatives sentiment)
Backup:    Coinbase Exchange (US-regulated spot anchor)
EMA/hist:  Binance daily klines (longest clean history)

Run locally (Claude Code sandbox blocks all exchange APIs):
    python3 scripts/daily_check.py
    python3 scripts/daily_check.py --quick   # HL + Coinbase only, skip EMA

Output: human-readable report + JSON block to paste back into the chat.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fetch_binance as bn  # noqa: E402
import fetch_coinbase as cb  # noqa: E402
import fetch_hyperliquid as hl  # noqa: E402
import indicators as ind  # noqa: E402

COINS_HL = ("BTC", "ETH", "SOL", "HYPE")
PAIRS_CB = ("BTC-USD", "ETH-USD", "SOL-USD")
PAIRS_BN = {"BTCUSDT": "BTCUSDT", "ETHUSDT": "ETHUSDT", "SOLUSDT": "SOLUSDT"}


def pct(x, digits=2):
    return "n/a" if x is None else f"{x:+.{digits}f}%"


def usd(x, digits=0):
    return "n/a" if x is None else f"${x:,.{digits}f}"


def funding_tag(fund_8h_pct):
    if fund_8h_pct is None:
        return "n/a"
    if fund_8h_pct > 0.05:
        return f"{fund_8h_pct:+.4f}% (hot — longs crowded)"
    if fund_8h_pct > 0.02:
        return f"{fund_8h_pct:+.4f}% (elevated)"
    if fund_8h_pct > -0.01:
        return f"{fund_8h_pct:+.4f}% (healthy)"
    return f"{fund_8h_pct:+.4f}% (shorts crowded — contrarian long)"


def cross_check(primary, backup, label_p="HL", label_b="Coinbase"):
    if primary is None or backup is None:
        return "one source missing"
    diff_pct = abs(primary - backup) / backup * 100
    tag = "⚠️" if diff_pct > 0.5 else "✅"
    return f"{tag} {label_p} vs {label_b}: {diff_pct:.2f}% diff"


def run(quick=False):
    hl_snap = hl.snapshot(COINS_HL)
    cb_snap = cb.snapshot(PAIRS_CB)

    out = {
        "ts_utc": int(time.time()),
        "hyperliquid": hl_snap,
        "coinbase": cb_snap,
    }

    hl_btc = hl_snap.get("BTC", {}).get("mark")
    cb_btc = cb_snap.get("BTC-USD", {}).get("last")
    out["btc_cross_check"] = cross_check(hl_btc, cb_btc)

    if not quick:
        btc_daily = bn.klines("BTCUSDT", "1d", 250)
        eth_daily = bn.klines("ETHUSDT", "1d", 250)
        out["btc_indicators"] = ind.summary(btc_daily)
        out["eth_indicators"] = ind.summary(eth_daily)
    return out


def print_report(r):
    hl_ = r["hyperliquid"]
    cb_ = r["coinbase"]
    btc_hl = hl_.get("BTC", {})
    eth_hl = hl_.get("ETH", {})
    sol_hl = hl_.get("SOL", {})
    hype_hl = hl_.get("HYPE", {})
    btc_cb = cb_.get("BTC-USD", {})

    print("=" * 60)
    print(f"DAILY CHECK — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(r['ts_utc']))}")
    print("=" * 60)

    print("\n[HYPERLIQUID — primary, perp]")
    print(f"  BTC  mark={usd(btc_hl.get('mark'))}  24h={pct(btc_hl.get('chg_24h_pct'))}")
    print(f"       funding(8h): {funding_tag(btc_hl.get('funding_8h_pct'))}")
    print(f"       OI: {btc_hl.get('open_interest', 0):,.1f}")
    print(f"  ETH  mark={usd(eth_hl.get('mark'), 2)}  24h={pct(eth_hl.get('chg_24h_pct'))}")
    print(f"  SOL  mark={usd(sol_hl.get('mark'), 2)}  24h={pct(sol_hl.get('chg_24h_pct'))}")
    print(f"  HYPE mark={usd(hype_hl.get('mark'), 2)}  24h={pct(hype_hl.get('chg_24h_pct'))}")

    print(f"\n[COINBASE — backup, spot]")
    print(f"  BTC-USD  last={usd(btc_cb.get('last'))}  24h={pct(btc_cb.get('chg_24h_pct'))}")
    print(f"           24h range: {usd(btc_cb.get('low_24h'))} – {usd(btc_cb.get('high_24h'))}")
    print(f"  cross-check: {r['btc_cross_check']}")

    if "btc_indicators" in r:
        ind_btc = r["btc_indicators"]
        print(f"\n[BINANCE — EMAs from daily closes]")
        print(f"  BTC last close: {usd(ind_btc.get('last_close'))}")
        for p in (50, 100, 200):
            e = ind_btc["emas"].get(p)
            v = ind_btc["vs_ema_pct"].get(p)
            print(f"  EMA{p:>3}: {usd(e)}   (price vs EMA: {pct(v)})")
        print(f"  7d range:  {usd(ind_btc.get('low_7d'))} – {usd(ind_btc.get('high_7d'))}")
        print(f"  30d range: {usd(ind_btc.get('low_30d'))} – {usd(ind_btc.get('high_30d'))}")

    print("\n[RAW JSON — paste to Tony]")
    print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="HL + Coinbase only, skip Binance EMA")
    args = ap.parse_args()
    try:
        print_report(run(quick=args.quick))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("HINT: HL/Coinbase/Binance APIs may be unreachable. Run from machine with open internet.", file=sys.stderr)
        sys.exit(1)
