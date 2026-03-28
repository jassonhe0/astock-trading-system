# -*- coding: utf-8 -*-
"""
同花顺交易接口
基于 easytrader 连接本机运行的同花顺客户端，实现自动下单。

使用前提：
  1. pip install easytrader pywinauto
  2. 同花顺客户端已运行并已登录
  3. config.local.yaml 中填好 broker 配置

easytrader 文档: https://github.com/shidenggui/easytrader
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from utils.logger import log
from utils.config_loader import get

# ── easytrader 可用性检测 ──────────────────────────────────────
# 用 inspect 确认是真实模块而非 MagicMock
_HAS_EASYTRADER = False
try:
    import importlib.util as _ilu
    if _ilu.find_spec("easytrader") is not None:
        import easytrader as _et
        import inspect as _inspect
        if _inspect.ismodule(_et):
            _HAS_EASYTRADER = True
except Exception:
    pass


@dataclass
class OrderResult:
    success: bool
    order_id: str = ""
    symbol: str = ""
    action: str = ""
    price: float = 0.0
    quantity: int = 0
    message: str = ""
    raw: dict = field(default_factory=dict)


class THSBroker:
    """同花顺交易接口封装"""

    def __init__(self):
        self._client = None
        self._connected = False
        # easytrader 不可用时自动进入模拟模式
        self._mock = not _HAS_EASYTRADER
        if self._mock:
            log.warning("[交易] easytrader 不可用 → 自动进入模拟模式，所有操作仅打印日志")

    # ──────────────────── 连接 ────────────────────

    def connect(self) -> bool:
        if self._mock:
            self._connected = True
            log.info("[交易] 模拟模式已连接")
            return True
        try:
            broker_type = get("broker.type", "ths")
            exe_path    = get("broker.exe_path", "")
            account     = get("broker.account", "")
            password    = get("broker.password", "")
            if not all([exe_path, account, password]):
                log.error("[交易] 请在 config.local.yaml 填写 broker.exe_path / account / password")
                return False
            self._client = _et.use(broker_type)
            self._client.prepare(exe_path, user=account, password=password)
            self._connected = True
            log.info(f"[交易] 同花顺连接成功 | 账号: {str(account)[:4]}****")
            return True
        except Exception as e:
            log.error(f"[交易] 连接失败: {e}")
            return False

    def disconnect(self):
        self._connected = False
        self._client = None
        log.info("[交易] 已断开")

    def is_connected(self) -> bool:
        return self._connected

    # ──────────────────── 账户查询 ────────────────────

    def get_balance(self) -> dict:
        if self._mock:
            return {"可用资金": 100000.0, "总资产": 150000.0, "持仓市值": 50000.0}
        try:
            balance = self._client.balance
            # easytrader 返回 dict 或 list[dict]
            if isinstance(balance, list):
                balance = balance[0] if balance else {}
            log.info(f"[账户] 资金: {balance}")
            return balance
        except Exception as e:
            log.error(f"[账户] 资金查询失败: {e}")
            return {}

    def get_position(self) -> list[dict]:
        if self._mock:
            return [
                {"证券代码": "000001", "证券名称": "平安银行",
                 "持仓数量": 1000, "可用数量": 1000,
                 "成本价": 10.5, "当前价": 11.2, "盈亏": 700.0}
            ]
        try:
            pos = self._client.position
            if not isinstance(pos, list):
                pos = [pos] if pos else []
            return pos
        except Exception as e:
            log.error(f"[账户] 持仓查询失败: {e}")
            return []

    def get_today_orders(self) -> list[dict]:
        if self._mock:
            return []
        try:
            orders = self._client.today_entrusts
            return orders if isinstance(orders, list) else []
        except Exception as e:
            log.error(f"[账户] 委托查询失败: {e}")
            return []

    def get_today_trades(self) -> list[dict]:
        if self._mock:
            return []
        try:
            trades = self._client.today_trades
            return trades if isinstance(trades, list) else []
        except Exception as e:
            log.error(f"[账户] 成交查询失败: {e}")
            return []

    # ──────────────────── 交易操作 ────────────────────

    def buy(
        self,
        symbol: str,
        price: float,
        amount: Optional[int] = None,
        percent: Optional[float] = None,
    ) -> OrderResult:
        """
        买入
        amount: 明确股数（优先）
        percent: 按可用资金比例，如 0.1 表示用10%资金
        """
        if not self._connected:
            return OrderResult(False, message="未连接，请先调用 connect()")

        # 按比例计算股数
        if amount is None and percent is not None:
            balance = self.get_balance()
            available = float(balance.get("可用资金", 0) or 0)
            if available <= 0 or price <= 0:
                return OrderResult(False, message="资金或价格为0，无法计算股数")
            amount = int(available * percent / price / 100) * 100

        if not amount or amount < 100:
            return OrderResult(False, message=f"买入数量不足100股 (amount={amount})")

        log.info(f"[下单] 买入 {symbol} × {amount} @ {price:.3f}")

        if self._mock:
            log.warning(f"[模拟] 买入 {symbol} × {amount} @ {price:.3f}（未实际执行）")
            return OrderResult(True, symbol=symbol, action="buy",
                               price=price, quantity=amount,
                               order_id="MOCK_BUY", message="模拟买入成功")
        try:
            result = self._client.buy(security=symbol, price=price, amount=amount)
            oid = str(result.get("委托编号", "") if isinstance(result, dict) else "")
            log.info(f"[下单] 买入委托成功: {oid}")
            return OrderResult(True, symbol=symbol, action="buy",
                               price=price, quantity=amount,
                               order_id=oid, message="买入委托成功",
                               raw=result if isinstance(result, dict) else {})
        except Exception as e:
            log.error(f"[下单] 买入失败 {symbol}: {e}")
            return OrderResult(False, symbol=symbol, message=str(e))

    def sell(
        self,
        symbol: str,
        price: float,
        amount: Optional[int] = None,
    ) -> OrderResult:
        """
        卖出
        amount=None 时自动查可用持仓全部卖出
        """
        if not self._connected:
            return OrderResult(False, message="未连接")

        if amount is None:
            positions = self.get_position()
            for p in positions:
                if not isinstance(p, dict):
                    continue
                code = str(p.get("证券代码", "")).zfill(6)
                if code == symbol.zfill(6):
                    amount = int(p.get("可用数量", 0) or 0)
                    break
            if not amount or amount < 100:
                return OrderResult(False, symbol=symbol,
                                   message=f"无可用持仓或数量不足 (amount={amount})")

        log.info(f"[下单] 卖出 {symbol} × {amount} @ {price:.3f}")

        if self._mock:
            log.warning(f"[模拟] 卖出 {symbol} × {amount} @ {price:.3f}（未实际执行）")
            return OrderResult(True, symbol=symbol, action="sell",
                               price=price, quantity=amount,
                               order_id="MOCK_SELL", message="模拟卖出成功")
        try:
            result = self._client.sell(security=symbol, price=price, amount=amount)
            oid = str(result.get("委托编号", "") if isinstance(result, dict) else "")
            log.info(f"[下单] 卖出委托成功: {oid}")
            return OrderResult(True, symbol=symbol, action="sell",
                               price=price, quantity=amount,
                               order_id=oid, message="卖出委托成功",
                               raw=result if isinstance(result, dict) else {})
        except Exception as e:
            log.error(f"[下单] 卖出失败 {symbol}: {e}")
            return OrderResult(False, symbol=symbol, message=str(e))

    def cancel_order(self, order_id: str) -> bool:
        if self._mock:
            log.warning(f"[模拟] 撤单 {order_id}")
            return True
        try:
            self._client.cancel_entrust(order_id)
            log.info(f"[撤单] 成功: {order_id}")
            return True
        except Exception as e:
            log.error(f"[撤单] 失败: {e}")
            return False

    def cancel_all_orders(self) -> int:
        orders = self.get_today_orders()
        cancelled = 0
        for order in orders:
            if not isinstance(order, dict):
                continue
            status = order.get("委托状态", "")
            if "已报" in str(status) or "待报" in str(status):
                oid = str(order.get("委托编号", ""))
                if self.cancel_order(oid):
                    cancelled += 1
                time.sleep(0.3)
        log.info(f"[撤单] 共撤销 {cancelled} 笔")
        return cancelled


# ──────────────────── 风控管理器 ────────────────────

class RiskManager:
    def __init__(self, broker: THSBroker):
        self.broker          = broker
        self.stop_loss       = float(get("risk.stop_loss_ratio", 0.05))
        self.take_profit     = float(get("risk.take_profit_ratio", 0.10))
        self.max_position    = float(get("risk.max_position_ratio", 0.20))
        self.max_total       = float(get("risk.max_total_ratio", 0.80))
        self.max_count       = int(get("risk.max_holding_count", 10))

    def check_buy(self, symbol: str, price: float, amount: int) -> tuple[bool, str]:
        balance   = self.broker.get_balance()
        positions = self.broker.get_position()
        total     = float(balance.get("总资产", 0) or 0)
        available = float(balance.get("可用资金", 0) or 0)

        if total <= 0:
            return False, "无法获取账户资产信息"
        if len(positions) >= self.max_count:
            return False, f"持仓股数已达上限 {self.max_count}"

        buy_amount = price * amount
        if buy_amount / total > self.max_position:
            return False, f"单笔仓位 {buy_amount/total:.1%} 超限 {self.max_position:.0%}"

        mktval = float(balance.get("持仓市值", 0) or 0)
        if (mktval + buy_amount) / total > self.max_total:
            return False, f"总仓位超限 {self.max_total:.0%}"

        if buy_amount > available:
            return False, f"可用资金不足 (需 {buy_amount:.0f} 有 {available:.0f})"

        return True, "通过"

    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        for p in self.broker.get_position():
            if not isinstance(p, dict):
                continue
            if str(p.get("证券代码", "")).zfill(6) == symbol.zfill(6):
                cost = float(p.get("成本价", current_price) or current_price)
                if cost > 0 and (current_price - cost) / cost <= -self.stop_loss:
                    log.warning(f"[风控] {symbol} 触发止损: {(current_price-cost)/cost:.2%}")
                    return True
        return False

    def check_take_profit(self, symbol: str, current_price: float) -> bool:
        for p in self.broker.get_position():
            if not isinstance(p, dict):
                continue
            if str(p.get("证券代码", "")).zfill(6) == symbol.zfill(6):
                cost = float(p.get("成本价", current_price) or current_price)
                if cost > 0 and (current_price - cost) / cost >= self.take_profit:
                    log.info(f"[风控] {symbol} 触发止盈: {(current_price-cost)/cost:.2%}")
                    return True
        return False
