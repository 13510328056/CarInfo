@echo off
python -m venv .venv
if errorlevel 1 (
  echo 创建虚拟环境失败，请检查 Python 是否已安装并已添加到 PATH。
  pause
  exit /b 1
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo 依赖安装失败，请检查网络或 Python 环境。
  pause
  exit /b 1
)
echo 安装完成。
echo 请运行 run.bat 启动服务。
pause
