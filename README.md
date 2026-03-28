# 📈 A股量化交易系统

基于 Python 的 A 股实时分析和量化交易系统，支持接入同花顺账户进行自动化交易。

## 功能特性

- **实时行情** - 基于 AKShare 获取实时股价、涨跌、资金流向
- **技术指标** - MA、EMA、MACD、RSI、BOLL、KDJ、CCI、ATR、OBV 等20+指标
- **K线形态** - 自动识别锤子线、十字星、早晨之星等经典形态
- **量化策略** - 内置5种策略，支持自定义扩展
- **回测引擎** - 历史模拟交易，输出胜率/夏普/最大回撤等完整绩效
- **同花顺接入** - 基于 easytrader 实现自动下单、撤单、查持仓
- **风控模块** - 仓位控制、止损止盈、每日交易次数限制
- **Web界面** - Streamlit 可视化控制台，K线图/信号扫描/回测报告一体化

## 目录结构

```
astockanalysis/
├── main.py                 # 主程序入口 (CLI)
├── setup.py                # 项目初始化脚本
├── config.yaml             # 配置模板
├── config.local.yaml       # 本地配置（填入账户信息，不提交git）
├── requirements.txt        # 依赖包
├── start.bat               # Windows快速启动菜单
├── core/
│   ├── data_fetcher.py     # 数据获取 (AKShare)
│   ├── indicators.py       # 技术指标计算
│   ├── backtester.py       # 回测引擎
│   └── trading_engine.py   # 实时交易调度器
├── strategies/
│   ├── base.py             # 策略基类
│   └── builtin.py          # 内置策略集合
├── broker/
│   └── ths_broker.py       # 同花顺交易接口
├── ui/
│   └── app.py              # Streamlit Web界面
├── utils/
│   ├── config_loader.py    # 配置加载器
│   └── logger.py           # 日志工具
├── data/                   # 数据缓存目录
├── logs/                   # 日志目录
└── backtest_results/       # 回测结果目录
```

## 快速开始

### 1. 安装依赖

```bash
cd D:\Code\Claude\astockanalysis
pip install -r requirements.txt
```

> **TA-Lib 注意**: 如果 `ta-lib` 安装失败，系统已内置纯Python实现（`pandas-ta`），可跳过。

### 2. 初始化项目

```bash
python main.py init
```

### 3. 配置同花顺账户

编辑 `config.local.yaml`：

```yaml
broker:
  type: "ths"
  exe_path: "C:/同花顺软件/同花顺/xiadan.exe"  # 修改为你的实际路径
  account: "你的资金账号"
  password: "你的交易密码"

strategy:
  live_trading: false  # 先用false测试，确认无误后改为true
```

### 4. 启动 Web 控制台

```bash
python main.py web
# 或双击 start.bat
```

访问 http://localhost:8501

### 5. 命令行操作

```bash
# 扫描信号
python main.py scan 000001 600519 000858 --strategy multi_factor

# 回测
python main.py backtest 000001 --start 20230101 --capital 100000 --save

# 查询实时行情
python main.py quote 000001 600519

# 启动自动交易（仅信号模式，不实际下单）
python main.py trade --symbols 000001,600519 --strategy multi_factor --interval 5

# 启动自动交易（实盘模式，谨慎！）
python main.py trade --symbols 000001,600519 --live
```

## 内置策略说明

| 策略名称 | 说明 |
|---------|------|
| `ma_cross` | 双均线金叉/死叉（MA5/MA20）|
| `macd` | MACD金叉死叉+零轴判断 |
| `rsi` | RSI超买超卖反转 |
| `bollinger` | 布林带上下轨突破 |
| `kdj` | KDJ金叉死叉 |
| `multi_factor` | **多因子综合评分（推荐）**，集成MA+MACD+RSI+BOLL+KDJ+量价 |

## 自定义策略

在 `strategies/builtin.py` 中继承 `BaseStrategy`：

```python
from strategies.base import BaseStrategy, Signal, SignalType

class MyStrategy(BaseStrategy):
    name = "my_strategy"
    description = "我的自定义策略"

    def generate_signal(self, df, symbol) -> Signal:
        price = df["close"].iloc[-1]
        # 你的逻辑...
        return self._make_signal(symbol, SignalType.BUY, price, "买入原因", confidence=0.7)
```

然后注册到 `STRATEGY_REGISTRY`：
```python
STRATEGY_REGISTRY["my_strategy"] = MyStrategy
```

## 同花顺交易接口说明

本系统通过 [easytrader](https://github.com/shidenggui/easytrader) 与同花顺客户端通信：

1. 同花顺客户端需**保持运行并登录**
2. 系统通过模拟鼠标/键盘或通信端口发送委托
3. **建议流程**：先在 `live_trading: false` 模式下验证信号，确认策略有效后再开启实盘

## 风控参数

在 `config.local.yaml` 中配置：

```yaml
risk:
  max_position_ratio: 0.2   # 单股仓位不超过总资产20%
  max_total_ratio: 0.8      # 总持仓不超过80%（留20%现金）
  stop_loss_ratio: 0.05     # 亏损5%触发止损
  take_profit_ratio: 0.10   # 盈利10%触发止盈
  max_holding_count: 10     # 最多持有10只股票
```

## 注意事项

⚠️ **重要声明**：
- 本系统仅供学习和研究使用
- 量化策略不保证盈利，投资有风险
- 实盘交易前请充分测试回测效果
- 建议先用小资金验证，逐步增加仓位
- 作者不对任何交易损失负责

## 常见问题

**Q: easytrader 连接失败？**
A: 确认同花顺已运行，检查 `exe_path` 路径是否正确，部分版本同花顺需要设置通讯密码

**Q: AKShare 数据获取超时？**  
A: 检查网络，或在 `config.yaml` 中调大 `data.akshare.timeout`

**Q: 技术指标显示 NaN？**  
A: 历史数据不足，至少需要60条以上K线数据才能计算所有指标
