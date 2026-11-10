@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
python "src\python\MDF资源工具.py"
if errorlevel 1 pause
