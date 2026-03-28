@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════╗
echo ║      A股量化交易系统 启动菜单        ║
echo ╠══════════════════════════════════════╣
echo ║  1. 启动 Web 控制台                  ║
echo ║  2. 扫描信号 (默认股票池)            ║
echo ║  3. 回测 平安银行 (000001)           ║
echo ║  4. 查询实时行情                     ║
echo ║  5. 安装依赖                         ║
echo ║  6. 初始化目录                       ║
echo ║  0. 退出                             ║
echo ╚══════════════════════════════════════╝
echo.
set /p choice=请输入选项: 

if "%choice%"=="1" (
    echo 启动 Web 界面...
    python main.py web
) else if "%choice%"=="2" (
    echo 扫描信号...
    python main.py scan 000001 600519 000858 002415 300750 601318
) else if "%choice%"=="3" (
    echo 回测 000001...
    python main.py backtest 000001 --start 20230101 --save
) else if "%choice%"=="4" (
    set /p syms=请输入股票代码(空格分隔): 
    python main.py quote %syms%
) else if "%choice%"=="5" (
    echo 安装依赖...
    pip install -r requirements.txt
) else if "%choice%"=="6" (
    python main.py init
) else if "%choice%"=="0" (
    exit
)

pause
