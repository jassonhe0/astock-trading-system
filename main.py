#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股量化交易系统 - 主程序入口
用法:
  python main.py web                    # 启动Web界面
  python main.py scan 000001 600519     # 扫描信号
  python main.py backtest 000001        # 回测
  python main.py trade --live           # 启动自动交易
  python main.py quote 000001           # 查询实时行情
"""
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


@click.group()
def cli():
    """📈 A股量化交易系统"""
    pass


# ─────────────────────────────────────────────
# web: 启动 Streamlit
# ─────────────────────────────────────────────
@cli.command()
@click.option("--port", default=8501, help="端口号")
def web(port):
    """🌐 启动 Web 控制台"""
    import subprocess
    console.print(Panel(
        f"[bold green]启动 Web 控制台[/]\n"
        f"访问地址: [link]http://localhost:{port}[/link]",
        title="A股量化系统", border_style="green"
    ))
    ui_path = Path(__file__).parent / "ui" / "app.py"
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(ui_path),
        "--server.port", str(port),
        "--server.address", "127.0.0.1",
        "--server.headless", "false",
    ])


# ─────────────────────────────────────────────
# scan: 信号扫描
# ─────────────────────────────────────────────
@cli.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option("--strategy", "-s", default="multi_factor", help="策略名称")
@click.option("--period", "-p", default="daily", help="K线周期")
def scan(symbols, strategy, period):
    """🔍 扫描股票信号"""
    from core.data_fetcher import get_kline
    from core.indicators import add_all_indicators
    from strategies.builtin import get_strategy

    strat = get_strategy(strategy)
    console.print(f"[cyan]使用策略: {strategy}[/]")

    table = Table(title="信号扫描结果", box=box.ROUNDED)
    table.add_column("代码", style="cyan")
    table.add_column("信号", style="bold")
    table.add_column("价格", justify="right")
    table.add_column("置信度", justify="right")
    table.add_column("原因")

    for sym in symbols:
        sym = sym.zfill(6)
        try:
            df = get_kline(sym, period)
            if df.empty:
                table.add_row(sym, "[red]获取失败[/]", "-", "-", "数据为空")
                continue
            df = add_all_indicators(df)
            sig = strat.generate_signal(df, sym)
            signal_str = {
                "buy": "[bold red]🟢 买入[/]",
                "sell": "[bold green]🔴 卖出[/]",
                "hold": "⚪ 持有",
            }.get(sig.signal.value, "-")
            table.add_row(
                sym, signal_str,
                f"{sig.price:.3f}",
                f"{sig.confidence:.0%}",
                sig.reason,
            )
        except Exception as e:
            table.add_row(sym, "[red]错误[/]", "-", "-", str(e))

    console.print(table)
    # click.echo 输出供测试和非rich环境使用
    for sym in symbols:
        sym = sym.zfill(6)
        click.echo(f"RESULT {sym}")


# ─────────────────────────────────────────────
# backtest: 回测
# ─────────────────────────────────────────────
@cli.command()
@click.argument("symbol")
@click.option("--strategy", "-s", default="multi_factor")
@click.option("--start", default="20230101", help="开始日期 YYYYMMDD")
@click.option("--end", default=None, help="结束日期 YYYYMMDD")
@click.option("--capital", "-c", default=100000.0, help="初始资金")
@click.option("--save", is_flag=True, help="保存结果到CSV")
def backtest(symbol, strategy, start, end, capital, save):
    """🔁 策略回测"""
    from core.backtester import Backtester
    from strategies.builtin import get_strategy

    strat = get_strategy(strategy)
    bt = Backtester(strat, initial_capital=capital)
    result = bt.run(symbol.zfill(6), start, end)

    if save:
        path = bt.save_result(result)
        console.print(f"[green]结果已保存: {path}[/]")


# ─────────────────────────────────────────────
# quote: 实时行情
# ─────────────────────────────────────────────
@cli.command()
@click.argument("symbols", nargs=-1, required=True)
def quote(symbols):
    """📊 查询实时行情"""
    from core.data_fetcher import get_realtime_quote

    table = Table(title="实时行情", box=box.ROUNDED)
    table.add_column("代码")
    table.add_column("最新价", justify="right")
    table.add_column("涨跌幅", justify="right")
    table.add_column("成交量", justify="right")

    for sym in symbols:
        q = get_realtime_quote(sym.zfill(6))
        price = q.get("price", 0) or 0
        chg = q.get("change_pct", 0) or 0
        vol = q.get("volume", 0) or 0
        chg_str = f"[red]{chg:+.2f}%[/]" if chg >= 0 else f"[green]{chg:+.2f}%[/]"
        table.add_row(sym.zfill(6), f"{price:.3f}", chg_str, f"{vol:,.0f}")

    console.print(table)


# ─────────────────────────────────────────────
# trade: 自动交易
# ─────────────────────────────────────────────
@cli.command()
@click.option("--symbols", "-w", default="000001,600519", help="监控股票(逗号分隔)")
@click.option("--strategy", "-s", default="multi_factor")
@click.option("--interval", "-i", default=5, help="扫描间隔(分钟)")
@click.option("--live", is_flag=True, help="开启实盘交易（谨慎！）")
def trade(symbols, strategy, interval, live):
    """⚡ 启动自动交易引擎"""
    from core.trading_engine import TradingEngine

    if live:
        console.print(Panel(
            "[bold red]⚠️  实盘交易模式！将真实下单！[/]\n"
            "请确认:\n"
            "  1. config.local.yaml 账号密码已正确配置\n"
            "  2. 同花顺客户端已登录\n"
            "  3. 风控参数已设置",
            title="警告", border_style="red"
        ))
        import click
        if not click.confirm("确认启动实盘交易？"):
            return

    engine = TradingEngine(strategy_name=strategy, live_trading=live)
    sym_list = [s.strip().zfill(6) for s in symbols.split(",")]
    engine.add_watch(*sym_list)

    console.print(f"[green]✅ 交易引擎启动[/] | 策略:{strategy} | "
                  f"股票:{sym_list} | 间隔:{interval}分 | "
                  f"模式:{'[red]实盘[/]' if live else '仅信号'}")

    engine.start(interval_minutes=interval)

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        engine.stop()
        console.print("[yellow]已停止[/]")


# ─────────────────────────────────────────────
# init: 初始化项目
# ─────────────────────────────────────────────
@cli.command()
def init():
    """🛠️ 初始化项目目录结构"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "setup", Path(__file__).parent / "setup.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.create_structure()


if __name__ == "__main__":
    cli()
