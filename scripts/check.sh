#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Vérification des prérequis (Linux / WSL2)
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Couleurs ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]${RESET}    $*"; }
warn() { echo -e "  ${YELLOW}[WARN]${RESET}  $*"; }
fail() { echo -e "  ${RED}[FAIL]${RESET}  $*"; ERRORS=$((ERRORS+1)); }
info() { echo -e "  ${BLUE}[INFO]${RESET}  $*"; }

ERRORS=0

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║   AuthForte — Vérification des prérequis    ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${RESET}"
echo ""

# ── 1. Docker ────────────────────────────────────────────────────────────────
echo -e "${BOLD}1. Docker${RESET}"
if command -v docker &>/dev/null; then
    VER=$(docker --version 2>&1)
    ok "Docker installé : $VER"
    if docker info &>/dev/null; then
        ok "Docker daemon actif"
    else
        fail "Docker daemon non démarré — lancez Docker Desktop ou 'sudo systemctl start docker'"
    fi
else
    fail "Docker non trouvé — installez Docker : https://docs.docker.com/engine/install/"
fi

# ── 2. Docker Compose ────────────────────────────────────────────────────────
echo -e "\n${BOLD}2. Docker Compose${RESET}"
if docker compose version &>/dev/null 2>&1; then
    VER=$(docker compose version 2>&1)
    ok "Docker Compose v2 : $VER"
elif command -v docker-compose &>/dev/null; then
    warn "docker-compose v1 détecté — préférez Docker Compose v2 (intégré à Docker Desktop)"
else
    fail "Docker Compose non trouvé"
fi

# ── 3. Fichier .env ───────────────────────────────────────────────────────────
echo -e "\n${BOLD}3. Configuration .env${RESET}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
if [ -f "$ROOT_DIR/.env" ]; then
    ok ".env trouvé"
    if grep -q "changeme" "$ROOT_DIR/.env"; then
        warn "SECRET_KEY contient la valeur par défaut — changez-la avant de passer en production"
    fi
    # Vérifier les variables critiques
    for VAR in SECRET_KEY DB_PASSWORD MYSQL_ROOT_PASSWORD; do
        if grep -q "^${VAR}=" "$ROOT_DIR/.env"; then
            ok "Variable $VAR définie"
        else
            warn "Variable $VAR absente du .env"
        fi
    done
else
    fail ".env manquant — copiez .env.example : cp .env.example .env"
fi

# ── 4. Ports disponibles ──────────────────────────────────────────────────────
echo -e "\n${BOLD}4. Ports réseau${RESET}"
for PORT in 80 3306 5000 1025 8025; do
    if ss -tlnp 2>/dev/null | grep -q ":${PORT} " || \
       netstat -tlnp 2>/dev/null | grep -q ":${PORT} "; then
        warn "Port $PORT déjà utilisé — conflit possible"
    else
        ok "Port $PORT disponible"
    fi
done

# ── 5. PC/SC daemon (NFC) ─────────────────────────────────────────────────────
echo -e "\n${BOLD}5. PC/SC — NFC${RESET}"
if command -v pcscd &>/dev/null; then
    ok "pcscd installé"
    if systemctl is-active --quiet pcscd 2>/dev/null; then
        ok "pcscd en cours d'exécution"
    else
        warn "pcscd non actif — démarrez avec : sudo systemctl start pcscd"
    fi
else
    warn "pcscd non installé — requis pour NFC : sudo apt install pcscd"
fi
if [ -S /var/run/pcscd/pcscd.comm ]; then
    ok "Socket PC/SC disponible : /var/run/pcscd/pcscd.comm"
else
    warn "Socket PC/SC absente — NFC désactivé si pcscd ne tourne pas"
fi

# ── 6. Règles udev ────────────────────────────────────────────────────────────
echo -e "\n${BOLD}6. Règles udev${RESET}"
if [ -f /etc/udev/rules.d/99-authforte.rules ]; then
    ok "Règles udev installées"
else
    warn "Règles udev absentes — lancez scripts/install.sh pour les installer"
fi

# ── Rapport final ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════════════${RESET}"
if [ "$ERRORS" -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}GO${RESET} — Tous les prérequis sont satisfaits ✓"
    echo -e "  Lancez : ${BOLD}make start-linux${RESET}  ou  ${BOLD}scripts/start.sh${RESET}"
else
    echo -e "  ${RED}${BOLD}NO-GO${RESET} — $ERRORS erreur(s) bloquante(s) à corriger"
fi
echo -e "${BOLD}══════════════════════════════════════════════${RESET}"
echo ""
