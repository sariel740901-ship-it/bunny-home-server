@echo off
cd /d %~dp0
echo 支起棋摊... (关掉这个窗口 = 收摊)
python server.py
pause
