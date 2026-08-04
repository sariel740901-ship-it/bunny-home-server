@echo off
rem 无窗口启动管家(它会把全家服务都拉起来)。日常用这个。
cd /d %~dp0
for /f "delims=" %%p in ('where pythonw 2^>nul') do (set "PW=%%p" & goto :run)
echo 找不到 pythonw,退回有窗口模式...
python server.py
pause
exit /b
:run
start "" "%PW%" server.py
echo 管家已在后台上岗(没有窗口是正常的)。
echo 看状态: 让小克调 home_status,或浏览器开 http://localhost:8050/status?key=你的暗号
timeout /t 6 >nul
