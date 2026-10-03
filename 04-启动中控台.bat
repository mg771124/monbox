@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo    MonsterBox - 启动中控台（无 CMD 视窗）
echo ==========================================
echo.
echo 正在以无控制台方式启动，本视窗会自动关闭...
echo.

:: 让源码目录可被导入，无需先安装项目
set "PYTHONPATH=%CD%\src"

:: 优先使用 pyw（Python 启动器自带的窗口化版本）
where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 -m monsterbox.main
    goto :end
)

:: 其次使用 pythonw（窗口化解释器）
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw -m monsterbox.main
    goto :end
)

echo [错误] 未找到 pyw 或 pythonw，请先安装 Python 3.11 或更新版本。
echo 安装时请勾选 Add Python to PATH。
echo.
pause

:end
