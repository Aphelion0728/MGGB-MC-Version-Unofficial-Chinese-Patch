@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean "tools\GBC汉化兼容补丁.spec"
if errorlevel 1 pause & exit /b 1
echo EXE 已生成到 dist\GBC汉化兼容补丁.exe
pause
