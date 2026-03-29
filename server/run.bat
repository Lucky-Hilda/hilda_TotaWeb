@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 请先复制 .env.example 为 .env 并填写 LONGCAT_API_KEY
call conda activate cosyvoice
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
pause