"""
Hyperliquid public info API client.

Docs: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint

No authentication required. Endpoint is POST-only.
Run locally (outside Claude Code sandbox) — the sandbox blocks api.hyperliquid.xyz.

Usage:
    python3 scripts/fetch_hyperliquid.py                # snapshot major coins
    python3 scripts/fetch_hyperliquid.py --coin BTC     # one coin, full ctx
    python3 scripts/fetch_hyperliquid.py --funding-history BTC 14  # last 14d
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
DEFAULT_COINS = ("BTC", "ETH", "SOL", "HYPE")


def _post(payload: dict, timeout: float = 10.0) -> dict | list:
    req = urllib.request.Request(
        HL_INFO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def meta_and_ctxs() -> tuple[list[dict], list[dict]]:
    data = _post({"type": "metaAndAssetCtxs"})
    return data[0]["universe"], data[1]


def snapshot(coins: tuple[str, ...] = DEFAULT_COINS) -> dict:
    universe, ctxs = meta_and_ctxs()
    idx_by_sym = {m["name"]: i for i, m in enumerate(universe)}
    out = {}
    for sym in coins:
        if sym not in idx_by_sym:
            out[sym] = {"error": "not_listed_on_hyperliquid"}
            continue
        c = ctxs[idx_by_sym[sym]]
        mark = float(c["markPx"])
        prev = float(c["prevDayPx"])
        out[sym] = {
            "mark": mark,
            "oracle": float(c.get("oraclePx", mark)),
            "mid": float(c.get("midPx", mark)),
            "prev_day": prev,
            "chg_24h_pct": (mark / prev - 1) * 100 if prev else None,
            # funding on HL is per-hour, not per-8h. Convert to per-8h for legacy comparison.
            "funding_hourly_pct": float(c.get("funding", 0)) * 100,
            "funding_8h_pct": float(c.get("funding", 0)) * 100 * 8,
            "open_interest": float(c.get("openInterest", 0)),
            "day_volume_base": float(c.get("dayNtlVlm", 0)),
            "premium_pct": float(c.get("premium", 0)) * 100,
        }
    return out


def funding_history(coin: str, days: int = 14) -> list[dict]:
    start_ms = int((time.time() - days * 86400) * 1000)
    return _post({"type": "fundingHistory", "coin": coin, "startTime": start_ms})


def candles(coin: str, interval: str = "1d", days: int = 250) -> list[dict]:
    """Daily candles for EMA computation."""
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 86400 * 1000
    return _post({
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": interval, "startTime": start_ms, "endTime": end_ms},
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", help="Single coin, e.g. BTC")
    ap.add_argument("--funding-history", nargs=2, metavar=("COIN", "DAYS"))
    ap.add_argument("--candles", nargs=2, metavar=("COIN", "DAYS"))
    args = ap.parse_args()

    try:
        if args.funding_history:
            print(json.dumps(funding_history(args.funding_history[0], int(args.funding_history[1])), indent=2))
        elif args.candles:
            print(json.dumps(candles(args.candles[0], "1d", int(args.candles[1])), indent=2))
        elif args.coin:
            print(json.dumps(snapshot((args.coin,)), indent=2))
        else:
            print(json.dumps(snapshot(), indent=2))
    except urllib.error.URLError as e:
        print(f"HL_API_UNREACHABLE: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
