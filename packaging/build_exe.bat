@echo off
REM snippin 一键打包为 Windows exe（T-17）
REM 用法:
REM   build_exe.bat            -> onefile 单文件版（默认）
REM   build_exe.bat onedir     -> 目录版（杀软误报时的替代分发形态）
REM 产物: dist\snippin.exe 或 dist\snippin\
cd /d "%~dp0\.."

setlocal
if "%1"=="" (set SNIPPIN_PKG_MODE=onefile) else (set SNIPPIN_PKG_MODE=%1)

python -c "import PyInstaller" 1>nul 2>nul
if errorlevel 1 (
  echo [snippin] 未安装 PyInstaller，正在安装 .[dev] 依赖...
  pip install -e ".[dev]"
)

echo [snippin] 打包形态: %SNIPPIN_PKG_MODE%
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\snippin.spec
if errorlevel 1 (
  echo [snippin] 打包失败，见上方日志
  exit /b 1
)

echo [snippin] 体积核查...
python packaging\check_size.py --mode %SNIPPIN_PKG_MODE%
if errorlevel 1 (
  echo [snippin] 体积核查未通过：请检查是否引入了重量级依赖，或在 PR 中更新 packaging\size-budget.json
  exit /b 1
)

echo.
if "%SNIPPIN_PKG_MODE%"=="onedir" (
  echo 产物位于 dist\snippin\snippin.exe（分发前需压缩为 zip）
) else (
  echo 产物位于 dist\snippin.exe
)
endlocal
