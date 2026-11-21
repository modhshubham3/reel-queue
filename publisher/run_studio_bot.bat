@echo off
cd /d "%~dp0"
:loop
python studio_bot.py >> studio_bot.log 2>&1
timeout /t 10 /nobreak >nul
goto loop
