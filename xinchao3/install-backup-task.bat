@echo off
chcp 65001 >nul
rem 双击一次: 注册心潮 3.x 的自动备份计划任务(覆盖旧的 2.6 任务 BunnyXinchaoBackup)。
rem 两个触发点:
rem   ① 每次开机登录后 5 分钟 —— 电脑不是常开的,凌晨那一次经常赶不上,开机这次最稳
rem   ② 每天 04:30 —— 电脑碰巧开着的话,趁他睡得最沉再收一次
rem 不管计划任务装没装上,最后都会当场跑一次备份,让你立刻看到结果。
set SCRIPT=%~dp0backup-xinchao3.bat

schtasks /Create /TN "BunnyXinchaoBackup" /TR "\"%SCRIPT%\"" /SC ONLOGON /DELAY 0005:00 /F >nul 2>&1
if %errorlevel%==0 (echo ✓ 开机触发装好了) else (echo ! 开机触发没装上,右键"以管理员身份运行"再试一次)
schtasks /Create /TN "BunnyXinchaoBackupNight" /TR "\"%SCRIPT%\"" /SC DAILY /ST 04:30 /F >nul 2>&1
if %errorlevel%==0 (echo ✓ 每天 04:30 装好了) else (echo ! 夜间触发没装上)
echo.
echo 现在当场跑一次备份:
echo ----------------------------------------
call "%SCRIPT%"
echo ----------------------------------------
pause
