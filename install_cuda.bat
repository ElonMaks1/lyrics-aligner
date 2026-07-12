@echo off
cd /d "%~dp0"
echo Installing PyTorch with CUDA 12.4 for RTX 3050...
.\.venv\Scripts\pip.exe install torch torchaudio --index-url https://download.pytorch.org/whl/cu124 --force-reinstall
.\.venv\Scripts\python.exe -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
pause
