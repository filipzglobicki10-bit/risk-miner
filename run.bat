@echo off
rem Risk Miner — uruchomienie (Windows). Wymaga Pythona 3.9+.
cd /d %~dp0
if not exist config.json copy config.example.json config.json
python -c "import pypdf" 2>nul || python -m pip install --user -q -r requirements-optional.txt
echo Otworz: http://127.0.0.1:8080
python app.py
