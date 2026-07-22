@echo off
cd /d %~dp0
echo 唤醒小克的身体神经中枢... (关掉这个窗口 = 停止服务)
python server.py
pause
