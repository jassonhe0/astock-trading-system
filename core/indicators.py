# -*- coding: utf-8 -*-
"""
技术指标计算引擎（纯 pandas/numpy 实现，无需 TA-Lib C 库）
支持: MA EMA MACD RSI BOLL KDJ CCI ATR OBV VWAP WR 等
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from utils.logger import log


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    对 K 线 DataFrame 批量计算技术指标
    必须包含列: open high low close volume
    """
    df = df.copy()
    if df.empty or len(df) < 5:
        return df

    c = df["close"]
    h = df["high"]
    l = df["low"]
    o = df["open"]
    v = df["volume"]

    # ── 均线 ──────────────────────────────────────
    for p in (5, 10, 20, 30, 60, 120, 250):
        df[f"ma{p}"]  = c.rolling(p).mean().round(3)
        df[f"ema{p}"] = c.ewm(span=p, adjust=False).mean().round(3)

    # ── MACD ─────────────────────────────────────
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["macd_dif"] = (ema12 - ema26).round(4)
    df["macd_dea"] = df["macd_dif"].ewm(span=9, adjust=False).mean().round(4)
    df["macd_bar"] = ((df["macd_dif"] - df["macd_dea"]) * 2).round(4)

    # ── RSI ──────────────────────────────────────
    for period in (6, 12, 24):
        delta = c.diff()
        gain  = delta.clip(lower=0).rolling(period).mean()
        loss  = (-delta.clip(upper=0)).rolling(period).mean()
        rs    = gain / loss.replace(0, np.nan)
        df[f"rsi{period}"] = (100 - 100 / (1 + rs)).round(2)

    # ── BOLL 布林带 ───────────────────────────────
    mid = c.rolling(20).mean()
    std = c.rolling(20).std()
    df["boll_mid"]   = mid.round(3)
    df["boll_up"]    = (mid + 2 * std).round(3)
    df["boll_dn"]    = (mid - 2 * std).round(3)
    df["boll_width"] = ((df["boll_up"] - df["boll_dn"]) / mid.replace(0, np.nan)).round(4)

    # ── KDJ ──────────────────────────────────────
    low9  = l.rolling(9).min()
    high9 = h.rolling(9).max()
    denom = (high9 - low9).replace(0, np.nan)
    rsv   = ((c - low9) / denom * 100).fillna(50)
    k_arr = [50.0] * len(df)
    d_arr = [50.0] * len(df)
    for i in range(1, len(df)):
        k_arr[i] = k_arr[i-1] * 2/3 + rsv.iloc[i] / 3
        d_arr[i] = d_arr[i-1] * 2/3 + k_arr[i] / 3
    df["kdj_k"] = pd.array(k_arr, dtype="float64")
    df["kdj_k"] = df["kdj_k"].round(2)
    df["kdj_d"] = pd.array(d_arr, dtype="float64")
    df["kdj_d"] = df["kdj_d"].round(2)
    df["kdj_j"] = (3 * df["kdj_k"] - 2 * df["kdj_d"]).round(2)

    # ── CCI ──────────────────────────────────────
    tp   = (h + l + c) / 3
    ma14 = tp.rolling(14).mean()
    md14 = tp.rolling(14).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    df["cci"] = ((tp - ma14) / (0.015 * md14.replace(0, np.nan))).round(2)

    # ── ATR 真实波幅 ──────────────────────────────
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    df["atr14"]    = tr.rolling(14).mean().round(3)
    df["atr_pct"]  = (df["atr14"] / c.replace(0, np.nan) * 100).round(2)

    # ── OBV 能量潮 ────────────────────────────────
    obv = [0.0]
    for i in range(1, len(df)):
        if c.iloc[i] > c.iloc[i-1]:
            obv.append(obv[-1] + v.iloc[i])
        elif c.iloc[i] < c.iloc[i-1]:
            obv.append(obv[-1] - v.iloc[i])
        else:
            obv.append(obv[-1])
    df["obv"] = obv

    # ── VWAP 成交量加权均价 ────────────────────────
    amount = df.get("amount", c * v)
    df["vwap"] = (amount / v.replace(0, np.nan)).round(3)

    # ── 量比 & 量均线 ─────────────────────────────
    df["vol_ma5"]   = v.rolling(5).mean().round(0)
    df["vol_ma20"]  = v.rolling(20).mean().round(0)
    df["vol_ratio"] = (v / df["vol_ma5"].replace(0, np.nan)).round(2)

    # ── 价格动量 ──────────────────────────────────
    df["momentum5"]  = c.pct_change(5).round(4)
    df["momentum20"] = c.pct_change(20).round(4)

    # ── 威廉指标 WR ───────────────────────────────
    highest14 = h.rolling(14).max()
    lowest14  = l.rolling(14).min()
    denom14   = (highest14 - lowest14).replace(0, np.nan)
    df["wr14"] = ((highest14 - c) / denom14 * -100).round(2)

    log.debug(f"[指标] 共计算 {len(df)} 条 × {len(df.columns)} 列")
    return df


def calc_support_resistance(df: pd.DataFrame, window: int = 20) -> dict:
    """计算支撑位和压力位，返回 Python 原生 float"""
    if df.empty or len(df) < window:
        return {}
    recent = df.tail(window)
    close  = float(df["close"].iloc[-1])
    high   = float(recent["high"].max())
    low    = float(recent["low"].min())
    mid    = (high + low) / 2
    r1     = 2 * mid - low
    s1     = 2 * mid - high
    return {
        "support1":    round(s1,  3),
        "support2":    round(low, 3),
        "resistance1": round(r1,  3),
        "resistance2": round(high, 3),
        "pivot":       round(mid,  3),
        "current":     round(close, 3),
    }


