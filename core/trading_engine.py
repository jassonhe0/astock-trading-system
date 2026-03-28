# -*- coding: utf-8 -*-
"""
实时交易调度器
交易时段内定时扫描股票池 → 生成信号 → 可选自动下单
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from core.data_fetcher import get_kline
from core.indicators import add_all_indicators
from strategies.base import SignalType
from strategies.builtin import get_strategy
from broker.ths_broker import THSBroker, RiskManager
from utils.logger import log
from utils.config_loader import get


def _is_trading_time() -> bool:
    """是否在A股交易时间内"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    from datetime import time as dtime
    t = now.time()
    return dtime(9, 30) <= t <= dtime(11, 30) or dtime(13, 0) <= t <= dtime(15, 0)


def _is_pre_market() -> bool:
    """是否在集合竞价时间 09:15-09:25"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    from datetime import time as dtime
    t = now.time()
    return dtime(9, 15) <= t <= dtime(9, 25)


class TradingEngine:
    """实时交易引擎"""

    def __init__(
        self,
        strategy_name: str = "multi_factor",
        strategy_params: Optional[dict] = None,
        live_trading: bool = False,
    ):
        self.strategy      = get_strategy(strategy_name, strategy_params)
        self.live_trading  = live_trading or get("strategy.live_trading", False)
        self.broker        = THSBroker()
        self.risk          = RiskManager(self.broker)
        self.watchlist: list[str] = []
        self._running      = False
        self._scheduler    = None
        self._signal_history: list[dict] = []

        if self.live_trading:
            log.warning("⚡ 实盘交易模式已启用！")
        else:
            log.info("📋 仅信号模式（不执行实际交易）")

    def add_watch(self, *symbols: str):
        for s in symbols:
            s = s.zfill(6)
            if s not in self.watchlist:
                self.watchlist.append(s)
                log.info(f"[监控] 添加 {s}")

    def remove_watch(self, symbol: str):
        symbol = symbol.zfill(6)
        if symbol in self.watchlist:
            self.watchlist.remove(symbol)

    def scan_once(self) -> list[dict]:
        """扫描所有监控股票，返回信号列表"""
        signals = []
        if not self.watchlist:
            log.warning("[扫描] 监控股票池为空")
            return signals

        log.info(f"[扫描] 开始扫描 {len(self.watchlist)} 只股票...")

        for symbol in self.watchlist:
            try:
                df = get_kline(symbol, "daily", use_cache=True)
                if df.empty or len(df) < 30:
                    continue
                df = add_all_indicators(df)
                sig = self.strategy.generate_signal(df, symbol)

                signal_dict = {
                    "symbol":     symbol,
                    "signal":     sig.signal.value,
                    "price":      sig.price,
                    "reason":     sig.reason,
                    "confidence": sig.confidence,
                    "stop_loss":  sig.stop_loss,
                    "take_profit":sig.take_profit,
                    "strategy":   sig.strategy_name,
                    "ts":         sig.timestamp,
                }

                log.info(f"  {sig}")
                signals.append(signal_dict)

                if self.live_trading and self.broker.is_connected():
                    self._execute_signal(sig)

                if self.broker.is_connected():
                    self._check_risk(symbol, sig.price)

                time.sleep(0.5)
            except Exception as e:
                log.error(f"[扫描] {symbol} 异常: {e}")

        self._signal_history.extend(signals)
        if len(self._signal_history) > 500:
            self._signal_history = self._signal_history[-500:]

        return signals

    def _execute_signal(self, sig):
        if sig.signal == SignalType.BUY:
            ok, msg = self.risk.check_buy(sig.symbol, sig.price, 100)
            if ok:
                result = self.broker.buy(sig.symbol, sig.price, percent=0.1)
                if result.success:
                    log.info(f"[交易] ✅ 买入: {sig.symbol} {result.order_id}")
                else:
                    log.warning(f"[交易] ❌ 买入失败: {sig.symbol} {result.message}")
            else:
                log.warning(f"[风控] 拒绝买入 {sig.symbol}: {msg}")
        elif sig.signal == SignalType.SELL:
            result = self.broker.sell(sig.symbol, sig.price)
            if result.success:
                log.info(f"[交易] ✅ 卖出: {sig.symbol} {result.order_id}")
            else:
                log.warning(f"[交易] ❌ 卖出失败: {sig.symbol} {result.message}")

    def _check_risk(self, symbol: str, price: float):
        if self.risk.check_stop_loss(symbol, price):
            if self.live_trading:
                log.warning(f"[止损] 执行 {symbol} @ {price}")
                self.broker.sell(symbol, price * 0.995)
        elif self.risk.check_take_profit(symbol, price):
            if self.live_trading:
                log.info(f"[止盈] 执行 {symbol} @ {price}")
                self.broker.sell(symbol, price * 0.995)

    def start(self, interval_minutes: int = 5):
        if self._running:
            return
        if self.live_trading and not self.broker.connect():
            log.error("[引擎] 同花顺连接失败，中止启动")
            return
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self._scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
            for h in ("9", "10", "11", "13", "14"):
                minute = f"30-59/{interval_minutes}" if h == "9" else f"*/{interval_minutes}"
                self._scheduler.add_job(
                    self._job_scan, "cron",
                    day_of_week="mon-fri", hour=h, minute=minute,
                )
            self._scheduler.add_job(
                self.broker.cancel_all_orders, "cron",
                day_of_week="mon-fri", hour="14", minute="57",
            )
            self._scheduler.start()
        except ImportError:
            log.warning("[引擎] apscheduler 未安装，使用简单循环模式")
            self._simple_loop(interval_minutes)
            return

        self._running = True
        log.info(f"[引擎] 启动 | 间隔{interval_minutes}分 | "
                 f"{'实盘' if self.live_trading else '仅信号'}")

    def _simple_loop(self, interval_minutes: int):
        """apscheduler 不可用时的备用循环"""
        self._running = True
        log.info(f"[引擎] 简单循环模式，间隔 {interval_minutes} 分钟")
        try:
            while self._running:
                if _is_trading_time():
                    self.scan_once()
                time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            self.stop()

    def _job_scan(self):
        if _is_trading_time():
            self.scan_once()

    def stop(self):
        self._running = False
        if self._scheduler:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                pass
        if self.live_trading:
            self.broker.disconnect()
        log.info("[引擎] 已停止")

    def get_recent_signals(self, n: int = 50) -> list[dict]:
        return self._signal_history[-n:]
