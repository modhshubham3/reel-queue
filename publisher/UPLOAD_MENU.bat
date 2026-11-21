@echo off
cd /d %~dp0
:menu
echo.
echo ==============================
echo   YouTube upload menu
echo ==============================
echo  1 = Setup (sirf pehli baar)
echo  2 = Sign-in: KAHANI channel
echo  3 = Sign-in: INTERVIEW channel
echo  4 = Sign-in: GTA channel
echo  5 = CHECK (kuch upload nahi hota)
echo  6 = TEST: sirf pehla video (i1)
echo  7 = POORA HAFTA upload
echo  8 = Sign-in MANUAL: KAHANI   (agar 2 atak jaye)
echo  9 = Sign-in MANUAL: INTERVIEW
echo 10 = Sign-in MANUAL: GTA
echo 11 = INSTAGRAM CHECK (kuch schedule nahi hota)
echo 12 = INSTAGRAM TEST: sirf 1 reel (i2)
echo 13 = INSTAGRAM: poora hafta schedule
echo 14 = INSTAGRAM FREE PLAN: sirf interview+kahani (3-3 karke)
echo  U = UPDATE (naye scripts khud download)
echo  0 = Band karo
echo.
echo  (Sign-in ke waqt window mein Ctrl+C mat dabana)
set /p c=Number likho aur Enter dabao: 
if "%c%"=="1" pip install google-api-python-client google-auth-oauthlib & goto menu
if "%c%"=="2" python yt_auth.py kahani & goto menu
if "%c%"=="3" python yt_auth.py interview & goto menu
if "%c%"=="4" python yt_auth.py gta & goto menu
if "%c%"=="5" python yt_publish.py ..\week1\queue.csv --dry-run & goto menu
if "%c%"=="6" python yt_publish.py ..\week1\queue.csv --only i1 & goto menu
if "%c%"=="7" python yt_publish.py ..\week1\queue.csv & goto menu
if "%c%"=="8" python yt_auth.py kahani --manual & goto menu
if "%c%"=="9" python yt_auth.py interview --manual & goto menu
if "%c%"=="10" python yt_auth.py gta --manual & goto menu
if "%c%"=="11" python ig_publish.py ..\week1\meta.json --dry-run & goto menu
if "%c%"=="12" python ig_publish.py ..\week1\meta.json --only i2 & goto menu
if "%c%"=="13" python ig_publish.py ..\week1\meta.json & goto menu
if "%c%"=="14" python ig_publish.py ..\week1\meta.json --lanes interview,kahani & goto menu
if /I "%c%"=="U" call UPDATE.bat & goto menu
if "%c%"=="0" exit
goto menu
