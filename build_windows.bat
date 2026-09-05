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

echo [1/3] Updating build tools...
py -3 -m pip install --upgrade pip || goto :build_error
echo [2/3] Installing StreamGrab and PyInstaller...
py -3 -m pip install -e ".[dev]" pyinstaller || goto :build_error
echo [3/3] Building StreamGrab.exe...
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name StreamGrab ^
  --collect-all yt_dlp ^
  --collect-all curl_cffi ^
  --hidden-import tkinter ^
  src\streamgrab\gui.py || goto :build_error

echo.
echo Build complete: dist\StreamGrab.exe
popd
pause
exit /b 0

:build_error
echo.
echo [ERROR] Build failed. Review the message above.
popd
pause
exit /b 1
