#!/bin/bash
# ─────────────────────────────────────────────
# DayBay Daily — Script de inicialização (macOS/Linux)
# ─────────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
ENV_FILE="$SCRIPT_DIR/.env"

echo ""
echo "  ☀️  DayBay Daily"
echo "  ─────────────────────────────"
echo ""

# Verifica Python
if ! command -v python3 &>/dev/null; then
  echo "  ❌ Python 3 não encontrado. Instale em: https://python.org"
  exit 1
fi

# Cria .env se não existir
if [ ! -f "$ENV_FILE" ]; then
  echo "  📋 Criando .env a partir do .env.example..."
  cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
  echo ""
  echo "  ⚠️  IMPORTANTE: Abra o arquivo .env e adicione sua OPENAI_API_KEY"
  echo "  ─────────────────────────────"
  echo "  Arquivo: $ENV_FILE"
  echo ""
  read -p "  Pressione Enter para continuar mesmo assim, ou Ctrl+C para configurar primeiro..."
fi

# Cria e ativa ambiente virtual
VENV="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV" ]; then
  echo "  📦 Criando ambiente virtual Python..."
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

# Instala dependências
echo "  📥 Instalando dependências..."
pip install -q -r "$BACKEND_DIR/requirements.txt"

# Inicia servidor
echo ""
echo "  🚀 Iniciando servidor DayBay..."
echo "  ─────────────────────────────"
echo "  Desktop:  http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "  (Para parar: Ctrl+C)"
echo ""

cd "$BACKEND_DIR"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
