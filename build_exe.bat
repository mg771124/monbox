@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
echo Python 3 was not found. Install Python 3.11 or newer on the build computer.
pause
goto end
:use_py
py -3 build_exe.py
goto end
:use_python
python build_exe.py
:end
