# -*- coding: utf-8 -*-
"""策略基类 - 所有策略继承此类"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import pandas as pd


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    EMPTY = "empty"


@dataclass
class Signal:
    symbol: str
    signal: SignalType
    price: float
    reason: str
    confidence: float = 0.5       # 0~1 信号置信度
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    quantity: Optional[int] = None
    timestamp: str = ""
    strategy_name: str = ""

    def is_buy(self) -> bool:
        return self.signal == SignalType.BUY

    def is_sell(self) -> bool:
        return self.signal == SignalType.SELL

    def __str__(self):
        return (
            f"[{self.strategy_name}] {self.symbol} "
            f"{'🟢 买入' if self.is_buy() else '🔴 卖出' if self.is_sell() else '⚪ 持有'} "
            f"@ {self.price:.3f}  置信度:{self.confidence:.0%}  原因:{self.reason}"
        )


class BaseStrategy(ABC):
    """所有策略的基类"""

    name: str = "base"
    description: str = ""

    def __init__(self, params: dict | None = None):
        self.params = params or {}

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        """
        根据K线数据生成交易信号
        df: 已经包含技术指标的K线DataFrame
        symbol: 股票代码
        """
        ...

    def get_default_params(self) -> dict:
        return {}

    def _make_signal(
        self, symbol: str, signal: SignalType, price: float,
        reason: str, confidence: float = 0.5,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Signal:
        from datetime import datetime
        return Signal(
            symbol=symbol,
            signal=signal,
            price=price,
            reason=reason,
            confidence=confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.now().isoformat(),
            strategy_name=self.name,
        )
