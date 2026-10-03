@echo off
REM 【通用】切换到本批次文件所在的项目根目录，避免双击时工作目录错误。
cd /d "%~dp0"
REM 【通用】设置 UTF-8 代码页，确保中文编译信息正常显示。
chcp 65001 >nul
REM 【通用】显示当前一键编译目标。
echo 正在编译无需安装 Python 的 MonsterBox.exe...
REM 【通用】安装项目、测试工具和 PyInstaller 编译器。
python -m pip install -e ".[dev]"
REM 【通用】依赖安装失败时停止，避免产生不完整 EXE。
if errorlevel 1 goto :error
REM 【通用】执行测试，确保通过验证后才开始打包。
python -m pytest -q
REM 【通用】测试失败时停止编译。
if errorlevel 1 goto :error
REM 【通用】以单文件、无控制台窗口模式封装 Python 与全部运行依赖。
python -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name MonsterBox --paths src --hidden-import monsterbox.services.automation --hidden-import monsterbox.services.orchestrator src\monsterbox\main.py
REM 【通用】PyInstaller 失败时显示错误状态。
if errorlevel 1 goto :error
REM 【通用】确认独立 EXE 已实际生成。
if not exist "dist\MonsterBox.exe" goto :error
REM 【通用】显示成品位置，目标电脑只需复制此 EXE。
echo.
echo 编译完成：%~dp0dist\MonsterBox.exe
REM 【通用】等待用户查看结果后关闭窗口。
pause
REM 【通用】以成功状态结束批次文件。
exit /b 0

:error
REM 【通用】明确提示编译失败，保留上方错误信息供排查。
echo.
echo 编译失败，请查看上方错误信息。
REM 【通用】等待用户查看错误后关闭窗口。
pause
REM 【通用】以失败状态结束批次文件。
exit /b 1
