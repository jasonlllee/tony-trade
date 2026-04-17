"""
Pure-Python indicators computed from Binance daily klines.
No external deps. Candle rows are Binance format: [openTime, open, high, low, close, volume, ...]
"""
from __future__ import annotations

from typing import Iterable


def _closes(candles: Iterable[list]) -> list[float]:
    return [float(c[4]) for c in candles]


def ema(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    seed = sum(values[:period]) / period
    out = [seed]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    # pad front so indices align with input
    return [float("nan")] * (period - 1) + out


def last(values: list[float]) -> float | None:
    for v in reversed(values):
        if v == v:  # not NaN
            return v
    return None


def summary(candles: list[list]) -> dict:
    closes = _closes(candles)
    last_close = closes[-1] if closes else None
    emas = {p: last(ema(closes, p)) for p in (20, 50, 100, 200)}
    out = {"last_close": last_close, "emas": emas}
    if last_close is not None:
        out["vs_ema_pct"] = {
            p: ((last_close / v - 1) * 100) if v else None for p, v in emas.items()
        }
    # 7d / 30d highs/lows
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    for window in (7, 30):
        if len(candles) >= window:
            out[f"high_{window}d"] = max(highs[-window:])
            out[f"low_{window}d"] = min(lows[-window:])
    return out
