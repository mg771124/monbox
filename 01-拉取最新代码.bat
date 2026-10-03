@echo off
chcp 65001 >nul
echo ==========================================
echo    MonsterBox - 拉取仓库最新代码
echo ==========================================
echo.

:: 检查是否在git仓库
git rev-parse --is-inside-work-tree >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 当前目录不是Git仓库！
    pause
    exit /b 1
)

:: 显示当前分支
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "current_branch=%%b"
echo 当前分支: %current_branch%
echo.

:: 检查本地是否有未提交的修改
git status --porcelain >nul
for /f "delims=" %%s in ('git status --porcelain') do set "has_changes=1"
if defined has_changes (
    echo [警告] 检测到本地有未提交的修改：
    git status --short
    echo.
    choice /c YN /m "是否暂存本地修改后再拉取（rebase模式）？(Y/N)"
    if errorlevel 2 goto :direct_pull
    if errorlevel 1 goto :stash_pull
) else (
    echo 本地工作区干净，直接拉取...
    goto :direct_pull
)

:stash_pull
echo.
echo 正在暂存本地修改...
git stash push -m "自动暂存-拉取前备份"
if %errorlevel% neq 0 (
    echo [错误] 暂存失败！请手动解决冲突后重试。
    pause
    exit /b 1
)
echo 暂存完成，开始拉取...
git pull --rebase
set "pull_result=%errorlevel%"
echo.
echo 正在恢复本地修改...
git stash pop
if %errorlevel% neq 0 (
    echo [警告] 恢复暂存时可能有冲突，请手动检查！
)
goto :end_result

:direct_pull
echo 正在拉取最新代码...
git pull
set "pull_result=%errorlevel%"

:end_result
echo.
if %pull_result% equ 0 (
    echo ==========================================
    echo    [成功] 代码已同步到最新版本！
    echo ==========================================
) else (
    echo ==========================================
    echo    [失败] 拉取过程中出现错误！
    echo    请检查网络连接或手动解决冲突。
    echo ==========================================
)
echo.
pause
