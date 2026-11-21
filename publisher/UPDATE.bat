@echo off
cd /d %~dp0
set U=https://raw.githubusercontent.com/modhshubham3/reel-queue/ccr-cb619668-8pcm8x
echo Naye scripts download ho rahe hain...
for %%F in (ig_publish.py yt_publish.py yt_auth.py UPLOAD_MENU.bat) do (
  powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing '%U%/publisher/%%F' -OutFile '%%F.new'; Move-Item -Force '%%F.new' '%%F'; Write-Host 'OK  %%F' } catch { Write-Host 'FAIL %%F'; Write-Host $_.Exception.Message }"
)
if not exist ..\week1 mkdir ..\week1
for %%F in (meta.json queue.csv) do (
  powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing '%U%/week1/%%F' -OutFile '..\week1\%%F'; Write-Host 'OK  week1\%%F' } catch { Write-Host 'FAIL %%F'; Write-Host $_.Exception.Message }"
)
echo.
echo Ho gaya. Ab UPLOAD_MENU.bat dobara kholo.
pause
