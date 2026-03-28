# -*- coding: utf-8 -*-
"""
A股量化交易系统 - Streamlit Web控制台
启动: streamlit run ui/app.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ── 页面配置（必须最先调用）──
st.set_page_config(
    page_title="A股量化交易系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container{padding-top:1rem}
</style>
""", unsafe_allow_html=True)

# ── 延迟导入业务模块（避免启动时因依赖缺失崩溃）──
@st.cache_resource
def _load_modules():
    from core.data_fetcher import (
        get_kline, get_realtime_quotes_batch, get_realtime_quote,
        search_stock, get_index_kline,
    )
    from core.indicators import (
        add_all_indicators, trend_analysis,
        detect_candlestick_patterns, calc_support_resistance,
    )
    from core.backtester import Backtester
    from strategies.builtin import get_strategy, STRATEGY_REGISTRY
    from broker.ths_broker import THSBroker, RiskManager
    return {
        "get_kline": get_kline,
        "get_realtime_quotes_batch": get_realtime_quotes_batch,
        "get_realtime_quote": get_realtime_quote,
        "search_stock": search_stock,
        "get_index_kline": get_index_kline,
        "add_all_indicators": add_all_indicators,
        "trend_analysis": trend_analysis,
        "detect_candlestick_patterns": detect_candlestick_patterns,
        "calc_support_resistance": calc_support_resistance,
        "Backtester": Backtester,
        "get_strategy": get_strategy,
        "STRATEGY_REGISTRY": STRATEGY_REGISTRY,
        "THSBroker": THSBroker,
        "RiskManager": RiskManager,
    }

try:
    M = _load_modules()
except Exception as e:
    st.error(f"模块加载失败: {e}")
    st.info("请确认已安装依赖: pip install -r requirements.txt")
    st.stop()

# ── 侧边栏导航 ──
with st.sidebar:
    st.title("📈 A股量化系统")
    st.divider()
    page = st.radio(
        "导航",
        ["🏠 市场概览", "📊 个股分析", "🤖 策略信号", "🔁 回测引擎", "💼 交易账户", "⚙️ 系统配置"],
    )
    st.divider()
    st.caption("行情: AKShare（免费）")
    st.caption(f"时间: {datetime.now().strftime('%H:%M:%S')}")
    if st.button("🔄 刷新"):
        st.rerun()


# ════════════════════════════════════════════════════
# 工具函数（必须定义在所有页面代码之前）
# ════════════════════════════════════════════════════

