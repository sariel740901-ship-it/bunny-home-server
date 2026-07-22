@echo off
cd /d %~dp0
echo 点亮暗房的红灯... (关掉这个窗口 = 停止服务)
python server.py
pause
