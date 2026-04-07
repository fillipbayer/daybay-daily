@echo off
REM ─────────────────────────────────────────────
REM DayBay Daily — Script de inicialização (Windows)
REM ─────────────────────────────────────────────

echo.
echo   ☀️  DayBay Daily
echo   ─────────────────────────────
echo.

SET SCRIPT_DIR=%~dp0
SET BACKEND_DIR=%SCRIPT_DIR%backend
SET ENV_FILE=%SCRIPT_DIR%.env
SET VENV=%SCRIPT_DIR%.venv

REM Verifica Python
where python >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo   Erro: Python nao encontrado. Instale em: https://python.org
    pause
    exit /b 1
)

REM Cria .env se nao existir
IF NOT EXIST "%ENV_FILE%" (
    echo   Criando .env a partir do .env.example...
    copy "%SCRIPT_DIR%.env.example" "%ENV_FILE%" >nul
    echo.
    echo   IMPORTANTE: Abra o arquivo .env e adicione sua OPENAI_API_KEY
    echo   Arquivo: %ENV_FILE%
    echo.
    pause
)

REM Cria ambiente virtual se nao existir
IF NOT EXIST "%VENV%" (
    echo   Criando ambiente virtual Python...
    python -m venv "%VENV%"
)

REM Ativa ambiente virtual
call "%VENV%\Scripts\activate.bat"

REM Instala dependencias
echo   Instalando dependencias...
pip install -q -r "%BACKEND_DIR%\requirements.txt"

REM Inicia servidor
echo.
echo   Iniciando servidor DayBay...
echo   ─────────────────────────────
echo   Desktop:  http://localhost:8000
echo   API docs: http://localhost:8000/docs
echo.
echo   (Para parar: Ctrl+C)
echo.

cd "%BACKEND_DIR%"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
