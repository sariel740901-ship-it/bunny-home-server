@echo off
cd /d %~dp0
echo 启动小克的 DJ 台... (关掉这个窗口 = 停止服务)
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
python server.py
pause
