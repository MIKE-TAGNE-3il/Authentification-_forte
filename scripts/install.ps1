# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Installation des prérequis (Windows / PowerShell)
#  Installe : Docker Desktop, usbipd-win, crée .env
#  Exécutez en tant qu'Administrateur pour les installations système
# ═══════════════════════════════════════════════════════════════════════════════
#Requires -Version 5.1

function info { param($msg) Write-Host "[->] $msg" -ForegroundColor Cyan }
function ok   { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function warn { param($msg) Write-Host "[!!] $msg" -ForegroundColor Yellow }

$rootDir = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "AuthForte — Installation Windows" -ForegroundColor White -BackgroundColor DarkBlue
Write-Host "══════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── 1. Vérifier winget ────────────────────────────────────────────────────────
info "Vérification de winget..."
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    warn "winget non disponible — installez Docker Desktop manuellement :"
    warn "https://www.docker.com/products/docker-desktop/"
} else {
    ok "winget disponible"

    # ── 2. Docker Desktop ─────────────────────────────────────────────────────
    info "Vérification de Docker Desktop..."
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        info "Installation de Docker Desktop via winget..."
        winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
        ok "Docker Desktop installé — redémarrez le PC si demandé"
    } else {
        ok "Docker Desktop déjà installé : $(docker --version 2>&1)"
    }

    # ── 3. usbipd-win ────────────────────────────────────────────────────────
    info "Vérification de usbipd-win..."
    if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
        info "Installation de usbipd-win via winget..."
        winget install -e --id dorssel.usbipd-win --accept-package-agreements --accept-source-agreements
        ok "usbipd-win installé"
    } else {
        ok "usbipd-win déjà installé : $(usbipd --version 2>&1)"
    }
}

# ── 4. WSL2 ──────────────────────────────────────────────────────────────────
info "Vérification de WSL2..."
$wslFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -ErrorAction SilentlyContinue
if ($wslFeature -and $wslFeature.State -eq "Enabled") {
    ok "WSL déjà activé"
} else {
    warn "WSL non activé — activez avec : wsl --install (puis redémarrez)"
}

# ── 5. Fichier .env ───────────────────────────────────────────────────────────
info "Vérification du fichier .env..."
$envFile = Join-Path $rootDir ".env"
$envExample = Join-Path $rootDir ".env.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        ok ".env créé depuis .env.example"
        warn "Editez .env et renseignez vos mots de passe avant de lancer Docker"
    } else {
        warn ".env.example introuvable — créez .env manuellement"
    }
} else {
    ok ".env déjà présent"
}

Write-Host ""
Write-Host "Installation terminée !" -ForegroundColor Green
Write-Host ""
Write-Host "Prochaines étapes :" -ForegroundColor White
Write-Host "  1. Editez .env (DB_PASSWORD, SECRET_KEY, etc.)"
Write-Host "  2. Lancez scripts\check.ps1 pour valider les prérequis"
Write-Host "  3. Lancez make start-windows  ou  scripts\start.ps1"
Write-Host ""
