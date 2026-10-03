@echo off
chcp 65001 >nul
echo ==========================================
echo    MonsterBox - 本地仓库状态检查
echo ==========================================
echo.

:: 检查是否在git仓库
git rev-parse --is-inside-work-tree >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 当前目录不是Git仓库！
    pause
    exit /b 1
)

:: 显示当前分支和最新提交
echo [当前分支]
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do echo %%b
echo.

echo [最近3次提交]
git log --oneline -3
echo.

:: 获取远程更新但不合并
echo 正在检查远程仓库更新...
git fetch origin --quiet
if %errorlevel% equ 0 (
    echo.
    echo [远程仓库差异]
    for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do (
        echo 本地领先远程: 
        for /f "delims=" %%a in ('git rev-list HEAD..origin/%%b --count 2^>nul') do echo   远程有 %%a 个新提交待拉取
        echo 远程领先本地:
        for /f "delims=" %%c in ('git rev-list origin/%%b..HEAD --count 2^>nul') do echo   本地有 %%c 个提交未推送
    )
)
echo.

echo [本地文件变更]
echo ------------------------------------------
git status --short
echo ------------------------------------------

for /f "delims=" %%s in ('git status --porcelain') do set "has_changes=1"
if defined has_changes (
    echo.
    echo 提示：有本地修改未提交，可使用：
    echo   1. 运行「01-拉取最新代码.bat」同步远程
    echo   2. 运行「02-提交并推送到仓库.bat」上传本地
) else (
    echo.
    echo 本地工作区干净，无未提交变更。
)
echo.
pause
