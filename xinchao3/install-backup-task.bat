@echo off
rem 本文件按 GBK 编码保存(中文 Windows 的 cmd 需要),GitHub 网页上看着是乱码,正常。
rem 双击一次: 注册心潮 3.x 的自动备份计划任务(覆盖旧的 2.6 任务 BunnyXinchaoBackup)。
rem 两个触发点: 每次开机登录后 5 分钟(最稳),加每天 04:30(电脑碰巧开着就再收一次)。
rem 不管计划任务装没装上,最后都会当场跑一次备份,让你立刻看到结果。
set SCRIPT=%~dp0backup-xinchao3.bat

schtasks /Create /TN "BunnyXinchaoBackup" /TR "\"%SCRIPT%\"" /SC ONLOGON /DELAY 0005:00 /F >nul 2>&1
if errorlevel 1 (echo ! 开机触发没装上,右键"以管理员身份运行"再试一次) else (echo OK 开机触发装好了)
schtasks /Create /TN "BunnyXinchaoBackupNight" /TR "\"%SCRIPT%\"" /SC DAILY /ST 04:30 /F >nul 2>&1
if errorlevel 1 (echo ! 夜间触发没装上) else (echo OK 每天 04:30 装好了)
echo.
echo 现在当场跑一次备份:
echo ----------------------------------------
call "%SCRIPT%"
echo ----------------------------------------
pause
