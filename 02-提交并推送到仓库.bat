@echo off
chcp 65001 >nul
echo ==========================================
echo    MonsterBox - 提交并推送到仓库
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

:: 先拉取最新代码避免冲突
echo 正在拉取远程最新代码以避免冲突...
git pull --no-edit
if %errorlevel% neq 0 (
    echo [警告] 拉取时出现问题，可能存在冲突，请检查后再试。
    pause
    exit /b 1
)
echo.

:: 检查是否有变更需要提交
echo 检测文件变更：
echo ------------------------------------------
git status --short
echo ------------------------------------------
echo.

git status --porcelain >nul
for /f "delims=" %%s in ('git status --porcelain') do set "has_changes=1"
if not defined has_changes (
    echo [提示] 没有检测到需要提交的文件变更。
    pause
    exit /b 0
)

:: 询问提交信息
set "commit_msg="
set /p "commit_msg=请输入提交说明（直接回车使用默认说明）: "
if "%commit_msg%"=="" (
    for /f "delims=" %%d in ('date /t') do set "datestr=%%d"
    for /f "delims=" %%t in ('time /t') do set "timestr=%%t"
    set "commit_msg=自动提交 - %datestr% %timestr%"
)

echo.
echo 提交信息: %commit_msg%
echo.

:: 添加所有变更
echo 正在添加所有变更文件...
git add -A
if %errorlevel% neq 0 (
    echo [错误] 添加文件失败！
    pause
    exit /b 1
)

:: 提交
echo 正在提交...
git commit -m "%commit_msg%"
if %errorlevel% neq 0 (
    echo [错误] 提交失败！可能是没有变更或存在冲突。
    pause
    exit /b 1
)

:: 推送
echo.
echo 正在推送到远程仓库...
git push origin %current_branch%
set "push_result=%errorlevel%"

echo.
if %push_result% equ 0 (
    echo ==========================================
    echo    [成功] 代码已成功推送到仓库！
    echo ==========================================
) else (
    echo ==========================================
    echo    [失败] 推送失败！
    echo    请检查网络连接或远程仓库权限。
    echo ==========================================
)
echo.
pause
