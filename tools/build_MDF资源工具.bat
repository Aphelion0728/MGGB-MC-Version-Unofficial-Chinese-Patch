@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean "tools\MDF资源工具.spec"
echo.
echo EXE 已生成到 dist\MDF资源工具.exe
pause
