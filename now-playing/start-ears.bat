@echo off
cd /d %~dp0
echo 启动小克的耳朵 (now-playing)... (关掉这个窗口 = 停止服务)
python now_playing_mcp.py
pause