def plot_candlestick(df: pd.DataFrame, symbol: str):
    """K线图 + 均线 + 成交量 + MACD"""
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=["K线 + 均线", "成交量", "MACD"],
    )
    # K线
    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#e53e3e",
        decreasing_line_color="#38a169",
        name="K线",
    ), row=1, col=1)
    # 均线
    ma_colors = {"ma5": "#FF6B35", "ma10": "#4ECDC4", "ma20": "#45B7D1", "ma60": "#96CEB4"}
    for col, color in ma_colors.items():
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df["date"], y=df[col], name=col.upper(),
                line=dict(color=color, width=1), opacity=0.85,
            ), row=1, col=1)
    # 布林带
    if "boll_up" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["boll_up"], name="BOLL上",
            line=dict(color="purple", width=1, dash="dot"), opacity=0.5,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["boll_dn"], name="BOLL下",
            line=dict(color="purple", width=1, dash="dot"), opacity=0.5,
            fill="tonexty", fillcolor="rgba(128,0,128,0.05)",
        ), row=1, col=1)
    # 成交量
    vol_colors = [
        "#e53e3e" if float(c) >= float(o) else "#38a169"
        for c, o in zip(df["close"], df["open"])
    ]
    fig.add_trace(go.Bar(
        x=df["date"], y=df["volume"], name="成交量",
        marker_color=vol_colors, opacity=0.7,
    ), row=2, col=1)
    if "vol_ma5" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["vol_ma5"], name="量MA5",
            line=dict(color="orange", width=1),
        ), row=2, col=1)
    # MACD
    if "macd_bar" in df.columns:
        macd_colors = ["#e53e3e" if float(v) > 0 else "#38a169" for v in df["macd_bar"]]
        fig.add_trace(go.Bar(
            x=df["date"], y=df["macd_bar"], name="MACD柱",
            marker_color=macd_colors, opacity=0.7,
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["macd_dif"], name="DIF",
            line=dict(color="#FF6B35", width=1.5),
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["macd_dea"], name="DEA",
            line=dict(color="#4ECDC4", width=1.5),
        ), row=3, col=1)

    fig.update_layout(
        height=700, showlegend=True,
        xaxis_rangeslider_visible=False,
        plot_bgcolor="white",
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════
# 页面: 市场概览
# ════════════════════════════════════════════════════
if page == "🏠 市场概览":
    st.title("🏠 市场概览")

    # 主要指数
    index_map = {
        "上证指数": "000001", "深证成指": "399001",
        "创业板指": "399006", "沪深300": "000300",
    }
    cols = st.columns(4)
    for i, (name, code) in enumerate(index_map.items()):
        try:
            df_idx = M["get_kline"](code, "daily",
                start_date=(datetime.now()-timedelta(days=10)).strftime("%Y%m%d"))
            if not df_idx.empty and len(df_idx) >= 2:
                price = float(df_idx["close"].iloc[-1])
                prev  = float(df_idx["close"].iloc[-2])
                chg   = (price - prev) / prev * 100
                cols[i].metric(name, f"{price:.2f}", f"{chg:+.2f}%")
            else:
                cols[i].metric(name, "加载中", "")
        except Exception:
            cols[i].metric(name, "连接中...", "")

    st.divider()

    # 全市场行情（先获取数据，再分列显示）
    st.subheader("📋 实时行情榜单")
    df_all = pd.DataFrame()
    with st.spinner("获取行情..."):
        try:
            df_all = M["get_realtime_quotes_batch"]([])
            if not df_all.empty and "change_pct" in df_all.columns:
                df_all["change_pct"] = pd.to_numeric(df_all["change_pct"], errors="coerce")
        except Exception as e:
            st.warning(f"行情数据获取失败: {e}")

    col1, col2 = st.columns(2)
    with col1:
        st.write("**涨幅榜 Top 10**")
        if not df_all.empty:
            disp_cols = [c for c in ["symbol","name","price","change_pct","volume"] if c in df_all.columns]
            top10 = df_all.nlargest(10, "change_pct")[disp_cols]
            st.dataframe(top10, use_container_width=True, hide_index=True)
        else:
            st.info("行情数据加载中...")

    with col2:
        st.write("**跌幅榜 Top 10**")
        if not df_all.empty:
            disp_cols = [c for c in ["symbol","name","price","change_pct","volume"] if c in df_all.columns]
            bot10 = df_all.nsmallest(10, "change_pct")[disp_cols]
            st.dataframe(bot10, use_container_width=True, hide_index=True)
        else:
            st.info("行情数据加载中...")

    # 沪深300走势
    st.subheader("📈 沪深300近90日走势")
    try:
        hs300 = M["get_kline"]("000300", "daily",
            start_date=(datetime.now()-timedelta(days=90)).strftime("%Y%m%d"))
        if not hs300.empty:
            fig = go.Figure(go.Scatter(
                x=hs300["date"], y=hs300["close"],
                mode="lines", name="沪深300",
                line=dict(color="#e53e3e", width=2),
                fill="tozeroy", fillcolor="rgba(229,62,62,0.05)",
            ))
            fig.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0),
                              plot_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.info("指数走势加载中...")


