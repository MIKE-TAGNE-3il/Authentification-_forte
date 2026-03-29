# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Makefile
#  Raccourcis pour les opérations Docker courantes.
#  Compatible Linux (make natif) et Windows (make via Git Bash / WSL)
# ═══════════════════════════════════════════════════════════════════════════════

COMPOSE_BASE = docker compose -f docker-compose.yml
COMPOSE_WIN  = $(COMPOSE_BASE) -f docker-compose.windows.yml
COMPOSE_LIN  = $(COMPOSE_BASE) -f docker-compose.linux.yml

.DEFAULT_GOAL := help

.PHONY: help start-linux start-windows stop logs restart build \
        check-linux check-windows install-linux install-windows \
        shell db-shell clean reset usb-windows

# ── Aide ─────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "╔═══════════════════════════════════════════════════╗"
	@echo "║          AuthForte — Makefile Reference           ║"
	@echo "╚═══════════════════════════════════════════════════╝"
	@echo ""
	@echo "  DÉMARRAGE"
	@echo "  ─────────────────────────────────────────────────"
	@echo "  make start-linux     Démarrer sur Linux"
	@echo "  make start-windows   Démarrer sur Windows"
	@echo "  make stop            Arrêter tous les conteneurs"
	@echo "  make restart         Redémarrer (stop + start-linux)"
	@echo "  make build           Reconstruire l'image backend"
	@echo ""
	@echo "  VÉRIFICATION"
	@echo "  ─────────────────────────────────────────────────"
	@echo "  make check-linux     Vérifier les prérequis Linux"
	@echo "  make check-windows   Vérifier les prérequis Windows"
	@echo ""
	@echo "  INSTALLATION"
	@echo "  ─────────────────────────────────────────────────"
	@echo "  make install-linux   Installer dépendances Linux"
	@echo "  make install-windows Installer dépendances Windows"
	@echo ""
	@echo "  OPÉRATIONS"
	@echo "  ─────────────────────────────────────────────────"
	@echo "  make logs            Afficher les logs en temps réel"
	@echo "  make shell           Ouvrir un shell dans le backend"
	@echo "  make db-shell        Ouvrir MySQL dans le conteneur db"
	@echo "  make usb-windows     Lancer le passthrough USB (Windows)"
	@echo ""
	@echo "  NETTOYAGE"
	@echo "  ─────────────────────────────────────────────────"
	@echo "  make clean           Arrêter + supprimer conteneurs"
	@echo "  make reset           Arrêter + supprimer tout (VOLUMES inclus)"
	@echo ""

# ── Démarrage ─────────────────────────────────────────────────────────────────
start-linux:
	@bash scripts/start.sh

start-windows:
	@powershell -ExecutionPolicy Bypass -File scripts/start.ps1

stop:
	@echo "Arrêt des conteneurs..."
	@$(COMPOSE_BASE) down || $(COMPOSE_LIN) down || $(COMPOSE_WIN) down
	@echo "Conteneurs arrêtés."

restart: stop start-linux

build:
	@echo "Reconstruction de l'image backend..."
	@$(COMPOSE_BASE) build backend

# ── Vérification ──────────────────────────────────────────────────────────────
check-linux:
	@bash scripts/check.sh

check-windows:
	@powershell -ExecutionPolicy Bypass -File scripts/check.ps1

# ── Installation ──────────────────────────────────────────────────────────────
install-linux:
	@bash scripts/install.sh

install-windows:
	@powershell -ExecutionPolicy Bypass -File scripts/install.ps1

# ── Opérations ────────────────────────────────────────────────────────────────
logs:
	@$(COMPOSE_BASE) logs -f

logs-backend:
	@$(COMPOSE_BASE) logs -f backend

shell:
	@docker exec -it authforte-backend bash

db-shell:
	@docker exec -it authforte-db mysql -u authforte -pauthforte_password authentification

usb-windows:
	@powershell -ExecutionPolicy Bypass -File scripts/usb-passthrough.ps1

# ── Nettoyage ─────────────────────────────────────────────────────────────────
clean:
	@echo "Nettoyage des conteneurs..."
	@$(COMPOSE_BASE) down --remove-orphans 2>/dev/null || true
	@echo "Nettoyage terminé."

reset:
	@echo "ATTENTION : Cette commande supprime les volumes Docker (données MySQL perdues)."
	@read -p "Confirmer ? [y/N] " ans && [ "$$ans" = "y" ] || exit 1
	@$(COMPOSE_BASE) down -v --remove-orphans
	@echo "Reset complet effectué."
