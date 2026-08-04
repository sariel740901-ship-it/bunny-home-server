@echo off
rem 双击一次: 往"启动"文件夹放快捷方式,以后开机自动上岗,不用点任何 bat。
cd /d %~dp0
for /f "delims=" %%p in ('where pythonw 2^>nul') do (set "PW=%%p" & goto :make)
echo 找不到 pythonw.exe,装好 Python 再来。
pause
exit /b
:make
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\BunnyHome.lnk');" ^
  "$s.TargetPath='%PW%';$s.Arguments='server.py';$s.WorkingDirectory='%~dp0';$s.Description='Bunny Home 管家';$s.Save()"
if %errorlevel%==0 (echo ✓ 装好了: 下次开机管家自动上岗。现在就要?双击 start-home.bat) else (echo ! 失败了,看看上面的报错)
pause
