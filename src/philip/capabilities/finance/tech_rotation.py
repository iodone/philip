"""Tech Theme Rotation Monitor — akshare data source.

Tracks 11 tech themes' capital rotation direction relative to QQQ benchmark.
"""

from __future__ import annotations

from typing import Any

import akshare as ak
import numpy as np
import pandas as pd

BENCHMARK = "QQQ"

ETF_THEMES: dict[str, str] = {
    "半导体": "SMH",
    "软件": "IGV",
    "云计算": "SKYY",
    "网络安全": "CIBR",
    "机器人": "BOTZ",
    "AI综合": "AIQ",
}

BASKET_THEMES: dict[str, list[str]] = {
    "光模块": ["ANET", "CIEN", "COHR", "LITE", "AAOI"],
    "储存": ["MU", "WDC", "STX"],
    "数据中心电力散热": ["VRT", "ETN", "PWR", "CEG", "GEV"],
    "云巨头": ["MSFT", "AMZN", "GOOGL", "META"],
    "AI硬件卖方": ["NVDA", "AVGO", "AMD", "ANET"],
}

# Thresholds
TREND_LEN = 20
SLOW_LEN = 50
VOL_LEN = 20
VOL_CONFIRM = 1.30
CROWD_REL60 = 18.0
CROWD_DIST50 = 8.0
SCORE_CONFIRMED = 75
SCORE_EARLY = 60
SCORE_WEAK = 45

TREND_MAP: dict[int, str] = {2: "强", 1: "偏强", -1: "偏弱", -2: "弱"}
STATE_MAP: dict[int, str] = {
    3: "拥挤主升",
    2: "确认进入",
    1: "早期轮动",
    0: "中性观察",
    -1: "资金撤出",
    -2: "派发/撤出",
}


