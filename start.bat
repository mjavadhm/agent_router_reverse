@echo off
title AgentRouter Reverse Proxy
cd /d "%~dp0"

echo ===================================================
echo Starting AgentRouter Reverse Proxy (Cline Spoofing)
echo Target: https://agentrouter.org
echo Local:  http://127.0.0.1:28471/v1
echo ===================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found! Creating .venv...
    python -m venv .venv
    .venv\Scripts\pip.exe install -r requirements.txt
)

.venv\Scripts\python.exe main.py
pause
