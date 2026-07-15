@echo off
cd /d %~dp0
echo 启动小克的语音条服务... (关掉这个窗口 = 停止服务)
python server.py
pause
