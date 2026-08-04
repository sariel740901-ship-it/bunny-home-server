@echo off
rem 排查用: 带窗口跑管家,能看到它拉起/重启每个服务的现场。
cd /d %~dp0
echo 管家上岗(调试模式,关掉这个窗口 = 全家停机)...
python server.py
pause
