@echo off
chcp 65001 >nul
title Risk Miner — baza doswiadczen inwestycji publicznych
cd /d "%~dp0"

set "PY="
where py >nul 2>&1 && (
    py -3 --version >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [BLAD] Nie znaleziono Pythona 3.9+ w systemie.
    echo Pobierz Pythona ze strony: https://www.python.org/downloads/
    echo (podczas instalacji zaznacz "Add python.exe to PATH").
    pause
    exit /b 1
)

if not exist config.json copy /y config.example.json config.json >nul

%PY% -c "import pypdf" >nul 2>&1
if errorlevel 1 (
    if exist ".venv\Scripts\python.exe" (
        set "PY=.venv\Scripts\python.exe"
    ) else (
        echo Instalowanie obslugi plikow PDF (pypdf)...
        %PY% -m pip install --user -q -r requirements-optional.txt >nul 2>&1
        if errorlevel 1 (
            %PY% -m venv .venv >nul 2>&1 && .venv\Scripts\python.exe -m pip install -q -r requirements-optional.txt >nul 2>&1 && set "PY=.venv\Scripts\python.exe"
        )
    )
)

echo.
echo ============================================================
echo   Risk Miner uruchamia sie...
echo   Przegladarka otworzy sie automatycznie: http://127.0.0.1:8080
echo   Nie zamykaj tego okna podczas pracy z aplikacja.
echo ============================================================
echo.

%PY% app.py --open
if errorlevel 1 (
    echo.
    echo [BLAD] Aplikacja zakonczyla sie bledem.
    pause
)
