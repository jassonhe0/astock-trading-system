# -*- coding: utf-8 -*-
"""
回测引擎
- 基于历史K线数据模拟交易
- 计算胜率、收益率、最大回撤、夏普比率等绩效指标
- 输出逐日净值曲线和交易记录
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from core.data_fetcher import get_kline
from core.indicators import add_all_indicators
from strategies.base import BaseStrategy, SignalType, Signal
from utils.logger import log


@dataclass
class Trade:
    symbol: str
    action: str          # buy / sell
    price: float
    quantity: int
    date: str
    amount: float = 0.0
    fee: float = 0.0
    pnl: float = 0.0     # 仅sell时有值
    signal_reason: str = ""


@dataclass
class BacktestResult:
    symbol: str
    strategy_name: str
    start_date: str
    end_date: str

    # 绩效指标
    total_return: float = 0.0          # 总收益率
    annual_return: float = 0.0         # 年化收益率
    benchmark_return: float = 0.0      # 基准（沪深300）收益率
    alpha: float = 0.0                 # 超额收益
    sharpe_ratio: float = 0.0          # 夏普比率
    max_drawdown: float = 0.0          # 最大回撤
    win_rate: float = 0.0              # 胜率
    profit_factor: float = 0.0         # 盈亏比
    total_trades: int = 0
    win_trades: int = 0
    lose_trades: int = 0

    # 初始/终止资金
    initial_capital: float = 100000.0
    final_capital: float = 0.0

    # 详细数据
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)  # date, equity, drawdown

    def summary(self) -> str:
        return (
            f"\n{'='*50}\n"
            f"📊 回测结果: {self.symbol} | {self.strategy_name}\n"
            f"   时间范围: {self.start_date} ~ {self.end_date}\n"
            f"{'─'*50}\n"
            f"   初始资金: ¥{self.initial_capital:,.0f}\n"
            f"   最终资金: ¥{self.final_capital:,.0f}\n"
            f"   总收益率: {self.total_return:+.2%}\n"
            f"   年化收益: {self.annual_return:+.2%}\n"
            f"   基准收益: {self.benchmark_return:+.2%}\n"
            f"   超额收益: {self.alpha:+.2%}\n"
            f"{'─'*50}\n"
            f"   夏普比率: {self.sharpe_ratio:.3f}\n"
            f"   最大回撤: {self.max_drawdown:.2%}\n"
            f"   胜率:     {self.win_rate:.1%}\n"
            f"   盈亏比:   {self.profit_factor:.2f}\n"
            f"   交易次数: {self.total_trades} (盈:{self.win_trades} 亏:{self.lose_trades})\n"
            f"{'='*50}"
        )


# ─────────────────────────────────────────────
# 手续费模型
# ─────────────────────────────────────────────
COMMISSION_RATE = 0.0003   # 万3 印花税+佣金
MIN_COMMISSION = 5.0       # 最低5元
STAMP_DUTY = 0.001         # 卖出印花税千1（A股）
SLIPPAGE = 0.001           # 滑点0.1%


def calc_fee(price: float, qty: int, action: str) -> float:
    amount = price * qty
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    stamp = amount * STAMP_DUTY if action == "sell" else 0
    return round(commission + stamp, 2)


# ─────────────────────────────────────────────
# 回测引擎
# ─────────────────────────────────────────────
class Backtester:
    def __init__(
        self,
        strategy: BaseStrategy,
        initial_capital: float = 100000.0,
        position_ratio: float = 0.95,    # 每次买入使用资金比例
        lot_size: int = 100,             # A股最小交易单位100股
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.position_ratio = position_ratio
        self.lot_size = lot_size

    def run(
        self,
        symbol: str,
        start_date: str,
        end_date: Optional[str] = None,
        period: str = "daily",
    ) -> BacktestResult:
        log.info(f"[回测] 开始: {symbol} {self.strategy.name} {start_date}~{end_date or '今日'}")

        # 获取数据
        df = get_kline(symbol, period, start_date, end_date)
        if df.empty or len(df) < 30:
            log.warning(f"[回测] 数据不足: {symbol}")
            return BacktestResult(symbol, self.strategy.name, start_date, end_date or "")

        df = add_all_indicators(df)
        result = BacktestResult(
            symbol=symbol,
            strategy_name=self.strategy.name,
            start_date=str(df["date"].iloc[0].date()),
            end_date=str(df["date"].iloc[-1].date()),
            initial_capital=self.initial_capital,
        )

        cash = self.initial_capital
        position = 0          # 持仓股数
        buy_price = 0.0       # 持仓成本
        equity_list = []
        trades: list[Trade] = []
        win_pnl, lose_pnl = [], []

        # 逐根K线回测
        for i in range(30, len(df)):
            hist = df.iloc[:i].copy()
            row = df.iloc[i]
            date = str(row["date"].date())
            price = float(row["close"])

            signal: Signal = self.strategy.generate_signal(hist, symbol)

            # 执行买入
            if signal.is_buy() and position == 0:
                buy_price_slip = price * (1 + SLIPPAGE)
                max_qty = int((cash * self.position_ratio) / (buy_price_slip * self.lot_size)) * self.lot_size
                if max_qty >= self.lot_size:
                    fee = calc_fee(buy_price_slip, max_qty, "buy")
                    cost = buy_price_slip * max_qty + fee
                    if cost <= cash:
                        cash -= cost
                        position = max_qty
                        buy_price = buy_price_slip
                        trades.append(Trade(
                            symbol=symbol, action="buy",
                            price=buy_price_slip, quantity=max_qty,
                            date=date, amount=cost, fee=fee,
                            signal_reason=signal.reason
                        ))
                        log.debug(f"[回测] {date} 买入 {symbol} x{max_qty} @{buy_price_slip:.3f}")

            # 执行卖出
            elif signal.is_sell() and position > 0:
                sell_price_slip = price * (1 - SLIPPAGE)
                fee = calc_fee(sell_price_slip, position, "sell")
                proceeds = sell_price_slip * position - fee
                pnl = proceeds - buy_price * position
                cash += proceeds
                if pnl >= 0:
                    win_pnl.append(pnl)
                else:
                    lose_pnl.append(abs(pnl))
                trades.append(Trade(
                    symbol=symbol, action="sell",
                    price=sell_price_slip, quantity=position,
                    date=date, amount=proceeds, fee=fee, pnl=pnl,
                    signal_reason=signal.reason
                ))
                log.debug(f"[回测] {date} 卖出 {symbol} x{position} @{sell_price_slip:.3f} pnl={pnl:.2f}")
                position = 0
                buy_price = 0.0

            # 计算当日净值
            equity = cash + position * price
            equity_list.append({"date": date, "equity": equity, "price": price})

        # 强制平仓
        if position > 0:
            last_price = float(df["close"].iloc[-1])
            fee = calc_fee(last_price, position, "sell")
            proceeds = last_price * position - fee
            pnl = proceeds - buy_price * position
            cash += proceeds
            if pnl >= 0: win_pnl.append(pnl)
            else: lose_pnl.append(abs(pnl))
            trades.append(Trade(
                symbol=symbol, action="sell",
                price=last_price, quantity=position,
                date=result.end_date, amount=proceeds, fee=fee, pnl=pnl,
                signal_reason="回测结束强制平仓"
            ))

        result.final_capital = cash
        result.total_return = (cash - self.initial_capital) / self.initial_capital
        result.trades = trades
        result.total_trades = len([t for t in trades if t.action == "sell"])
        result.win_trades = len(win_pnl)
        result.lose_trades = len(lose_pnl)
        result.win_rate = result.win_trades / max(result.total_trades, 1)
        avg_win = np.mean(win_pnl) if win_pnl else 0
        avg_lose = np.mean(lose_pnl) if lose_pnl else 1
        result.profit_factor = avg_win / max(avg_lose, 0.01)

        # 净值曲线
        eq_df = pd.DataFrame(equity_list)
        if not eq_df.empty:
            eq_df["return"] = eq_df["equity"].pct_change().fillna(0)
            # 年化收益
            days = len(eq_df)
            result.annual_return = (1 + result.total_return) ** (252 / max(days, 1)) - 1
            # 最大回撤
            cummax = eq_df["equity"].cummax()
            dd = (eq_df["equity"] - cummax) / cummax
            result.max_drawdown = float(abs(dd.min()))
            eq_df["drawdown"] = dd
            # 夏普比率（无风险利率2.5%）
            rf_daily = 0.025 / 252
            excess = eq_df["return"] - rf_daily
            result.sharpe_ratio = (
                excess.mean() / excess.std() * np.sqrt(252)
                if excess.std() > 0 else 0
            )
            result.equity_curve = eq_df

        log.info(f"[回测] 完成: {result.total_return:+.2%} 夏普={result.sharpe_ratio:.2f} "
                 f"最大回撤={result.max_drawdown:.2%} 胜率={result.win_rate:.1%}")
        print(result.summary())
        return result

    def save_result(self, result: BacktestResult, output_dir: str = "backtest_results") -> str:
        """保存回测结果到CSV"""
        from pathlib import Path
        out = Path(output_dir)
        out.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{result.symbol}_{result.strategy_name}_{ts}"
        # 交易记录
        if result.trades:
            trades_df = pd.DataFrame([vars(t) for t in result.trades])
            trades_df.to_csv(out / f"{fname}_trades.csv", index=False, encoding="utf-8-sig")
        # 净值曲线
        if not result.equity_curve.empty:
            result.equity_curve.to_csv(out / f"{fname}_equity.csv", index=False, encoding="utf-8-sig")
        log.info(f"[回测] 结果已保存至 {out / fname}*.csv")
        return str(out / fname)
