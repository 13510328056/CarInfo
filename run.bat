@echo off
if not exist .venv\Scripts\activate (
  echo 未检测到虚拟环境，请先运行 setup.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate
python app.py
