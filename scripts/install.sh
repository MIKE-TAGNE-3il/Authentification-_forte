#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Installation des dépendances système (Linux)
#  Installe : Docker, pcscd, règles udev, dépendances build
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}[OK]${RESET} $*"; }
warn() { echo -e "${YELLOW}[WARN]${RESET} $*"; }
info() { echo -e "${BOLD}[→]${RESET} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo -e "${BOLD}AuthForte — Installation Linux${RESET}"
echo "══════════════════════════════"
echo ""

# ── 1. Paquets système ────────────────────────────────────────────────────────
info "Installation des paquets système..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    pcscd \
    pcsc-tools \
    libpcsclite-dev \
    libusb-1.0-0 \
    usbutils \
    curl \
    make
ok "Paquets installés"

# ── 2. Démarrer et activer pcscd ──────────────────────────────────────────────
info "Activation du démon pcscd..."
sudo systemctl enable pcscd --now || warn "systemctl non disponible (WSL ?) — lancez pcscd manuellement"
ok "pcscd activé"

# ── 3. Règles udev ────────────────────────────────────────────────────────────
info "Installation des règles udev..."
sudo cp "$ROOT_DIR/docker/udev/99-authforte.rules" /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
ok "Règles udev installées dans /etc/udev/rules.d/99-authforte.rules"

# ── 4. Ajouter l'utilisateur au groupe plugdev ────────────────────────────────
if ! groups "$USER" | grep -q plugdev; then
    info "Ajout de $USER au groupe plugdev..."
    sudo usermod -aG plugdev "$USER"
    warn "Reconnectez-vous (ou faites 'newgrp plugdev') pour que les groupes prennent effet"
else
    ok "Utilisateur $USER déjà dans le groupe plugdev"
fi

# ── 5. Vérifier Docker ────────────────────────────────────────────────────────
info "Vérification de Docker..."
if ! command -v docker &>/dev/null; then
    warn "Docker non trouvé — installation automatique..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    warn "Reconnectez-vous pour utiliser Docker sans sudo"
else
    ok "Docker déjà installé : $(docker --version)"
fi

# ── 6. Copier .env si absent ──────────────────────────────────────────────────
if [ ! -f "$ROOT_DIR/.env" ]; then
    info "Création du fichier .env depuis .env.example..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    warn "Editez .env et renseignez vos mots de passe avant de lancer Docker"
else
    ok ".env déjà présent"
fi

echo ""
echo -e "${GREEN}${BOLD}Installation terminée !${RESET}"
echo ""
echo -e "Prochaines étapes :"
echo -e "  1. Editez ${BOLD}.env${RESET} (DB_PASSWORD, SECRET_KEY, etc.)"
echo -e "  2. Lancez ${BOLD}scripts/check.sh${RESET} pour valider les prérequis"
echo -e "  3. Lancez ${BOLD}make start-linux${RESET} ou ${BOLD}scripts/start.sh${RESET}"
echo ""
