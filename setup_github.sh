#!/bin/bash
# ─────────────────────────────────────────────
# DayBay Daily — Setup GitHub
# Inicializa o repositório e faz o push para o GitHub
# ─────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GITHUB_USER="fillipbayer"
REPO_NAME="daybay-daily"

echo ""
echo "  ☀️  DayBay Daily — Setup GitHub"
echo "  ────────────────────────────────"
echo ""

# Verifica git
if ! command -v git &>/dev/null; then
  echo "  ❌ git não encontrado. Instale em: https://git-scm.com"
  exit 1
fi

# Inicializa o repositório se necessário
if [ ! -d ".git" ]; then
  echo "  📁 Inicializando repositório git..."
  git init -b main
fi

# Cria .env se não existir (não vai para o git)
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  📋 Arquivo .env criado (configure sua OPENAI_API_KEY)"
fi

# Cria diretórios de dados que precisam existir mas não vão ao git
mkdir -p data/bulletins data/audio
touch data/bulletins/.gitkeep data/audio/.gitkeep

# Adiciona e commita
echo "  📦 Adicionando arquivos..."
git add .
git status --short

echo ""
echo "  💾 Criando commit inicial..."
git commit -m "feat: DayBay Daily — boletim pessoal com IA

- Backend Python (FastAPI) com 18 fontes RSS
- Boletim em áudio via OpenAI TTS
- Palavras do dia: inglês avançado + mandarim básico
- Integração Microsoft Calendar (Outlook/Teams)
- Frontend responsivo (desktop + mobile)
- Deploy: Railway (backend) + Cloudflare Pages (frontend)"

echo ""

# Usa GitHub CLI se disponível
if command -v gh &>/dev/null; then
  echo "  🚀 Criando repositório no GitHub via gh CLI..."
  gh repo create "$GITHUB_USER/$REPO_NAME" \
    --public \
    --description "Boletim diário personalizado com IA — notícias, áudio, idiomas e agenda" \
    --push \
    --source=. \
    --remote=origin
  echo ""
  echo "  ✅ Repositório criado e código enviado!"
  echo "  🔗 https://github.com/$GITHUB_USER/$REPO_NAME"
else
  echo "  GitHub CLI (gh) não encontrado. Configure o remote manualmente:"
  echo ""
  echo "  1. Crie o repositório em: https://github.com/new"
  echo "     Nome: $REPO_NAME"
  echo ""
  echo "  2. Então rode:"
  echo "     git remote add origin https://github.com/$GITHUB_USER/$REPO_NAME.git"
  echo "     git push -u origin main"
fi

echo ""
echo "  ────────────────────────────────"
echo "  Próximos passos:"
echo "  1. Deploy Railway  → https://railway.app/new"
echo "  2. Deploy Cloudflare Pages → https://pages.cloudflare.com"
echo "  ────────────────────────────────"
echo ""
