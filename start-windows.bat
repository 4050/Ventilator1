@echo off
cd /d "%~dp0"
py -3 server.py 2>nul || python server.py
pause
