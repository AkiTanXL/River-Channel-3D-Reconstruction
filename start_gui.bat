@echo off
REM RC3DR GUI 启动脚本 (Windows)

echo 正在启动 RC3DR GUI...
cd /d "%~dp0"
python gui\main.py

pause
