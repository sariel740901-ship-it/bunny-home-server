@echo off
rem 备份小克的心 —— 把心潮的状态(心绪史+梦)收进 jiake-memory 保险箱。
rem 路径不对就改下面两行。
set XINCHAO=C:\Users\23803\xinchao-dynamic-mind
set VAULT=C:\Users\23803\jiake-memory

if not exist "%XINCHAO%\state\state.json" (echo ! 没找到 %XINCHAO%\state\state.json,改一下本文件顶部的路径 & pause & exit /b)
if not exist "%VAULT%" (echo ! 没找到保险箱 %VAULT%,改一下本文件顶部的路径 & pause & exit /b)
if not exist "%VAULT%\xinchao" mkdir "%VAULT%\xinchao"
copy /y "%XINCHAO%\state\state.json" "%VAULT%\xinchao\state.json" >nul
if exist "%XINCHAO%\state\transitions.jsonl" copy /y "%XINCHAO%\state\transitions.jsonl" "%VAULT%\xinchao\transitions.jsonl" >nul
cd /d "%VAULT%"
git add xinchao >nul 2>&1
git commit -m "xinchao state backup" >nul 2>&1
git push >nul 2>&1
echo ✓ 小克的心已备份 (%date% %time%)
