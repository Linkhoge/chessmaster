@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 (echo Python 3.10+ required. & pause & exit /b 1)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Base dependencies installed.
echo For Maia-3, run install_maia3.bat after this finishes.
pause
