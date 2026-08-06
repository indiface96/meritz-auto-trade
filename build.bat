@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHON=C:\Users\KDM_HOME\AppData\Local\Programs\Python\Python314-32\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] Python not found: %PYTHON%
    pause
    exit /b 1
)
echo ===== Build Start =====
"%PYTHON%" -m PyInstaller --clean build.spec
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build Failed!
    pause
    exit /b 1
)
echo ===== Build Complete =====
pause
