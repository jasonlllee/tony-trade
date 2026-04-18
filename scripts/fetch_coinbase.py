"""
Coinbase Exchange public API client — no auth required.

US-regulated spot price anchor. Used as backup to Hyperliquid.

Run locally (Claude Code sandbox blocks api.exchange.coinbase.com):
    python3 scripts/fetch_coinbase.py                    # snapshot major spot pairs
    python3 scripts/fetch_coinbase.py --pair BTC-USD     # one pair
    python3 scripts/fetch_coinbase.py --candles BTC-USD 86400 300   # daily candles

Docs: https://docs.cdp.coinbase.com/exchange/docs/welcome
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

CB_BASE = "https://api.exchange.coinbase.com"

DEFAULT_PAIRS = ("BTC-USD", "ETH-USD", "SOL-USD")


def _get(path: str, timeout: float = 10.0):
    req = urllib.request.Request(f"{CB_BASE}{path}", headers={"User-Agent": "tony-trade/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ticker(pair: str) -> dict:
    """Last trade + 24h volume."""
    return _get(f"/products/{pair}/ticker")


def stats_24h(pair: str) -> dict:
    """24h open/high/low/last/volume."""
    return _get(f"/products/{pair}/stats")


def candles(pair: str, granularity: int = 86400, limit: int = 300) -> list:
    """
    granularity in seconds: 60, 300, 900, 3600, 21600, 86400
    Returns [time, low, high, open, close, volume]
    """
    q = urllib.parse.urlencode({"granularity": granularity})
    return _get(f"/products/{pair}/candles?{q}")


def snapshot(pairs: tuple[str, ...] = DEFAULT_PAIRS) -> dict:
    out = {}
    for p in pairs:
        row: dict = {}
        try:
            t = ticker(p)
            row["last"] = float(t["price"])
            row["bid"] = float(t["bid"])
            row["ask"] = float(t["ask"])
            row["volume_24h_base"] = float(t["volume"])
        except Exception as e:
            row["ticker_error"] = str(e)
        try:
            s = stats_24h(p)
            row["open_24h"] = float(s["open"])
            row["high_24h"] = float(s["high"])
            row["low_24h"] = float(s["low"])
            row["last"] = row.get("last") or float(s["last"])
            if row.get("last") and row.get("open_24h"):
                row["chg_24h_pct"] = (row["last"] / row["open_24h"] - 1) * 100
        except Exception as e:
            row["stats_error"] = str(e)
        out[p] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", help="One pair, e.g. BTC-USD")
    ap.add_argument("--candles", nargs=3, metavar=("PAIR", "GRANULARITY_SEC", "LIMIT"))
    args = ap.parse_args()

    try:
        if args.candles:
            print(json.dumps(candles(args.candles[0], int(args.candles[1]), int(args.candles[2])), indent=2))
        elif args.pair:
            print(json.dumps(snapshot((args.pair,)), indent=2))
        else:
            print(json.dumps(snapshot(), indent=2))
    except urllib.error.URLError as e:
        print(f"COINBASE_API_UNREACHABLE: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
