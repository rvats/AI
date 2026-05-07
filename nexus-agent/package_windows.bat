@echo off
setlocal

cd /d %~dp0

echo Installing runtime + packaging dependencies...
python -m pip install -r requirements-packaging.txt
if errorlevel 1 exit /b %errorlevel%

echo Building Nexus Desktop (Windows onefile)...
python packaging\build.py
if errorlevel 1 exit /b %errorlevel%

echo Done. Binary is in dist\
endlocal
