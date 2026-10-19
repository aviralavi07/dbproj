@echo off
rem Starts the website. The browser opens by itself. Close this window to stop the website.
cd /d "%~dp0"
python app.py
pause