# ════════════════════════════════════════════════════
# 页面: 个股分析
# ════════════════════════════════════════════════════
elif page == "📊 个股分析":
    st.title("📊 个股分析")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        symbol_input = st.text_input("股票代码", "000001", placeholder="如 000001 / 600519")
    with c2:
        period = st.selectbox("K线周期", ["daily","weekly","60","30","15","5"], index=0)
    with c3:
        days = st.selectbox("历史天数", [90, 180, 365, 730], index=1)

    symbol = symbol_input.strip().zfill(6)
    start  = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    if st.button("🔍 分析", type="primary"):
        with st.spinner("获取数据并计算指标..."):
            try:
                df = M["get_kline"](symbol, period, start_date=start)
            except Exception as e:
                st.error(f"数据获取失败: {e}")
                st.stop()

        if df is None or df.empty:
            st.error("未获取到数据，请检查股票代码或网络连接")
        else:
            df = M["add_all_indicators"](df)

            # 实时价格
            curr_price = float(df["close"].iloc[-1])
            try:
                quote = M["get_realtime_quote"](symbol)
                if quote.get("price"):
                    curr_price = float(quote["price"])
            except Exception:
                quote = {}

            # 顶部指标卡
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("最新价", f"{curr_price:.3f}")
            chg = quote.get("change_pct", df["change_pct"].iloc[-1] if "change_pct" in df.columns else 0)
            c2.metric("涨跌幅", f"{float(chg or 0):+.2f}%")
            amt = quote.get("amount", 0)
            c3.metric("成交额", f"{float(amt)/1e8:.2f}亿" if amt else "N/A")
            trend = M["trend_analysis"](df)
            c4.metric("均线趋势", trend.get("ma_trend", "N/A"))
            c5.metric("综合评分", f"{trend.get('score', 50)}/100")

            # K线图
            st.subheader(f"📊 {symbol} K线图")
            plot_candlestick(df, symbol)

            # 技术分析 + 形态
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📋 技术指标状态")
                state_map = {
                    "均线趋势": trend.get("ma_trend"),
                    "MACD":    trend.get("macd_state"),
                    "RSI":     trend.get("rsi_state"),
                    "KDJ":     trend.get("kdj_state"),
                    "BOLL":    trend.get("boll_state"),
                }
                for label, val in state_map.items():
                    v = str(val or "")
                    icon = "🟢" if any(k in v for k in ["多","金叉","超卖"]) else \
                           "🔴" if any(k in v for k in ["空","死叉","超买"]) else "⚪"
                    st.write(f"{icon} **{label}**: {v}")

            with col2:
                st.subheader("🕯️ K线形态")
                patterns = M["detect_candlestick_patterns"](df)
                if patterns:
                    for p in patterns:
                        icon = "🟢" if "看多" in p else "🔴" if "看空" in p else "⚪"
                        st.write(f"{icon} {p}")
                else:
                    st.write("⚪ 暂无明显形态")

                st.subheader("🎯 支撑压力位")
                sr = M["calc_support_resistance"](df)
                if sr:
                    for k, v in [("压力位2","resistance2"),("压力位1","resistance1"),
                                  ("轴心点","pivot"),("支撑位1","support1"),("支撑位2","support2")]:
                        icon = "🔴" if "压力" in k else "🟢" if "支撑" in k else "⚪"
                        st.write(f"{icon} {k}: `{sr.get(v,0):.3f}`")

            # 最新指标数值
            st.subheader("📈 指标数值（最新一根K线）")
            latest = df.iloc[-1]
            want = ["ma5","ma10","ma20","ma60","macd_dif","macd_dea","macd_bar",
                    "rsi6","rsi12","rsi24","kdj_k","kdj_d","kdj_j",
                    "boll_up","boll_mid","boll_dn","cci","atr14","vol_ratio"]
            ind_data = {}
            for col in want:
                if col in latest.index and pd.notna(latest[col]):
                    ind_data[col] = round(float(latest[col]), 3)
            st.dataframe(pd.DataFrame([ind_data]), use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════
# 页面: 策略信号
# ════════════════════════════════════════════════════
elif page == "🤖 策略信号":
    st.title("🤖 策略信号扫描")

    REGISTRY = M["STRATEGY_REGISTRY"]

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        symbols_input = st.text_area(
            "监控股票池（每行一个代码）",
            "000001\n600519\n000858\n002415\n300750\n601318\n000333\n600036",
            height=160,
        )
    with c2:
        strategy_name = st.selectbox("策略", list(REGISTRY.keys()), index=list(REGISTRY.keys()).index("multi_factor"))
        buy_thr  = st.slider("买入阈值（多因子）", 50, 90, 65)
        sell_thr = st.slider("卖出阈值（多因子）", 10, 50, 35)
    with c3:
        st.write("**策略说明**")
        st.info(REGISTRY[strategy_name].description)

    if st.button("🔍 立即扫描", type="primary"):
        symbols = [s.strip().zfill(6) for s in symbols_input.splitlines() if s.strip()]
        if not symbols:
            st.warning("请输入至少一个股票代码")
        else:
            strategy = M["get_strategy"](strategy_name, {
                "buy_threshold": buy_thr, "sell_threshold": sell_thr,
            })
            results = []
            bar = st.progress(0, text="扫描中...")
            for i, sym in enumerate(symbols):
                bar.progress((i+1)/len(symbols), text=f"分析 {sym} ...")
                try:
                    df = M["get_kline"](sym, "daily")
                    if df is None or df.empty:
                        results.append({"代码":sym,"信号":"❌ 无数据","价格":"-","置信度":"-","止损":"-","止盈":"-","原因":"数据为空"})
                        continue
                    df = M["add_all_indicators"](df)
                    sig = strategy.generate_signal(df, sym)
                    signal_label = {"buy":"🟢 买入","sell":"🔴 卖出","hold":"⚪ 持有"}.get(sig.signal.value,"-")
                    results.append({
                        "代码": sym,
                        "信号": signal_label,
                        "价格": f"{sig.price:.3f}",
                        "置信度": f"{sig.confidence:.0%}",
                        "止损": f"{sig.stop_loss:.3f}" if sig.stop_loss else "-",
                        "止盈": f"{sig.take_profit:.3f}" if sig.take_profit else "-",
                        "原因": sig.reason,
                    })
                except Exception as e:
                    results.append({"代码":sym,"信号":"❌ 错误","价格":"-","置信度":"-","止损":"-","止盈":"-","原因":str(e)})
            bar.empty()

            df_res = pd.DataFrame(results)
            buy_mask  = df_res["信号"].str.contains("买入", na=False)
            sell_mask = df_res["信号"].str.contains("卖出", na=False)
            df_res = pd.concat([df_res[buy_mask], df_res[sell_mask], df_res[~buy_mask & ~sell_mask]])
            st.dataframe(df_res, use_container_width=True, hide_index=True)
            st.success(f"✅ 扫描完成 | 🟢 买入 {buy_mask.sum()} 只 | 🔴 卖出 {sell_mask.sum()} 只 | ⚪ 持有 {(~buy_mask&~sell_mask).sum()} 只")


# ════════════════════════════════════════════════════
# 页面: 回测引擎
# ════════════════════════════════════════════════════
elif page == "🔁 回测引擎":
    st.title("🔁 策略回测")

    REGISTRY = M["STRATEGY_REGISTRY"]

    c1, c2, c3 = st.columns(3)
    with c1:
        bt_symbol   = st.text_input("股票代码", "000001")
        bt_strategy = st.selectbox("策略", list(REGISTRY.keys()),
                                   index=list(REGISTRY.keys()).index("multi_factor"))
    with c2:
        bt_start = st.date_input("开始日期", value=datetime.now()-timedelta(days=365))
        bt_end   = st.date_input("结束日期",  value=datetime.now())
    with c3:
        bt_capital = st.number_input("初始资金（元）", value=100000, step=10000, min_value=10000)
        bt_period  = st.selectbox("K线周期", ["daily","weekly"], index=0)
        buy_thr2  = st.slider("买入阈值", 50, 90, 65, key="bt_buy")
        sell_thr2 = st.slider("卖出阈值", 10, 50, 35, key="bt_sell")

    if st.button("🚀 开始回测", type="primary"):
        with st.spinner("回测计算中，请稍候..."):
            try:
                strategy = M["get_strategy"](bt_strategy, {
                    "buy_threshold": buy_thr2, "sell_threshold": sell_thr2,
                })
                bt = M["Backtester"](strategy, initial_capital=float(bt_capital))
                result = bt.run(
                    bt_symbol.strip().zfill(6),
                    str(bt_start).replace("-",""),
                    str(bt_end).replace("-",""),
                    bt_period,
                )
            except Exception as e:
                st.error(f"回测失败: {e}")
                st.stop()

        if result.total_trades == 0 and result.equity_curve.empty:
            st.warning("交易次数为0，请调整策略参数或延长时间范围")
        else:
            # 绩效卡
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("总收益率",  f"{result.total_return:+.2%}")
            r2.metric("年化收益",  f"{result.annual_return:+.2%}")
            r3.metric("最大回撤",  f"{result.max_drawdown:.2%}")
            r4.metric("夏普比率",  f"{result.sharpe_ratio:.3f}")

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("胜率",     f"{result.win_rate:.1%}")
            r2.metric("盈亏比",   f"{result.profit_factor:.2f}")
            r3.metric("交易次数", result.total_trades)
            r4.metric("最终资金", f"¥{result.final_capital:,.0f}")

            # 净值曲线
            if not result.equity_curve.empty:
                st.subheader("📈 净值曲线 & 回撤")
                eq = result.equity_curve
                fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                     row_heights=[0.7, 0.3],
                                     subplot_titles=["净值", "回撤(%)"])
                fig2.add_trace(go.Scatter(
                    x=eq["date"], y=eq["equity"],
                    name="策略净值", line=dict(color="#e53e3e", width=2),
                ), row=1, col=1)
                fig2.add_trace(go.Scatter(
                    x=eq["date"], y=[float(bt_capital)]*len(eq),
                    name="初始资金", line=dict(color="gray", dash="dash", width=1),
                ), row=1, col=1)
                fig2.add_trace(go.Scatter(
                    x=eq["date"], y=(eq["drawdown"]*100).round(2),
                    name="回撤%", fill="tozeroy",
                    line=dict(color="#38a169", width=1),
                ), row=2, col=1)
                fig2.update_layout(height=480, margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig2, use_container_width=True)

            # 交易记录
            if result.trades:
                st.subheader("📋 交易明细")
                trades_list = []
                for t in result.trades:
                    d = vars(t).copy()
                    if d.get("pnl", 0) != 0:
                        d["pnl"] = f"{'🟢' if d['pnl']>0 else '🔴'} {d['pnl']:+.2f}"
                    trades_list.append(d)
                st.dataframe(pd.DataFrame(trades_list), use_container_width=True, hide_index=True)

                if st.button("💾 保存回测结果"):
                    try:
                        path = bt.save_result(result)
                        st.success(f"已保存: {path}")
                    except Exception as e:
                        st.error(f"保存失败: {e}")


