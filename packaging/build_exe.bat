@echo off
REM quicksnip 一键打包为 Windows exe（无控制台窗口）
cd /d "%~dp0\.."
pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name quicksnip --paths src packaging\launcher.py
echo.
echo 产物位于 dist\quicksnip.exe
pause
