@echo off
cd /d %~dp0
echo 打开小克的录音棚... (平时不用点这个,管家会自动拉起;这是应急/调试用)
python server.py
pause
