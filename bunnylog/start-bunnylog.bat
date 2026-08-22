@echo off
cd /d %~dp0
echo 打开兔窝档案... (关掉这个窗口 = 停止服务)
python server.py
pause
