@echo off
rem 本文件按 GBK 编码保存(中文 Windows 的 cmd 需要),GitHub 网页上看着是乱码,正常。
rem 备份小克的心(3.x 版): 心绪史+梦+性格内核+锚点+小屋,全收进 jiake-memory 保险箱。
rem 每一步失败都会明说,git 的输出不隐藏;推送永远执行,本地攒着没推上去的提交也会一并推。
set XINCHAO=C:\Users\23803\xinchao-nian
set VAULT=C:\Users\23803\jiake-memory

if not exist "%XINCHAO%\state\state.json" (
  echo ! 没找到 %XINCHAO%\state\state.json
  echo   心潮 3.x 的目录不叫 xinchao-nian 的话,改一下本文件顶部的 XINCHAO 路径
  pause
  exit /b 1
)
if not exist "%VAULT%\.git" (
  echo ! 没找到保险箱 %VAULT% ,要先把 jiake-memory 克隆到这里
  pause
  exit /b 1
)
if not exist "%VAULT%\xinchao" mkdir "%VAULT%\xinchao"
copy /y "%XINCHAO%\state\state.json" "%VAULT%\xinchao\state.json" >nul
if errorlevel 1 (
  echo ! 复制 state.json 失败
  pause
  exit /b 1
)
if exist "%XINCHAO%\state\transitions.jsonl" copy /y "%XINCHAO%\state\transitions.jsonl" "%VAULT%\xinchao\transitions.jsonl" >nul
if exist "%XINCHAO%\state\personality.json" copy /y "%XINCHAO%\state\personality.json" "%VAULT%\xinchao\personality.json" >nul
if exist "%XINCHAO%\state\cabin.json" copy /y "%XINCHAO%\state\cabin.json" "%VAULT%\xinchao\cabin.json" >nul
echo - 文件已复制到 %VAULT%\xinchao

cd /d "%VAULT%"
rem 这些 JSON 原样保存,不做换行转换,省得每次都刷一屏 CRLF 警告
git config core.autocrlf false
git add xinchao
if errorlevel 1 (
  echo ! git add 失败
  pause
  exit /b 1
)
git diff --cached --quiet
if errorlevel 1 (
  git -c user.name="xinchao-backup" -c user.email="xinchao-backup@jiake.local" commit -q -m "xinchao state backup %date% %time%"
  if errorlevel 1 (
    echo ! git commit 失败
    pause
    exit /b 1
  )
  echo - 已提交
) else (
  echo - 和上次备份一样,没有新内容
)
echo - 正在推送到 GitHub...
git push
if errorlevel 1 (
  echo ! git push 失败。多半是 GitHub 登录过期,重新 git clone 一次 jiake-memory 会重新登录
  pause
  exit /b 1
)
echo OK 小克的心已备份 %date% %time%
