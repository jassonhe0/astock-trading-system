# -*- coding: utf-8 -*-
"""
数据获取模块
- 实时行情（AKShare）
- 历史K线（AKShare / Tushare）
- 财务数据
- 本地缓存
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd

from utils.logger import log
from utils.config_loader import get

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# 实时行情
# ─────────────────────────────────────────────

def get_realtime_quote(symbol: str) -> dict:
    """
    获取单只股票实时行情
    symbol: '000001' (不含市场前缀)
    返回: {symbol, name, price, open, high, low, volume, amount,
           change, change_pct, bid1..bid5, ask1..ask5, ...}
    """
    try:
        df = ak.stock_bid_ask_em(symbol=symbol)
        result = {"symbol": symbol, "ts": datetime.now().isoformat()}
        for _, row in df.iterrows():
            item = row.get("item", "")
            val = row.get("value", None)
            key_map = {
                "最新": "price", "今开": "open", "最高": "high", "最低": "low",
                "昨收": "prev_close", "成交量": "volume", "成交额": "amount",
                "涨跌幅": "change_pct", "涨跌额": "change",
                "买一价": "bid1", "买二价": "bid2", "买三价": "bid3",
                "卖一价": "ask1", "卖二价": "ask2", "卖三价": "ask3",
                "买一量": "bid1_vol", "卖一量": "ask1_vol",
            }
            if item in key_map:
                try:
                    result[key_map[item]] = float(val) if val not in (None, "-", "") else None
                except (ValueError, TypeError):
                    result[key_map[item]] = val
        return result
    except Exception as e:
        log.warning(f"[行情] {symbol} 实时数据获取失败: {e}")
        return {"symbol": symbol, "error": str(e)}


def get_realtime_quotes_batch(symbols: list[str]) -> pd.DataFrame:
    """批量获取实时行情（东方财富）"""
    try:
        df = ak.stock_zh_a_spot_em()
        df = df.rename(columns={
            "代码": "symbol", "名称": "name",
            "最新价": "price", "涨跌幅": "change_pct", "涨跌额": "change",
            "成交量": "volume", "成交额": "amount",
            "今开": "open", "最高": "high", "最低": "low", "昨收": "prev_close",
            "市盈率-动态": "pe", "市净率": "pb",
        })
        if symbols:
            df = df[df["symbol"].isin(symbols)]
        return df.reset_index(drop=True)
    except Exception as e:
        log.error(f"[行情] 批量行情获取失败: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# 历史K线
# ─────────────────────────────────────────────

def get_kline(
    symbol: str,
    period: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust: str = "qfq",
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    获取历史K线数据
    period: daily / weekly / monthly / 60 / 30 / 15 / 5 / 1
    adjust: qfq(前复权) / hfq(后复权) / '' (不复权)
    返回列: date, open, high, low, close, volume, amount, change_pct
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    cache_key = f"{symbol}_{period}_{adjust}_{start_date}_{end_date}"
    cache_file = CACHE_DIR / f"{cache_key}.parquet"

    # 检查缓存（当天日内数据不缓存）
    if use_cache and cache_file.exists():
        mtime = cache_file.stat().st_mtime
        age = time.time() - mtime
        # 日线及以上：缓存6小时；分钟线：缓存30分钟
        max_age = 21600 if period in ("daily", "weekly", "monthly") else 1800
        if age < max_age:
            log.debug(f"[缓存] 使用缓存 {cache_key}")
            return pd.read_parquet(cache_file)

    try:
        period_map = {
            "daily": "daily", "weekly": "weekly", "monthly": "monthly",
            "60": "60", "30": "30", "15": "15", "5": "5", "1": "1",
        }
        ak_period = period_map.get(period, "daily")

        if period in ("daily", "weekly", "monthly"):
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=ak_period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            df = df.rename(columns={
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low",
                "成交量": "volume", "成交额": "amount",
                "涨跌幅": "change_pct", "涨跌额": "change",
                "换手率": "turnover",
            })
        else:
            # 分钟线
            df = ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                period=ak_period,
                start_date=start_date.replace("-", "")[:8] + " 09:30:00",
                end_date=end_date.replace("-", "")[:8] + " 15:00:00",
                adjust=adjust,
            )
            df = df.rename(columns={
                "时间": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low",
                "成交量": "volume", "成交额": "amount",
                "涨跌幅": "change_pct",
            })

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        # 保存缓存
        if use_cache and len(df) > 0:
            df.to_parquet(cache_file, index=False)

        log.info(f"[行情] {symbol} {period} {len(df)}条数据")
        return df

    except Exception as e:
        log.error(f"[行情] {symbol} K线数据获取失败: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# 股票列表 & 搜索
# ─────────────────────────────────────────────

def get_stock_list() -> pd.DataFrame:
    """获取A股全量股票列表"""
    cache_file = CACHE_DIR / "stock_list.parquet"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 86400:  # 缓存1天
            return pd.read_parquet(cache_file)
    try:
        df = ak.stock_info_a_code_name()
        df.columns = ["symbol", "name"]
        df.to_parquet(cache_file, index=False)
        return df
    except Exception as e:
        log.error(f"[股票列表] 获取失败: {e}")
        return pd.DataFrame(columns=["symbol", "name"])


def search_stock(keyword: str) -> pd.DataFrame:
    """按代码或名称搜索股票"""
    df = get_stock_list()
    if df.empty:
        return df
    mask = df["symbol"].str.contains(keyword) | df["name"].str.contains(keyword)
    return df[mask].reset_index(drop=True)


# ─────────────────────────────────────────────
# 财务 & 资金流
# ─────────────────────────────────────────────

def get_money_flow(symbol: str) -> pd.DataFrame:
    """获取个股资金流向"""
    try:
        df = ak.stock_individual_fund_flow(stock=symbol, market="sh" if symbol.startswith("6") else "sz")
        return df
    except Exception as e:
        log.warning(f"[资金流] {symbol} 获取失败: {e}")
        return pd.DataFrame()


def get_market_sentiment() -> dict:
    """获取市场情绪指标（北向资金、涨跌家数）"""
    result = {}
    try:
        # 涨跌家数
        df = ak.stock_market_activity_legu()
        result["market_activity"] = df.to_dict("records")
    except Exception:
        pass
    try:
        # 北向资金
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if not df.empty:
            latest = df.iloc[-1]
            result["north_flow"] = {
                "date": str(latest.get("日期", "")),
                "net_flow": float(latest.get("当日净流入", 0) or 0),
            }
    except Exception:
        pass
    return result


# ─────────────────────────────────────────────
# 指数数据
# ─────────────────────────────────────────────

def get_index_kline(
    symbol: str = "sh000001",
    period: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """获取指数历史数据"""
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    try:
        df = ak.index_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )
        df = df.rename(columns={
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low",
            "成交量": "volume", "成交额": "amount",
        })
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        log.error(f"[指数] {symbol} 获取失败: {e}")
        return pd.DataFrame()
