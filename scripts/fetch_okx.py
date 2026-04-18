"""
OKX public market API client — no auth required.

Run locally (Claude Code sandbox blocks www.okx.com):
    python3 scripts/fetch_okx.py                         # snapshot major perps
    python3 scripts/fetch_okx.py --inst BTC-USDT-SWAP    # one instrument
    python3 scripts/fetch_okx.py --funding BTC-USDT-SWAP # funding rate
    python3 scripts/fetch_okx.py --candles BTC-USDT-SWAP 1D 250

Docs: https://www.okx.com/docs-v5/en/

This is the same data Jason sees on his OKX trading screen. Use this snapshot
as the authoritative price/funding/OI source for all trade decisions.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

OKX_BASE = "https://www.okx.com"

DEFAULT_INSTS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")


def _get(path: str, timeout: float = 10.0) -> dict:
    with urllib.request.urlopen(f"{OKX_BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ticker(inst_id: str) -> dict:
    """Last/mark/24h stats."""
    return _get(f"/api/v5/market/ticker?instId={inst_id}")


def funding_rate(inst_id: str) -> dict:
    return _get(f"/api/v5/public/funding-rate?instId={inst_id}")


def open_interest(inst_id: str) -> dict:
    return _get(f"/api/v5/public/open-interest?instId={inst_id}")


def mark_price(inst_id: str) -> dict:
    return _get(f"/api/v5/public/mark-price?instId={inst_id}")


def candles(inst_id: str, bar: str = "1D", limit: int = 250) -> dict:
    """OKX returns array; latest first."""
    q = urllib.parse.urlencode({"instId": inst_id, "bar": bar, "limit": limit})
    return _get(f"/api/v5/market/candles?{q}")


def snapshot(insts: tuple[str, ...] = DEFAULT_INSTS) -> dict:
    out = {}
    for inst in insts:
        row: dict = {}
        try:
            t = ticker(inst)["data"][0]
            row["last"] = float(t["last"])
            row["high_24h"] = float(t["high24h"])
            row["low_24h"] = float(t["low24h"])
            row["vol_ccy_24h"] = float(t["volCcy24h"])
        except Exception as e:
            row["ticker_error"] = str(e)
        try:
            mp = mark_price(inst)["data"][0]
            row["mark"] = float(mp["markPx"])
        except Exception as e:
            row["mark_error"] = str(e)
        try:
            f = funding_rate(inst)["data"][0]
            row["funding_rate_pct"] = float(f["fundingRate"]) * 100
            row["next_funding_time_ms"] = int(f["nextFundingTime"])
        except Exception as e:
            row["funding_error"] = str(e)
        try:
            oi = open_interest(inst)["data"][0]
            row["open_interest_ccy"] = float(oi["oiCcy"])  # in base currency (BTC)
            row["open_interest_usd"] = float(oi["oiUsd"])
        except Exception as e:
            row["oi_error"] = str(e)
        out[inst] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", help="One instrument, e.g. BTC-USDT-SWAP")
    ap.add_argument("--funding", help="Funding rate for one inst")
    ap.add_argument("--candles", nargs=3, metavar=("INST", "BAR", "LIMIT"))
    args = ap.parse_args()

    try:
        if args.candles:
            print(json.dumps(candles(args.candles[0], args.candles[1], int(args.candles[2])), indent=2))
        elif args.funding:
            print(json.dumps(funding_rate(args.funding), indent=2))
        elif args.inst:
            print(json.dumps(snapshot((args.inst,)), indent=2))
        else:
            print(json.dumps(snapshot(), indent=2))
    except urllib.error.URLError as e:
        print(f"OKX_API_UNREACHABLE: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