def fetch_daily(symbol: str, days: int = 300) -> pd.DataFrame | None:
    """Fetch daily OHLCV for a US stock via akshare."""
    try:
        df = ak.stock_us_daily(symbol=symbol, adjust="qfq")
        df = df.rename(
            columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        df["DollarVol"] = df["Close"] * df["Volume"]
        return df.tail(days)
    except Exception:
        return None


def fetch_all_data() -> dict[str, pd.DataFrame]:
    """Fetch daily data for all tracked symbols."""
    syms: set[str] = {BENCHMARK}
    syms.update(ETF_THEMES.values())
    for basket in BASKET_THEMES.values():
        syms.update(basket)

    data: dict[str, pd.DataFrame] = {}
    for sym in sorted(syms):
        df = fetch_daily(sym)
        if df is not None:
            data[sym] = df
    return data


def build_basket(
    data: dict[str, pd.DataFrame], symbols: list[str]
) -> pd.DataFrame | None:
    """Build a composite basket index from individual stocks."""
    dfs = [data[s] for s in symbols if s in data]
    if not dfs:
        return None

    idx = dfs[0].index
    for d in dfs[1:]:
        idx = idx.intersection(d.index)
    if len(idx) < SLOW_LEN + 10:
        return None

    rets = pd.DataFrame(index=idx)
    for s, d in zip(symbols, dfs):
        rets[s] = d.loc[idx, "Close"].pct_change()
    ci = (1 + rets.mean(axis=1)).cumprod() * 100

    dv = pd.DataFrame(index=idx)
    for s, d in zip(symbols, dfs):
        dv[s] = d.loc[idx, "DollarVol"]

    br = pd.Series(0.0, index=idx)
    for s, d in zip(symbols, dfs):
        c = d.loc[idx, "Close"]
        m = c.rolling(TREND_LEN).mean()
        br += (c > m).astype(float)
    br = br / len(symbols) * 100

    return pd.DataFrame({"Close": ci, "DollarVol": dv.sum(axis=1), "Breadth": br})


def calc_metrics(tdf: pd.DataFrame, bdf: pd.DataFrame) -> dict[str, Any]:
    """Calculate rotation metrics for a theme relative to benchmark."""
    ci = tdf.index.intersection(bdf.index)
    if len(ci) < SLOW_LEN + 10:
        return {"valid": False}

    t = tdf.loc[ci]
    b = bdf.loc[ci, "Close"]
    ratio = t["Close"] / b

    r1 = ratio.pct_change(1) * 100
    r5 = ratio.pct_change(5) * 100
    r20 = ratio.pct_change(20) * 100
    r60 = ratio.pct_change(60) * 100
    ma20 = ratio.rolling(TREND_LEN).mean()
    ma50 = ratio.rolling(SLOW_LEN).mean()
    vr = t["DollarVol"] / t["DollarVol"].rolling(VOL_LEN).mean()
    d50 = (ratio / ma50 - 1) * 100

    r60v = r60.iloc[-1] if len(r60.dropna()) > 0 else None
    d50v = d50.iloc[-1] if len(d50.dropna()) > 0 else None
    bv = t["Breadth"].iloc[-1] if "Breadth" in t.columns else None

    # Trend score
    ts = (
        (10 if ratio.iloc[-1] > ma20.iloc[-1] else 0)
        + (10 if ratio.iloc[-1] > ma50.iloc[-1] else 0)
        + (10 if ma20.iloc[-1] > ma20.iloc[-6] else 0)
    )

    # Acceleration score
    acs = (
        (8 if r5.iloc[-1] > 0 else 0)
        + (9 if r5.iloc[-1] > r20.iloc[-1] / 4 else 0)
        + (8 if r5.iloc[-1] > r5.iloc[-6] else 0)
    )

    # Volume score
    vs = (
        20
        if (r1.iloc[-1] > 0 and vr.iloc[-1] >= VOL_CONFIRM)
        else (10 if (r1.iloc[-1] > 0 and vr.iloc[-1] >= 1) else 0)
    )

    # Breadth score
    bs = (
        15
        if (bv is not None and bv >= 70)
        else (8 if (bv is not None and bv >= 50) else 0)
    )

    # Overextension / crowd score
    oe = (r60v is not None and r60v > CROWD_REL60) or (
        d50v is not None and d50v > CROWD_DIST50
    )
    cs = 0 if oe else 10

    sc = ts + acs + vs + bs + cs

    # Trend code
    if ratio.iloc[-1] > ma20.iloc[-1] and ratio.iloc[-1] > ma50.iloc[-1]:
        tc = 2
    elif ratio.iloc[-1] > ma20.iloc[-1]:
        tc = 1
    elif ratio.iloc[-1] < ma20.iloc[-1] and ratio.iloc[-1] < ma50.iloc[-1]:
        tc = -2
    elif ratio.iloc[-1] < ma20.iloc[-1]:
        tc = -1
    else:
        tc = 0

    # State code
    dist = (
        ratio.iloc[-1] < ma20.iloc[-1]
        and r5.iloc[-1] < 0
        and vr.iloc[-1] > VOL_CONFIRM
        and r1.iloc[-1] < 0
    )
    if dist:
        st = -2
    elif oe and sc >= SCORE_EARLY:
        st = 3
    elif sc >= SCORE_CONFIRMED:
        st = 2
    elif sc >= SCORE_EARLY:
        st = 1
    elif sc < SCORE_WEAK and r5.iloc[-1] < 0 and r20.iloc[-1] < 0:
        st = -1
    else:
        st = 0

    def _safe(v: float | None) -> float | None:
        if v is None:
            return None
        return None if isinstance(v, float) and np.isnan(v) else v

    return {
        "valid": True,
        "rel1": _safe(r1.iloc[-1]),
        "rel5": _safe(r5.iloc[-1]),
        "rel20": _safe(r20.iloc[-1]),
        "rel60": _safe(r60v),
        "vol_ratio": _safe(vr.iloc[-1]),
        "breadth": _safe(bv),
        "score": sc,
        "trend_code": tc,
        "state": st,
    }


def run_rotation_monitor() -> list[dict[str, Any]]:
    """Run the full rotation monitor and return structured results."""
    data = fetch_all_data()
    if BENCHMARK not in data:
        return []

    bdf = data[BENCHMARK]
    results: list[dict[str, Any]] = []

    for theme, sym in ETF_THEMES.items():
        if sym in data:
            m = calc_metrics(data[sym], bdf)
            m["theme"] = theme
            m["proxy"] = sym
            results.append(m)

    for theme, syms in BASKET_THEMES.items():
        bk = build_basket(data, syms)
        if bk is not None:
            m = calc_metrics(bk, bdf)
            m["theme"] = theme
            m["proxy"] = "Basket"
            results.append(m)

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results
