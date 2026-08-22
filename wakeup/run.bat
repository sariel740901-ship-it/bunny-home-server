@echo off
rem 不想用 Docker 的话,双击这个直接跑(需要装 Node 18+)。
rem 崩了自动重启 —— 节律存在 state\state.json,重启接着同一节律。
cd /d %~dp0
if not exist .env (
  echo 还没有 .env —— 先 Copy-Item env.template .env 然后填好再跑
  pause
  exit /b 1
)
:loop
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%~dp0.env") do set "%%a=%%b"
node engine.js
echo [%date% %time%] 引擎退出了,5 秒后重启...
timeout /t 5 /nobreak >nul
goto loop
