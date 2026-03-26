#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Démarrage Docker (Linux)
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

BOLD='\033[1m'; GREEN='\033[0;32m'; RESET='\033[0m'

echo -e "${BOLD}AuthForte — Démarrage Linux${RESET}"

# Vérifier .env
if [ ! -f .env ]; then
    echo "Fichier .env manquant. Copiez .env.example : cp .env.example .env"
    exit 1
fi

# S'assurer que pcscd tourne sur l'hôte
if command -v systemctl &>/dev/null; then
    sudo systemctl start pcscd 2>/dev/null || true
fi

# Démarrer les conteneurs
docker compose -f docker-compose.yml -f docker-compose.linux.yml up -d --build

echo ""
echo -e "${GREEN}${BOLD}Plateforme démarrée !${RESET}"
echo ""
echo -e "  Application  → http://localhost"
echo -e "  Flask direct → http://localhost:5000"
echo -e "  MailHog UI   → http://localhost:8025"
echo -e "  MySQL        → localhost:3306"
echo ""
echo -e "Logs : ${BOLD}docker compose logs -f backend${RESET}"
echo -e "Arrêt : ${BOLD}scripts/stop.sh${RESET}"
echo ""
