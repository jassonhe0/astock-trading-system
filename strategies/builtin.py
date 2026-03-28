# -*- coding: utf-8 -*-
"""
内置量化策略集合
1. MACrossStrategy     - 均线金叉/死叉
2. MACDStrategy        - MACD金叉/死叉
3. RSIStrategy         - RSI超买超卖
4. BollingerStrategy   - 布林带突破
5. KDJStrategy         - KDJ金叉/死叉
6. MultiFactorStrategy - 多因子综合评分策略（推荐）
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from strategies.base import BaseStrategy, Signal, SignalType
from core.indicators import add_all_indicators
from utils.logger import log


# ─────────────────────────────────────────────
# 1. 均线金叉策略
# ─────────────────────────────────────────────
class MACrossStrategy(BaseStrategy):
    name = "ma_cross"
    description = "双均线金叉死叉策略"

    def get_default_params(self) -> dict:
        return {"fast_period": 5, "slow_period": 20}

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        p = {**self.get_default_params(), **self.params}
        fast, slow = p["fast_period"], p["slow_period"]
        col_fast = f"ma{fast}"
        col_slow = f"ma{slow}"

        if col_fast not in df.columns:
            df = add_all_indicators(df)

        if len(df) < slow + 2:
            return self._make_signal(symbol, SignalType.HOLD, df["close"].iloc[-1], "数据不足")

        curr_fast = df[col_fast].iloc[-1]
        curr_slow = df[col_slow].iloc[-1]
        prev_fast = df[col_fast].iloc[-2]
        prev_slow = df[col_slow].iloc[-2]
        price = df["close"].iloc[-1]

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            sl = price * (1 - 0.05)
            tp = price * (1 + 0.10)
            return self._make_signal(
                symbol, SignalType.BUY, price,
                f"MA{fast}上穿MA{slow}（金叉）", 0.7, sl, tp
            )
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            return self._make_signal(
                symbol, SignalType.SELL, price,
                f"MA{fast}下穿MA{slow}（死叉）", 0.7
            )
        return self._make_signal(symbol, SignalType.HOLD, price, "均线无交叉")


# ─────────────────────────────────────────────
# 2. MACD策略
# ─────────────────────────────────────────────
class MACDStrategy(BaseStrategy):
    name = "macd"
    description = "MACD金叉死叉 + 零轴判断"

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if "macd_dif" not in df.columns:
            df = add_all_indicators(df)
        if len(df) < 30:
            return self._make_signal(symbol, SignalType.HOLD, df["close"].iloc[-1], "数据不足")

        dif = df["macd_dif"]
        dea = df["macd_dea"]
        price = df["close"].iloc[-1]

        # 金叉：DIF上穿DEA
        if dif.iloc[-2] <= dea.iloc[-2] and dif.iloc[-1] > dea.iloc[-1]:
            above_zero = dif.iloc[-1] > 0
            conf = 0.75 if above_zero else 0.55
            reason = "MACD金叉（零轴上方）" if above_zero else "MACD金叉（零轴下方，需谨慎）"
            sl = price * 0.95
            tp = price * 1.12
            return self._make_signal(symbol, SignalType.BUY, price, reason, conf, sl, tp)

        # 死叉：DIF下穿DEA
        if dif.iloc[-2] >= dea.iloc[-2] and dif.iloc[-1] < dea.iloc[-1]:
            below_zero = dif.iloc[-1] < 0
            conf = 0.75 if below_zero else 0.55
            reason = "MACD死叉（零轴下方）" if below_zero else "MACD死叉（零轴上方）"
            return self._make_signal(symbol, SignalType.SELL, price, reason, conf)

        return self._make_signal(symbol, SignalType.HOLD, price, "MACD无信号")


# ─────────────────────────────────────────────
# 3. RSI策略
# ─────────────────────────────────────────────
class RSIStrategy(BaseStrategy):
    name = "rsi"
    description = "RSI超买超卖策略"

    def get_default_params(self) -> dict:
        return {"period": 14, "overbought": 70, "oversold": 30}

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        p = {**self.get_default_params(), **self.params}
        rsi_col = "rsi12"
        if rsi_col not in df.columns:
            df = add_all_indicators(df)
        price = df["close"].iloc[-1]
        rsi = df[rsi_col].iloc[-1]
        rsi_prev = df[rsi_col].iloc[-2] if len(df) > 1 else rsi

        if rsi_prev < p["oversold"] and rsi >= p["oversold"]:
            sl = price * 0.95
            tp = price * 1.08
            return self._make_signal(
                symbol, SignalType.BUY, price,
                f"RSI从超卖区反弹 ({rsi:.1f})", 0.65, sl, tp
            )
        if rsi_prev > p["overbought"] and rsi <= p["overbought"]:
            return self._make_signal(
                symbol, SignalType.SELL, price,
                f"RSI从超买区回落 ({rsi:.1f})", 0.65
            )
        return self._make_signal(symbol, SignalType.HOLD, price, f"RSI={rsi:.1f}")


# ─────────────────────────────────────────────
# 4. 布林带突破策略
# ─────────────────────────────────────────────
class BollingerStrategy(BaseStrategy):
    name = "bollinger"
    description = "布林带上下轨突破反转策略"

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if "boll_up" not in df.columns:
            df = add_all_indicators(df)
        price = df["close"].iloc[-1]
        c = df["close"]
        up = df["boll_up"]
        dn = df["boll_dn"]
        mid = df["boll_mid"]

        # 价格从下轨反弹（超卖回归）
        if c.iloc[-2] < dn.iloc[-2] and c.iloc[-1] > dn.iloc[-1]:
            sl = dn.iloc[-1] * 0.98
            tp = mid.iloc[-1]
            return self._make_signal(
                symbol, SignalType.BUY, price,
                f"价格反弹突破布林下轨 ({dn.iloc[-1]:.3f})", 0.68, sl, tp
            )
        # 价格从上轨回落
        if c.iloc[-2] > up.iloc[-2] and c.iloc[-1] < up.iloc[-1]:
            return self._make_signal(
                symbol, SignalType.SELL, price,
                f"价格回落布林上轨 ({up.iloc[-1]:.3f})", 0.65
            )
        return self._make_signal(symbol, SignalType.HOLD, price, "布林带无信号")


# ─────────────────────────────────────────────
# 5. KDJ策略
# ─────────────────────────────────────────────
class KDJStrategy(BaseStrategy):
    name = "kdj"
    description = "KDJ金叉死叉策略"

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if "kdj_k" not in df.columns:
            df = add_all_indicators(df)
        price = df["close"].iloc[-1]
        k = df["kdj_k"]
        d = df["kdj_d"]
        j = df["kdj_j"]

        if k.iloc[-2] < d.iloc[-2] and k.iloc[-1] > d.iloc[-1] and j.iloc[-1] < 80:
            oversold = j.iloc[-1] < 30
            conf = 0.72 if oversold else 0.58
            sl = price * 0.95
            tp = price * 1.08
            return self._make_signal(
                symbol, SignalType.BUY, price,
                f"KDJ金叉 J={j.iloc[-1]:.1f}{'（超卖区）' if oversold else ''}", conf, sl, tp
            )
        if k.iloc[-2] > d.iloc[-2] and k.iloc[-1] < d.iloc[-1] and j.iloc[-1] > 20:
            overbought = j.iloc[-1] > 80
            conf = 0.72 if overbought else 0.58
            return self._make_signal(
                symbol, SignalType.SELL, price,
                f"KDJ死叉 J={j.iloc[-1]:.1f}{'（超买区）' if overbought else ''}", conf
            )
        return self._make_signal(symbol, SignalType.HOLD, price, f"KDJ K={k.iloc[-1]:.1f}")


# ─────────────────────────────────────────────
# 6. 多因子综合策略（推荐）
# ─────────────────────────────────────────────
class MultiFactorStrategy(BaseStrategy):
    name = "multi_factor"
    description = "多因子综合评分策略（MA+MACD+RSI+BOLL+KDJ+量价）"

    def get_default_params(self) -> dict:
        return {
            "buy_threshold": 65,    # 综合分数 >= 此值产生买入信号
            "sell_threshold": 35,   # 综合分数 <= 此值产生卖出信号
        }

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        p = {**self.get_default_params(), **self.params}
        if "ma5" not in df.columns:
            df = add_all_indicators(df)
        if len(df) < 30:
            return self._make_signal(symbol, SignalType.HOLD, df["close"].iloc[-1], "数据不足")

        price = df["close"].iloc[-1]
        score = 50.0
        reasons = []

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # ── 均线因子 (20分) ─────────────────────
        ma_score = 0
        if price > latest.get("ma5", 0): ma_score += 4
        if price > latest.get("ma10", 0): ma_score += 4
        if price > latest.get("ma20", 0): ma_score += 4
        if latest.get("ma5", 0) > latest.get("ma20", 0): ma_score += 4
        if latest.get("ma10", 0) > latest.get("ma60", 0): ma_score += 4
        score += ma_score - 10
        if ma_score >= 16: reasons.append("均线多头排列")
        if ma_score <= 4: reasons.append("均线空头排列")

        # ── MACD因子 (20分) ─────────────────────
        macd_score = 0
        dif = latest.get("macd_dif", 0)
        dea = latest.get("macd_dea", 0)
        bar = latest.get("macd_bar", 0)
        if dif > 0: macd_score += 5
        if dea > 0: macd_score += 5
        if bar > 0: macd_score += 5
        if dif > dea: macd_score += 5
        if (prev.get("macd_dif", 0) <= prev.get("macd_dea", 0) and dif > dea):
            macd_score += 5
            reasons.append("MACD金叉")
        score += macd_score - 10

        # ── RSI因子 (15分) ──────────────────────
        rsi = latest.get("rsi12", 50)
        if 40 <= rsi <= 60:
            score += 0
        elif rsi < 30:
            score += 10
            reasons.append(f"RSI超卖({rsi:.0f})")
        elif rsi > 70:
            score -= 10
            reasons.append(f"RSI超买({rsi:.0f})")
        elif rsi > 50:
            score += 5

        # ── BOLL因子 (10分) ─────────────────────
        boll_up = latest.get("boll_up", price * 1.1)
        boll_dn = latest.get("boll_dn", price * 0.9)
        boll_mid = latest.get("boll_mid", price)
        if price < boll_dn:
            score += 8; reasons.append("布林下轨超卖")
        elif price > boll_up:
            score -= 8; reasons.append("布林上轨超买")
        elif price > boll_mid:
            score += 3

        # ── KDJ因子 (10分) ──────────────────────
        k = latest.get("kdj_k", 50)
        d = latest.get("kdj_d", 50)
        j = latest.get("kdj_j", 50)
        if (prev.get("kdj_k", 50) < prev.get("kdj_d", 50) and k > d):
            score += 8; reasons.append("KDJ金叉")
        elif (prev.get("kdj_k", 50) > prev.get("kdj_d", 50) and k < d):
            score -= 8; reasons.append("KDJ死叉")
        elif j < 20:
            score += 5; reasons.append("KDJ超卖")
        elif j > 80:
            score -= 5; reasons.append("KDJ超买")

        # ── 量价因子 (10分) ─────────────────────
        vol_ratio = latest.get("vol_ratio", 1.0)
        change_pct = df["close"].pct_change().iloc[-1] * 100
        if change_pct > 0 and vol_ratio > 1.5:
            score += 8; reasons.append(f"放量上涨({vol_ratio:.1f}x)")
        elif change_pct < 0 and vol_ratio > 2:
            score -= 8; reasons.append(f"放量下跌({vol_ratio:.1f}x)")
        elif change_pct > 0 and vol_ratio < 0.7:
            score -= 3; reasons.append("缩量上涨(需谨慎)")

        score = max(0, min(100, score))
        reason_str = " | ".join(reasons) if reasons else "无明显信号"
        conf = abs(score - 50) / 50

        log.debug(f"[多因子] {symbol} 评分={score:.0f} {reason_str}")

        if score >= p["buy_threshold"]:
            sl = price * 0.95
            tp = price * (1 + min(0.20, (score - 50) / 100))
            return self._make_signal(
                symbol, SignalType.BUY, price,
                f"综合评分{score:.0f} | {reason_str}", conf, sl, tp
            )
        elif score <= p["sell_threshold"]:
            return self._make_signal(
                symbol, SignalType.SELL, price,
                f"综合评分{score:.0f} | {reason_str}", conf
            )
        return self._make_signal(
            symbol, SignalType.HOLD, price,
            f"综合评分{score:.0f} | {reason_str}", conf
        )


# ─────────────────────────────────────────────
# 策略注册表
# ─────────────────────────────────────────────
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "ma_cross": MACrossStrategy,
    "macd": MACDStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "kdj": KDJStrategy,
    "multi_factor": MultiFactorStrategy,
}


def get_strategy(name: str, params: dict | None = None) -> BaseStrategy:
    cls = STRATEGY_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"未知策略: {name}，可用策略: {list(STRATEGY_REGISTRY.keys())}")
    return cls(params=params)
