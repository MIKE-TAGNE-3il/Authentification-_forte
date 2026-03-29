# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Démarrage Docker (Windows / PowerShell)
# ═══════════════════════════════════════════════════════════════════════════════
#Requires -Version 5.1

$rootDir = Split-Path -Parent $PSScriptRoot
Set-Location $rootDir

Write-Host "AuthForte — Démarrage Windows" -ForegroundColor White

# Vérifier .env
if (-not (Test-Path ".env")) {
    Write-Host "[FAIL] Fichier .env manquant. Copiez .env.example :" -ForegroundColor Red
    Write-Host "       Copy-Item .env.example .env" -ForegroundColor Yellow
    exit 1
}

# Vérifier que Docker Desktop est démarré
$dockerOk = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Docker Desktop non démarré. Lancez Docker Desktop et réessayez." -ForegroundColor Red
    exit 1
}

# Démarrer les conteneurs
Write-Host "[->] Démarrage des conteneurs..." -ForegroundColor Cyan
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Plateforme démarrée !" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Application  -> http://localhost"
    Write-Host "  Flask direct -> http://localhost:5000"
    Write-Host "  MailHog UI   -> http://localhost:8025"
    Write-Host "  MySQL        -> localhost:3306"
    Write-Host ""
    Write-Host "Logs : docker compose logs -f backend"
    Write-Host "Arrêt : scripts\stop.ps1"
    Write-Host ""
} else {
    Write-Host "[FAIL] Echec du démarrage — vérifiez les logs :" -ForegroundColor Red
    Write-Host "       docker compose logs" -ForegroundColor Yellow
    exit 1
}