def detect_candlestick_patterns(df: pd.DataFrame) -> list[str]:
    """识别最近3根K线的经典形态"""
    if len(df) < 5:
        return []
    patterns = []
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values

    body   = np.abs(c - o)
    sh_up  = h - np.maximum(c, o)
    sh_dn  = np.minimum(c, o) - l

    i = -1  # 最新一根
    # 锤子线
    if body[i] > 0 and sh_dn[i] > 2 * body[i] and sh_up[i] < 0.5 * body[i] and c[i] > o[i]:
        patterns.append("锤子线(看多)")
    # 吊颈线
    if body[i] > 0 and sh_dn[i] > 2 * body[i] and sh_up[i] < 0.5 * body[i] and c[i] < o[i]:
        patterns.append("吊颈线(看空)")
    # 十字星
    if body[i] < (h[i] - l[i]) * 0.1 and (h[i] - l[i]) > 0:
        patterns.append("十字星(变盘)")
    # 早晨之星（需要至少3根）
    if (c[-3] < o[-3] and
            body[-2] < body[-3] * 0.3 and
            c[-1] > o[-1] and
            c[-1] > (o[-3] + c[-3]) / 2):
        patterns.append("早晨之星(看多)")
    # 黄昏之星
    if (c[-3] > o[-3] and
            body[-2] < body[-3] * 0.3 and
            c[-1] < o[-1] and
            c[-1] < (o[-3] + c[-3]) / 2):
        patterns.append("黄昏之星(看空)")
    # 红三兵（需至少5根防止越界）
    if len(df) >= 5:
        if all(c[-3+j] > o[-3+j] for j in range(3)) and c[-1] > c[-2] > c[-3]:
            patterns.append("红三兵(看多)")
        if all(c[-3+j] < o[-3+j] for j in range(3)) and c[-1] < c[-2] < c[-3]:
            patterns.append("三只乌鸦(看空)")

    return patterns


def trend_analysis(df: pd.DataFrame) -> dict:
    """多维度趋势分析，返回状态字典"""
    if df.empty or "ma5" not in df.columns:
        df = add_all_indicators(df)
    if df.empty:
        return {}

    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest
    c      = float(latest["close"])
    result = {}

    # 均线趋势
    ma5  = float(latest.get("ma5",  c) or c)
    ma10 = float(latest.get("ma10", c) or c)
    ma20 = float(latest.get("ma20", c) or c)
    if c > ma5 > ma10 > ma20:
        result["ma_trend"] = "上涨"
    elif c < ma5 < ma10 < ma20:
        result["ma_trend"] = "下跌"
    else:
        result["ma_trend"] = "震荡"

    # MACD
    dif = float(latest.get("macd_dif", 0) or 0)
    dea = float(latest.get("macd_dea", 0) or 0)
    bar = float(latest.get("macd_bar", 0) or 0)
    prev_dif = float(prev.get("macd_dif", 0) or 0)
    prev_dea = float(prev.get("macd_dea", 0) or 0)
    if prev_dif <= prev_dea and dif > dea:
        result["macd_state"] = "金叉向上"
    elif prev_dif >= prev_dea and dif < dea:
        result["macd_state"] = "死叉向下"
    elif dif > 0 and dea > 0 and bar > 0:
        result["macd_state"] = "多头强势"
    elif dif < 0 and dea < 0 and bar < 0:
        result["macd_state"] = "空头弱势"
    else:
        result["macd_state"] = "中性"

    # RSI
    rsi = float(latest.get("rsi12", 50) or 50)
    if rsi > 80:   result["rsi_state"] = "严重超买"
    elif rsi > 70: result["rsi_state"] = "超买"
    elif rsi < 20: result["rsi_state"] = "严重超卖"
    elif rsi < 30: result["rsi_state"] = "超卖"
    else:          result["rsi_state"] = "正常"

    # KDJ
    k = float(latest.get("kdj_k", 50) or 50)
    d = float(latest.get("kdj_d", 50) or 50)
    j = float(latest.get("kdj_j", 50) or 50)
    pk = float(prev.get("kdj_k", 50) or 50)
    pd_ = float(prev.get("kdj_d", 50) or 50)
    if pk < pd_ and k > d:    result["kdj_state"] = "金叉"
    elif pk > pd_ and k < d:  result["kdj_state"] = "死叉"
    elif j > 80:               result["kdj_state"] = "超买"
    elif j < 20:               result["kdj_state"] = "超卖"
    else:                      result["kdj_state"] = "中性"

    # BOLL
    boll_up = float(latest.get("boll_up", c*1.1) or c*1.1)
    boll_dn = float(latest.get("boll_dn", c*0.9) or c*0.9)
    boll_mid= float(latest.get("boll_mid", c)    or c)
    if c > boll_up:   result["boll_state"] = "突破上轨(超买)"
    elif c < boll_dn: result["boll_state"] = "突破下轨(超卖)"
    elif c > boll_mid:result["boll_state"] = "上方运行"
    else:             result["boll_state"] = "下方运行"

    # 综合评分 0~100
    score = 50.0
    if result["ma_trend"] == "上涨":   score += 15
    elif result["ma_trend"] == "下跌": score -= 15
    if "金叉" in result.get("macd_state", ""):  score += 10
    elif "死叉" in result.get("macd_state",""):  score -= 10
    if "超卖" in result.get("rsi_state", ""):   score += 10
    elif "超买" in result.get("rsi_state",""):  score -= 10
    if "金叉" in result.get("kdj_state",""):    score += 5
    elif "死叉" in result.get("kdj_state",""):  score -= 5
    result["score"] = int(max(0, min(100, score)))

    return result
