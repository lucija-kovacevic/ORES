@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Prvo pokretanje: stvaram virtualno okruzenje .venv i instaliram pakete...
  py -3 -m venv .venv 2>nul || "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv
  if not exist ".venv\Scripts\python.exe" (
    echo Python nije pronaden. Instalirajte Python 3.10+ s https://www.python.org/downloads/
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo.
echo ================================================================
echo  ORES trziste - studenti u istoj mrezi otvaraju u pregledniku:
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { '     http://' + $_.IPAddress + ':8501' }"
echo.
echo  Na ovom racunalu: http://localhost:8501
echo  Ako Windows pita za vatrozid (firewall), kliknite "Allow / Dopusti".
echo  Za zaustavljanje zatvorite ovaj prozor.
echo ================================================================
echo.
start "" http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py
pause
