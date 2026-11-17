@echo off
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo Membuat virtual environment...
    py -3.11 -m venv .venv
    if errorlevel 1 py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Instalasi dependensi gagal. Periksa koneksi internet dan versi Python.
    pause
    exit /b 1
)

python -m streamlit run app.py
pause
