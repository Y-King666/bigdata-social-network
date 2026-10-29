@echo off
rem Start the standalone second-level dashboard on http://127.0.0.1:8601/
cd /d "%~dp0.."
".venv\Scripts\python.exe" -u "dashboard\server.py" >> "stream\logs\dashboard_server.log" 2>&1
