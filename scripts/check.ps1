# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Vérification des prérequis (Windows / PowerShell)
# ═══════════════════════════════════════════════════════════════════════════════
#Requires -Version 5.1

$ErrorCount = 0

function ok   { param($msg) Write-Host "  [OK]    $msg" -ForegroundColor Green  }
function warn { param($msg) Write-Host "  [WARN]  $msg" -ForegroundColor Yellow }
function fail { param($msg) Write-Host "  [FAIL]  $msg" -ForegroundColor Red; $script:ErrorCount++ }
function info { param($msg) Write-Host "  [INFO]  $msg" -ForegroundColor Cyan  }
function head { param($msg) Write-Host "`n$msg" -ForegroundColor White         }

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   AuthForte — Vérification des prérequis    ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Docker Desktop ────────────────────────────────────────────────────────
head "1. Docker Desktop"
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    $ver = (docker --version 2>&1)
    ok "Docker installé : $ver"
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        ok "Docker daemon actif"
    } else {
        fail "Docker Desktop non démarré — ouvrez Docker Desktop"
    }
} else {
    fail "Docker non trouvé — installez Docker Desktop : https://www.docker.com/products/docker-desktop/"
}

# ── 2. Docker Compose ────────────────────────────────────────────────────────
head "2. Docker Compose"
$composeV2 = docker compose version 2>&1
if ($LASTEXITCODE -eq 0) {
    ok "Docker Compose v2 : $composeV2"
} else {
    fail "Docker Compose v2 non disponible (inclus dans Docker Desktop >= 3.x)"
}

# ── 3. WSL2 ──────────────────────────────────────────────────────────────────
head "3. WSL2"
$wsl = Get-Command wsl -ErrorAction SilentlyContinue
if ($wsl) {
    $wslVersion = wsl --status 2>&1 | Select-String "Default Version"
    ok "WSL disponible. $wslVersion"
} else {
    warn "WSL non trouvé — recommandé pour Docker Desktop (mode WSL2)"
}

# ── 4. usbipd-win (partage USB) ───────────────────────────────────────────────
head "4. usbipd-win (partage USB vers Docker)"
$usbipd = Get-Command usbipd -ErrorAction SilentlyContinue
if ($usbipd) {
    $usbipdVer = (usbipd --version 2>&1)
    ok "usbipd-win installé : $usbipdVer"
} else {
    warn "usbipd-win non installé — requis pour NFC/Cryptonox/YubiKey dans Docker"
    warn "Installez via : winget install usbipd  OU  https://github.com/dorssel/usbipd-win"
}

# ── 5. Fichier .env ───────────────────────────────────────────────────────────
head "5. Configuration .env"
$rootDir = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $rootDir ".env"
if (Test-Path $envFile) {
    ok ".env trouvé"
    $envContent = Get-Content $envFile -Raw
    if ($envContent -match "changeme") {
        warn "SECRET_KEY contient la valeur par défaut — changez-la"
    }
    foreach ($var in @("SECRET_KEY", "DB_PASSWORD", "MYSQL_ROOT_PASSWORD")) {
        if ($envContent -match "^${var}=") {
            ok "Variable $var définie"
        } else {
            warn "Variable $var absente du .env"
        }
    }
} else {
    fail ".env manquant — copiez .env.example : Copy-Item .env.example .env"
}

# ── 6. Ports disponibles ──────────────────────────────────────────────────────
head "6. Ports réseau"
$portsToCheck = @(80, 3306, 5000, 1025, 8025)
foreach ($port in $portsToCheck) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $proc = (Get-Process -Id (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess -ErrorAction SilentlyContinue).Name
        warn "Port $port utilisé par '$proc' — conflit possible"
    } else {
        ok "Port $port disponible"
    }
}

# ── 7. Périphériques USB (usbipd) ────────────────────────────────────────────
head "7. Périphériques USB détectés"
if (Get-Command usbipd -ErrorAction SilentlyContinue) {
    info "Périphériques USB détectés par usbipd :"
    usbipd list 2>&1 | ForEach-Object { Write-Host "    $_" }
    info "Astuce : scripts\usb-passthrough.ps1 pour partager un périphérique avec Docker"
} else {
    info "usbipd non disponible — ignoré"
}

# ── Rapport final ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan
if ($ErrorCount -eq 0) {
    Write-Host "  GO — Tous les prérequis sont satisfaits ✓" -ForegroundColor Green
    Write-Host "  Lancez : make start-windows  ou  scripts\start.ps1" -ForegroundColor White
} else {
    Write-Host "  NO-GO — $ErrorCount erreur(s) bloquante(s) à corriger" -ForegroundColor Red
}
Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

exit $ErrorCount
