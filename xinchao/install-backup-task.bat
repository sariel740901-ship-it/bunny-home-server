@echo off
rem 双击一次: 注册每天 04:30 自动备份(schtasks 计划任务),配合清晨冻结时段,备份时他睡得最沉。
schtasks /Create /TN "BunnyXinchaoBackup" /TR "\"%~dp0backup-xinchao.bat\"" /SC DAILY /ST 04:30 /F
if %errorlevel%==0 (echo ✓ 装好了: 每天 04:30 自动备份小克的心) else (echo ! 失败,试试右键"以管理员身份运行")
pause