# ════════════════════════════════════════════════════
# 页面: 交易账户
# ════════════════════════════════════════════════════
elif page == "💼 交易账户":
    st.title("💼 交易账户（同花顺）")

    THSBroker   = M["THSBroker"]
    RiskManager = M["RiskManager"]

    if "broker" not in st.session_state:
        st.session_state.broker = THSBroker()

    broker = st.session_state.broker

    # 连接控制栏
    col_btn, col_status = st.columns([2, 3])
    with col_btn:
        if st.button("🔌 连接同花顺", type="primary"):
            with st.spinner("连接中..."):
                ok = broker.connect()
            if ok:
                st.success("✅ 连接成功")
            else:
                st.error("❌ 连接失败，请检查 config.local.yaml 中的账号配置")
        if st.button("⛔ 断开连接"):
            broker.disconnect()
            st.info("已断开")
    with col_status:
        if broker.is_connected():
            mode = "模拟模式" if broker._mock else "实盘模式"
            st.success(f"🟢 已连接（{mode}）")
        else:
            st.warning("🔴 未连接")

    st.divider()

    if broker.is_connected():
        tab1, tab2, tab3, tab4 = st.tabs(["💰 资金", "📦 持仓", "📋 当日委托", "✅ 当日成交"])

        with tab1:
            balance = broker.get_balance()
            if balance and isinstance(balance, dict):
                bc = st.columns(len(balance))
                for i, (k, v) in enumerate(balance.items()):
                    try:
                        bc[i].metric(k, f"¥{float(v):,.2f}")
                    except Exception:
                        bc[i].metric(k, str(v))
            else:
                st.info("资金信息获取中...")

        with tab2:
            positions = broker.get_position()
            if positions:
                st.dataframe(pd.DataFrame(positions), use_container_width=True, hide_index=True)
            else:
                st.info("暂无持仓")

        with tab3:
            orders = broker.get_today_orders()
            if orders:
                st.dataframe(pd.DataFrame(orders), use_container_width=True, hide_index=True)
                if st.button("🗑️ 撤销所有未成交委托", type="secondary"):
                    n = broker.cancel_all_orders()
                    st.success(f"已撤销 {n} 笔委托")
            else:
                st.info("今日暂无委托")

        with tab4:
            trades = broker.get_today_trades()
            if trades:
                st.dataframe(pd.DataFrame(trades), use_container_width=True, hide_index=True)
            else:
                st.info("今日暂无成交")

        # 手动下单
        st.divider()
        st.subheader("🖊️ 手动下单")
        mc1, mc2, mc3, mc4, mc5 = st.columns([2, 1, 1, 1, 1])
        order_sym    = mc1.text_input("代码", "000001", key="order_sym")
        order_action = mc2.selectbox("操作", ["买入", "卖出"], key="order_action")
        order_price  = mc3.number_input("价格", min_value=0.01, value=10.0, step=0.01, key="order_price")
        order_qty    = mc4.number_input("数量(股)", min_value=100, value=100, step=100, key="order_qty")
        mc5.write("")
        mc5.write("")
        if mc5.button("📤 提交", type="primary", key="order_submit"):
            risk = RiskManager(broker)
            sym6 = order_sym.strip().zfill(6)
            if order_action == "买入":
                ok, msg = risk.check_buy(sym6, order_price, order_qty)
                if not ok:
                    st.error(f"风控拒绝: {msg}")
                else:
                    r = broker.buy(sym6, order_price, order_qty)
                    if r.success:
                        st.success(f"✅ 买入委托成功: {r.order_id}")
                    else:
                        st.error(f"❌ 买入失败: {r.message}")
            else:
                r = broker.sell(sym6, order_price, order_qty)
                if r.success:
                    st.success(f"✅ 卖出委托成功: {r.order_id}")
                else:
                    st.error(f"❌ 卖出失败: {r.message}")
    else:
        st.info("请先点击「连接同花顺」按钮")


