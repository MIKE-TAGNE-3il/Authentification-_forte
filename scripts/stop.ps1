# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Arrêt Docker (Windows / PowerShell)
# ═══════════════════════════════════════════════════════════════════════════════
#Requires -Version 5.1

$rootDir = Split-Path -Parent $PSScriptRoot
Set-Location $rootDir

Write-Host "AuthForte — Arrêt des conteneurs..." -ForegroundColor Cyan
docker compose -f docker-compose.yml -f docker-compose.windows.yml down

if ($LASTEXITCODE -eq 0) {
    Write-Host "Conteneurs arrêtés." -ForegroundColor Green
} else {
    Write-Host "Erreur lors de l'arrêt." -ForegroundColor Red
    exit 1
}

# Option : supprimer aussi les volumes (DESTRUCTIF — décommenter si besoin)
# docker compose -f docker-compose.yml -f docker-compose.windows.yml down -v
