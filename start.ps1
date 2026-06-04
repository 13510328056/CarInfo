if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Host "未检测到虚拟环境，请先运行 .\setup.bat 或手动创建虚拟环境。" -ForegroundColor Yellow
    exit 1
}
& .\.venv\Scripts\Activate.ps1
python app.py