# ════════════════════════════════════════════════════
# 页面: 系统配置
# ════════════════════════════════════════════════════
elif page == "⚙️ 系统配置":
    st.title("⚙️ 系统配置")

    from utils.config_loader import get_config
    cfg = get_config()
    # 隐藏密码
    import copy
    safe_cfg = copy.deepcopy(cfg)
    if "broker" in safe_cfg and "password" in safe_cfg["broker"]:
        safe_cfg["broker"]["password"] = "******"
    st.json(safe_cfg)
    st.info("修改配置请编辑项目根目录的 `config.local.yaml`，重启应用后生效")

    st.divider()
    st.subheader("📦 依赖包状态")
    deps = {
        "akshare":    "行情数据",
        "pandas":     "数据处理",
        "numpy":      "数值计算",
        "pandas_ta":  "技术指标",
        "streamlit":  "Web界面",
        "plotly":     "交互图表",
        "loguru":     "日志系统",
        "easytrader": "同花顺交易",
        "apscheduler":"定时任务",
        "backtrader": "回测框架",
    }
    for pkg, desc in deps.items():
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "已安装")
            st.write(f"✅ `{pkg}` ({ver}) — {desc}")
        except ImportError:
            st.write(f"❌ `{pkg}` — {desc}（未安装，运行: `pip install {pkg}`）")
