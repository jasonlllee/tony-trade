"""
Tony daily check — exchange-native data, no third-party aggregators.

Primary:   OKX public API (mark price + funding + OI; Jason trades here)
Secondary: Binance spot (24h OHLCV + EMA from daily klines, cross-check)

Run locally (Claude Code sandbox blocks all exchange APIs):
    python3 scripts/daily_check.py
    python3 scripts/daily_check.py --quick   # OKX-only, skip EMA/Binance

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
import fetch_okx as okx  # noqa: E402
import indicators as ind  # noqa: E402

INSTS_OKX = ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
PAIRS_BN = {"BTCUSDT": "BTCUSDT", "ETHUSDT": "ETHUSDT", "SOLUSDT": "SOLUSDT"}


def pct(x, digits=2):
    return "n/a" if x is None else f"{x:+.{digits}f}%"


def usd(x, digits=0):
    return "n/a" if x is None else f"${x:,.{digits}f}"


def funding_tag(fund_pct):
    if fund_pct is None:
        return "n/a"
    if fund_pct > 0.05:
        return f"{fund_pct:+.4f}% (hot — longs crowded)"
    if fund_pct > 0.02:
        return f"{fund_pct:+.4f}% (elevated)"
    if fund_pct > -0.01:
        return f"{fund_pct:+.4f}% (healthy)"
    return f"{fund_pct:+.4f}% (shorts crowded — contrarian long)"


def cross_check(okx_mark, bn_last):
    if okx_mark is None or bn_last is None:
        return "one source missing"
    diff_pct = abs(okx_mark - bn_last) / bn_last * 100
    if diff_pct > 0.5:
        return f"⚠️ {diff_pct:.2f}% divergence — re-verify before trading"
    return f"✅ aligned ({diff_pct:.2f}%)"


def run(quick=False):
    okx_snap = okx.snapshot(INSTS_OKX)
    out = {"ts_utc": int(time.time()), "okx": okx_snap}

    if not quick:
        bn_snap = bn.snapshot(PAIRS_BN)
        btc_daily = bn.klines("BTCUSDT", "1d", 250)
        eth_daily = bn.klines("ETHUSDT", "1d", 250)
        out["binance"] = bn_snap
        out["btc_indicators"] = ind.summary(btc_daily)
        out["eth_indicators"] = ind.summary(eth_daily)
        okx_btc_mark = okx_snap.get("BTC-USDT-SWAP", {}).get("mark")
        bn_btc_last = bn_snap.get("BTCUSDT", {}).get("spot_last")
        out["price_cross_check"] = cross_check(okx_btc_mark, bn_btc_last)
    return out


def print_report(r):
    okx_ = r["okx"]
    btc = okx_.get("BTC-USDT-SWAP", {})
    eth = okx_.get("ETH-USDT-SWAP", {})
    sol = okx_.get("SOL-USDT-SWAP", {})

    print("=" * 60)
    print(f"DAILY CHECK — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(r['ts_utc']))}")
    print("=" * 60)

    print("\n[OKX — execution venue, authoritative]")
    print(f"  BTC-USDT-SWAP  mark={usd(btc.get('mark'))}  last={usd(btc.get('last'))}")
    print(f"                 24h: {usd(btc.get('low_24h'))} – {usd(btc.get('high_24h'))}")
    print(f"                 funding: {funding_tag(btc.get('funding_rate_pct'))}")
    print(f"                 OI: {btc.get('open_interest_ccy', 0):,.1f} BTC ({usd(btc.get('open_interest_usd'))})")
    print(f"  ETH-USDT-SWAP  mark={usd(eth.get('mark'), 2)}  funding={funding_tag(eth.get('funding_rate_pct'))}")
    print(f"  SOL-USDT-SWAP  mark={usd(sol.get('mark'), 2)}  funding={funding_tag(sol.get('funding_rate_pct'))}")

    if "binance" in r:
        ind_btc = r["btc_indicators"]
        print(f"\n[BINANCE — cross-check + EMAs]")
        print(f"  cross-check: {r['price_cross_check']}")
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
    ap.add_argument("--quick", action="store_true", help="OKX only, skip Binance EMA")
    args = ap.parse_args()
    try:
        print_report(run(quick=args.quick))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("HINT: OKX/Binance APIs may be unreachable. Run from a machine with open internet.", file=sys.stderr)
        sys.exit(1)
