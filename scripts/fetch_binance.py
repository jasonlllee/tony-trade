"""
Binance public API client — spot + USD-M futures.

No authentication required for public endpoints.
Run locally (outside Claude Code sandbox) — sandbox blocks api.binance.com.

Spot docs:    https://developers.binance.com/docs/binance-spot-api-docs
Futures docs: https://developers.binance.com/docs/derivatives/usds-margined-futures

Usage:
    python3 scripts/fetch_binance.py                        # snapshot major coins
    python3 scripts/fetch_binance.py --klines BTCUSDT 1d 250
    python3 scripts/fetch_binance.py --funding BTCUSDT
    python3 scripts/fetch_binance.py --oi BTCUSDT
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

SPOT_BASE = "https://api.binance.com"
FUTURES_BASE = "https://fapi.binance.com"

# spot_symbol -> futures_symbol (USD-M perp)
DEFAULT_PAIRS = {
    "BTCUSDT": "BTCUSDT",
    "ETHUSDT": "ETHUSDT",
    "SOLUSDT": "SOLUSDT",
}


def _get(url: str, timeout: float = 10.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ticker_24h(symbol: str) -> dict:
    return _get(f"{SPOT_BASE}/api/v3/ticker/24hr?symbol={symbol}")


def klines(symbol: str, interval: str = "1d", limit: int = 250, futures: bool = False) -> list:
    base = FUTURES_BASE + "/fapi/v1/klines" if futures else SPOT_BASE + "/api/v3/klines"
    q = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "limit": limit})
    return _get(f"{base}?{q}")


def premium_index(symbol: str) -> dict:
    """Current mark price, index price, funding rate (per 8h)."""
    return _get(f"{FUTURES_BASE}/fapi/v1/premiumIndex?symbol={symbol}")


def funding_history(symbol: str, limit: int = 30) -> list:
    return _get(f"{FUTURES_BASE}/fapi/v1/fundingRate?symbol={symbol}&limit={limit}")


def open_interest(symbol: str) -> dict:
    return _get(f"{FUTURES_BASE}/fapi/v1/openInterest?symbol={symbol}")


def long_short_ratio(symbol: str, period: str = "1h", limit: int = 1) -> list:
    """Top trader long/short ratio (accounts)."""
    q = urllib.parse.urlencode({"symbol": symbol, "period": period, "limit": limit})
    return _get(f"{FUTURES_BASE}/futures/data/topLongShortAccountRatio?{q}")


def snapshot(pairs: dict[str, str] = DEFAULT_PAIRS) -> dict:
    out = {}
    for spot_sym, fut_sym in pairs.items():
        row: dict = {}
        try:
            t = ticker_24h(spot_sym)
            row["spot_last"] = float(t["lastPrice"])
            row["spot_chg_24h_pct"] = float(t["priceChangePercent"])
            row["spot_high_24h"] = float(t["highPrice"])
            row["spot_low_24h"] = float(t["lowPrice"])
            row["spot_volume_quote_24h"] = float(t["quoteVolume"])
        except Exception as e:
            row["spot_error"] = str(e)
        try:
            p = premium_index(fut_sym)
            row["perp_mark"] = float(p["markPrice"])
            row["perp_index"] = float(p["indexPrice"])
            row["perp_funding_8h_pct"] = float(p["lastFundingRate"]) * 100
            row["perp_next_funding_ms"] = int(p["nextFundingTime"])
        except Exception as e:
            row["perp_error"] = str(e)
        try:
            oi = open_interest(fut_sym)
            row["perp_open_interest"] = float(oi["openInterest"])
        except Exception as e:
            row["oi_error"] = str(e)
        out[spot_sym] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--klines", nargs=3, metavar=("SYMBOL", "INTERVAL", "LIMIT"))
    ap.add_argument("--funding", metavar="SYMBOL")
    ap.add_argument("--oi", metavar="SYMBOL")
    ap.add_argument("--ls-ratio", metavar="SYMBOL")
    args = ap.parse_args()

    try:
        if args.klines:
            print(json.dumps(klines(args.klines[0], args.klines[1], int(args.klines[2])), indent=2))
        elif args.funding:
            print(json.dumps(premium_index(args.funding), indent=2))
        elif args.oi:
            print(json.dumps(open_interest(args.oi), indent=2))
        elif args.ls_ratio:
            print(json.dumps(long_short_ratio(args.ls_ratio), indent=2))
        else:
            print(json.dumps(snapshot(), indent=2))
    except urllib.error.URLError as e:
        print(f"BINANCE_API_UNREACHABLE: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
