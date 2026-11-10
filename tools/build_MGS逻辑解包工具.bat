@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean "tools\MGS逻辑解包工具.spec"
echo EXE 已生成到 dist\MGS逻辑解包工具.exe
pause
