@echo off
setlocal
pushd "%~dp0" || (
  echo [ERROR] Cannot access the StreamGrab project directory.
  pause
  exit /b 1
)

where py >nul 2>nul || (
  echo [ERROR] Windows Python was not found.
  echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
  echo During setup, enable "Add python.exe to PATH" and install the Python Launcher.
  popd
  pause
  exit /b 1
)

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul || (
  echo [ERROR] Python 3.11 or newer was not found.
  popd
  pause
  exit /b 1
)

echo [1/4] Updating build tools...
py -3 -m pip install --upgrade pip || goto :build_error
echo [2/4] Installing StreamGrab, the latest yt-dlp and PyInstaller...
py -3 -m pip install --upgrade -e ".[dev]" "yt-dlp[default,curl-cffi]" pyinstaller || goto :build_error
echo [3/4] Building StreamGrab.exe...
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name StreamGrab ^
  --collect-all yt_dlp ^
  --collect-all curl_cffi ^
  --collect-all yt_dlp_ejs ^
  --copy-metadata yt-dlp ^
  --copy-metadata yt-dlp-ejs ^
  --hidden-import tkinter ^
  src\streamgrab\gui.py || goto :build_error

echo [4/4] Creating the dist\StreamGrab app folder...
if not exist "dist\StreamGrab" mkdir "dist\StreamGrab" || goto :build_error
move /y "dist\StreamGrab.exe" "dist\StreamGrab\StreamGrab.exe" >nul || goto :build_error

echo.
echo Build complete: dist\StreamGrab\StreamGrab.exe
echo Copy the whole dist\StreamGrab folder. The app keeps yt-dlp up to date
echo in its yt-dlp subfolder on first launch.
popd
pause
exit /b 0

:build_error
echo.
echo [ERROR] Build failed. Review the message above.
popd
pause
exit /b 1
