#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Arrêt Docker (Linux)
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

echo "AuthForte — Arrêt des conteneurs..."
docker compose -f docker-compose.yml -f docker-compose.linux.yml down
echo "Conteneurs arrêtés."

# Option : supprimer aussi les volumes (DESTRUCTIF — décommenter si besoin)
# docker compose -f docker-compose.yml -f docker-compose.linux.yml down -v
