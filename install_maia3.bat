@echo off
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo ERROR: Python virtual environment not found.
  echo Run install_windows.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate
if errorlevel 1 (
  echo ERROR: Could not activate the virtual environment.
  pause
  exit /b 1
)

echo.
echo Downloading the official Maia-3 source from GitHub...
set "ZIP=%TEMP%\maia3-main.zip"
set "SRC=%TEMP%\maia3-main"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/CSSLab/maia3/archive/refs/heads/main.zip' -OutFile '%ZIP%'"
if errorlevel 1 (
  echo ERROR: Could not download Maia-3 from GitHub.
  echo Check your internet connection and try again.
  pause
  exit /b 1
)

if exist "%SRC%" rmdir /s /q "%SRC%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%TEMP%' -Force"
if errorlevel 1 (
  echo ERROR: Could not extract the Maia-3 source archive.
  pause
  exit /b 1
)

echo.
echo Installing Maia-3 from its official source...
python -m pip install --upgrade pip
python -m pip install "%TEMP%\maia3-main"
if errorlevel 1 (
  echo.
  echo ERROR: Maia-3 installation failed.
  echo Check the Python and PyTorch installation messages above.
  pause
  exit /b 1
)

echo.
echo Checking Maia-3 command...
maia3-uci --list-models
if errorlevel 1 (
  echo WARNING: Maia-3 installed, but its command could not be run.
  echo Try: python -m maia3.uci --list-models
  pause
  exit /b 1
)

echo.
echo Maia-3 installation completed.
echo The 5M model weights will download automatically on first engine use.
echo You can pre-download them with: maia3-cache --model maia3-5m
pause
