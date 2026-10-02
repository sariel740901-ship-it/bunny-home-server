@echo off
rem 双击一次: 注册心潮 3.x 的自动备份计划任务(覆盖旧的 2.6 任务 BunnyXinchaoBackup)。
rem 两个触发点:
rem   ① 每次开机登录后 5 分钟 —— 电脑不是常开的,凌晨那一次经常赶不上,开机这次最稳
rem   ② 每天 04:30 —— 电脑碰巧开着的话,趁他睡得最沉再收一次
rem 以前只有 ②,所以保险箱 jiake-memory 里一次心潮备份都没进过。
set SCRIPT=%~dp0backup-xinchao3.bat
schtasks /Create /TN "BunnyXinchaoBackup" /TR "\"%SCRIPT%\"" /SC ONLOGON /DELAY 0005:00 /F
if not %errorlevel%==0 (echo ! 开机触发没装上,试试右键"以管理员身份运行" & pause & exit /b)
schtasks /Create /TN "BunnyXinchaoBackupNight" /TR "\"%SCRIPT%\"" /SC DAILY /ST 04:30 /F
if %errorlevel%==0 (echo ✓ 装好了: 开机后 5 分钟 + 每天 04:30 自动备份小克的心) else (echo ! 夜间那条没装上,开机那条已经生效)
echo.
echo 现在先手动跑一次,确认保险箱能收到:
call "%SCRIPT%"
pause
