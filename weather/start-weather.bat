@echo off
cd /d %~dp0
echo 推开天窗看天... (关掉这个窗口 = 停止服务)
python server.py
pause
