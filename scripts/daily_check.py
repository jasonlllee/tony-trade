"""
Tony daily check — pulls exchange-native data only.

Primary:   Hyperliquid (mark price + funding, since that's where Jason trades)
Secondary: Binance spot (24h OHLCV) + Binance futures (funding, OI) for cross-validation and EMA.

Run locally (outside the sandboxed Claude Code environment):
    python3 scripts/daily_check.py

Output is human-readable plus a JSON block Tony can paste into Claude.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fetch_binance as bn  # noqa: E402
import fetch_hyperliquid as hl  # noqa: E402
import indicators as ind  # noqa: E402

COINS_HL = ("BTC", "ETH", "SOL", "HYPE")
PAIRS_BN = {"BTCUSDT": "BTCUSDT", "ETHUSDT": "ETHUSDT", "SOLUSDT": "SOLUSDT"}


def pct(x: float | None, digits: int = 2) -> str:
    return "n/a" if x is None else f"{x:+.{digits}f}%"


def usd(x: float | None, digits: int = 0) -> str:
    return "n/a" if x is None else f"${x:,.{digits}f}"


def funding_tag(fund_8h_pct: float | None) -> str:
    if fund_8h_pct is None:
        return "n/a"
    if fund_8h_pct > 0.05:
        return f"{fund_8h_pct:+.4f}% (hot — longs crowded)"
    if fund_8h_pct > 0.02:
        return f"{fund_8h_pct:+.4f}% (elevated)"
    if fund_8h_pct > -0.01:
        return f"{fund_8h_pct:+.4f}% (healthy)"
    return f"{fund_8h_pct:+.4f}% (shorts crowded — contrarian long)"


def cross_check(hl_mark: float, bn_last: float) -> str:
    if hl_mark is None or bn_last is None:
        return "one source missing"
    diff_pct = abs(hl_mark - bn_last) / bn_last * 100
    if diff_pct > 0.5:
        return f"⚠️ {diff_pct:.2f}% divergence — re-verify before trading"
    return f"✅ aligned ({diff_pct:.2f}%)"


def scenario_status(btc_mark: float, btc_24h_low: float | None) -> dict:
    """Evaluate the three playbooks from tony_handoff.md."""
    a_trigger = btc_mark > 73_500 and (btc_24h_low is None or btc_24h_low > 72_000)
    b_trigger = 68_500 <= btc_mark <= 69_500
    c_trigger = btc_mark < 65_800
    return {
        "A_breakout_long": "TRIGGERED" if a_trigger else f"distance {((73500-btc_mark)/btc_mark*100):+.2f}% to $73.5K",
        "B_pullback_long": "TRIGGERED" if b_trigger else f"distance {((69000-btc_mark)/btc_mark*100):+.2f}% to $69K zone",
        "C_breakdown_short": "TRIGGERED" if c_trigger else f"distance {((65800-btc_mark)/btc_mark*100):+.2f}% to $65.8K",
    }


def run() -> dict:
    hl_snap = hl.snapshot(COINS_HL)
    bn_snap = bn.snapshot(PAIRS_BN)

    # BTC daily klines for EMA
    btc_daily = bn.klines("BTCUSDT", "1d", 250)
    eth_daily = bn.klines("ETHUSDT", "1d", 250)
    btc_ind = ind.summary(btc_daily)
    eth_ind = ind.summary(eth_daily)

    btc_hl_mark = hl_snap.get("BTC", {}).get("mark")
    btc_bn_last = bn_snap.get("BTCUSDT", {}).get("spot_last")

    return {
        "ts_utc": int(time.time()),
        "sources": {
            "hyperliquid": hl_snap,
            "binance": bn_snap,
        },
        "btc_indicators": btc_ind,
        "eth_indicators": eth_ind,
        "price_cross_check": cross_check(btc_hl_mark, btc_bn_last),
        "playbooks": scenario_status(btc_hl_mark or btc_bn_last, bn_snap.get("BTCUSDT", {}).get("spot_low_24h")),
    }


def print_report(r: dict) -> None:
    hl_ = r["sources"]["hyperliquid"]
    bn_ = r["sources"]["binance"]
    btc_hl = hl_.get("BTC", {})
    eth_hl = hl_.get("ETH", {})
    sol_hl = hl_.get("SOL", {})
    hype_hl = hl_.get("HYPE", {})
    btc_bn = bn_.get("BTCUSDT", {})
    ind_btc = r["btc_indicators"]

    print("=" * 60)
    print(f"DAILY CHECK — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(r['ts_utc']))}")
    print("=" * 60)

    print("\n[PRICES — Hyperliquid primary, Binance cross-check]")
    print(f"  BTC  HL mark={usd(btc_hl.get('mark'))}  BN spot={usd(btc_bn.get('spot_last'))}  24h={pct(btc_hl.get('chg_24h_pct'))}")
    print(f"       cross-check: {r['price_cross_check']}")
    print(f"       BN 24h range: {usd(btc_bn.get('spot_low_24h'))} – {usd(btc_bn.get('spot_high_24h'))}")
    print(f"  ETH  HL mark={usd(eth_hl.get('mark'), 2)}  24h={pct(eth_hl.get('chg_24h_pct'))}")
    print(f"  SOL  HL mark={usd(sol_hl.get('mark'), 2)}  24h={pct(sol_hl.get('chg_24h_pct'))}")
    print(f"  HYPE HL mark={usd(hype_hl.get('mark'), 2)}  24h={pct(hype_hl.get('chg_24h_pct'))}")

    print("\n[BTC TECHNICALS — Binance daily closes]")
    print(f"  last close:  {usd(ind_btc.get('last_close'))}")
    for p in (50, 100, 200):
        e = ind_btc["emas"].get(p)
        v = ind_btc["vs_ema_pct"].get(p) if "vs_ema_pct" in ind_btc else None
        print(f"  EMA{p:>3}:     {usd(e)}   (price vs EMA: {pct(v)})")
    print(f"  7d range:   {usd(ind_btc.get('low_7d'))} – {usd(ind_btc.get('high_7d'))}")
    print(f"  30d range:  {usd(ind_btc.get('low_30d'))} – {usd(ind_btc.get('high_30d'))}")

    print("\n[DERIVATIVES]")
    print(f"  HL BTC funding 8h: {funding_tag(btc_hl.get('funding_8h_pct'))}")
    print(f"  BN BTC funding 8h: {funding_tag(btc_bn.get('perp_funding_8h_pct'))}")
    print(f"  HL BTC OI: {btc_hl.get('open_interest')}")
    print(f"  BN BTC OI (contracts): {btc_bn.get('perp_open_interest')}")

    print("\n[PLAYBOOK STATUS]")
    for k, v in r["playbooks"].items():
        print(f"  {k}: {v}")

    print("\n[RAW JSON — paste to Tony for decision]")
    print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    try:
        print_report(run())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("HINT: Hyperliquid/Binance APIs may be unreachable in this environment.", file=sys.stderr)
        print("      Run this script on a machine with open internet.", file=sys.stderr)
        sys.exit(1)
