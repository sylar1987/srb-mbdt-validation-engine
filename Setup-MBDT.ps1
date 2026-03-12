#Requires -Version 5.1
<#
.SYNOPSIS
    Setup-Skript fuer die SRB MBDT Validierungsengine v1.1
    Single Resolution Board - Minimum Bail-in Data Template Validator

.DESCRIPTION
    Prueft Python-Installation (3.9+), installiert benoettigte Abhaengigkeiten
    (pandas, openpyxl) via pip und bereitet die Laufzeitumgebung vor.

.NOTES
    Ausfuehren als normaler Benutzer (kein Admin erforderlich, solange Python
    im Benutzerpfad installiert ist).

    Falls das Skript nicht startet:
      Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#>

[CmdletBinding()]
param(
    [switch]$Force,           # Pakete auch dann neu installieren, wenn bereits vorhanden
    [switch]$NoVenv,          # Kein virtuelles Environment anlegen (direkt in Python-Basis)
    [string]$VenvPath = ""    # Optionaler Pfad fuer venv (Standard: .\venv)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
function Write-Header {
    param([string]$Text)
    $line = "=" * 70
    Write-Host ""
    Write-Host $line -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host $line -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    Write-Host "  [*] $Text" -ForegroundColor Yellow
}

function Write-OK {
    param([string]$Text)
    Write-Host "  [OK] $Text" -ForegroundColor Green
}

function Write-Fail {
    param([string]$Text)
    Write-Host "  [FEHLER] $Text" -ForegroundColor Red
}

function Write-Info {
    param([string]$Text)
    Write-Host "  [i] $Text" -ForegroundColor Gray
}

# ---------------------------------------------------------------------------
# UTF-8-Konsole (Umlaute korrekt darstellen)
# ---------------------------------------------------------------------------
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding             = [System.Text.Encoding]::UTF8
$null = chcp 65001 2>$null

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
Write-Header "SRB MBDT Validierungsengine v1.1 - Setup"
Write-Info "Single Resolution Board - Minimum Bail-in Data Template"
Write-Info "EBA DPM 4.2 konform | B01 - B14 | MBDT 2.1"
Write-Host ""

# ---------------------------------------------------------------------------
# Skriptverzeichnis ermitteln
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Write-Info "Arbeitsverzeichnis: $ScriptDir"

# ---------------------------------------------------------------------------
# Schritt 1: Python pruefen
# ---------------------------------------------------------------------------
Write-Step "Pruefe Python-Installation ..."

$pythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 9)) {
                $pythonCmd = $candidate
                Write-OK "Python $major.$minor gefunden: $candidate"
                break
            }
            else {
                Write-Info "Python $major.$minor zu alt (mindestens 3.9 benoetigt) - naechste Alternative ..."
            }
        }
    }
    catch {
        # Kandidat nicht gefunden - weiter
    }
}

if (-not $pythonCmd) {
    Write-Fail "Kein geeignetes Python (>= 3.9) gefunden."
    Write-Host ""
    Write-Host "  Bitte Python 3.9 oder hoeher installieren:" -ForegroundColor White
    Write-Host "  https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "  Sicherstellen, dass 'Python zum PATH hinzufuegen' angehakt ist." -ForegroundColor White
    Write-Host ""
    exit 1
}

# ---------------------------------------------------------------------------
# Schritt 2: pip pruefen
# ---------------------------------------------------------------------------
Write-Step "Pruefe pip ..."

try {
    $pipVer = & $pythonCmd -m pip --version 2>&1
    Write-OK "pip verfuegbar: $pipVer"
}
catch {
    Write-Fail "pip nicht gefunden. Bitte pip installieren:"
    Write-Host "  $pythonCmd -m ensurepip --upgrade" -ForegroundColor White
    exit 1
}

# ---------------------------------------------------------------------------
# Schritt 3: Virtuelles Environment (optional, empfohlen)
# ---------------------------------------------------------------------------
if (-not $NoVenv) {
    if ($VenvPath -eq "") {
        $VenvPath = Join-Path $ScriptDir "venv"
    }

    Write-Step "Virtuelles Environment pruefen: $VenvPath"

    if (Test-Path (Join-Path $VenvPath "Scripts\python.exe")) {
        Write-OK "Virtuelles Environment bereits vorhanden."
    }
    else {
        Write-Step "Erstelle virtuelles Environment ..."
        try {
            & $pythonCmd -m venv $VenvPath
            Write-OK "venv angelegt unter: $VenvPath"
        }
        catch {
            Write-Fail "Fehler beim Anlegen des venv: $_"
            Write-Info "Fahre ohne venv fort (--NoVenv)."
            $NoVenv = $true
        }
    }

    if (-not $NoVenv) {
        $pythonCmd = Join-Path $VenvPath "Scripts\python.exe"
        Write-Info "Verwende Python aus venv: $pythonCmd"
    }
}
else {
    Write-Info "Virtuelles Environment uebersprungen (-NoVenv)."
}

# ---------------------------------------------------------------------------
# Schritt 4: Abhaengigkeiten installieren
# ---------------------------------------------------------------------------
Write-Step "Installiere Python-Abhaengigkeiten ..."

$requirementsFile = Join-Path $ScriptDir "requirements.txt"

if (Test-Path $requirementsFile) {
    Write-Info "Lese requirements.txt ..."
    $installArgs = @("-m", "pip", "install", "-r", $requirementsFile, "--upgrade")
    if (-not $Force) {
        $installArgs += "--quiet"
    }
    try {
        & $pythonCmd @installArgs
        if ($LASTEXITCODE -ne 0) { throw "pip install fehlgeschlagen (Exit $LASTEXITCODE)" }
        Write-OK "Alle Abhaengigkeiten installiert."
    }
    catch {
        Write-Fail "Fehler bei der Installation: $_"
        exit 1
    }
}
else {
    Write-Info "requirements.txt nicht gefunden - installiere einzeln ..."
    foreach ($pkg in @("pandas>=1.5.0", "openpyxl>=3.0.10")) {
        try {
            & $pythonCmd -m pip install $pkg --upgrade --quiet
            if ($LASTEXITCODE -ne 0) { throw "Exit $LASTEXITCODE" }
            Write-OK "$pkg installiert."
        }
        catch {
            Write-Fail "Fehler bei $pkg : $_"
            exit 1
        }
    }
}

# ---------------------------------------------------------------------------
# Schritt 5: Pflichtdateien pruefen
# ---------------------------------------------------------------------------
Write-Step "Pruefe Projektdateien ..."

$requiredFiles = @(
    "mbdt_validator.py",
    "run_validation.py",
    "rule_catalog.json",
    "field_structure.json"
)

$allPresent = $true
foreach ($f in $requiredFiles) {
    $fp = Join-Path $ScriptDir $f
    if (Test-Path $fp) {
        Write-OK "$f vorhanden."
    }
    else {
        Write-Fail "$f FEHLT! Bitte vollstaendiges Paket entpacken."
        $allPresent = $false
    }
}

if (-not $allPresent) {
    Write-Host ""
    Write-Fail "Einige Pflichtdateien fehlen. Setup abgebrochen."
    exit 1
}

# ---------------------------------------------------------------------------
# Schritt 6: Syntaxpruefung Python-Dateien
# ---------------------------------------------------------------------------
Write-Step "Syntaxpruefung der Python-Dateien ..."

foreach ($pyFile in @("mbdt_validator.py", "run_validation.py")) {
    $fp = Join-Path $ScriptDir $pyFile
    try {
        & $pythonCmd -m py_compile $fp
        if ($LASTEXITCODE -ne 0) { throw "Syntaxfehler in $pyFile" }
        Write-OK "$pyFile - Syntax OK"
    }
    catch {
        Write-Fail "Syntaxfehler in $pyFile : $_"
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Schritt 7: Ausgabeverzeichnis anlegen
# ---------------------------------------------------------------------------
$outputDir = Join-Path $ScriptDir "output"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
    Write-OK "Ausgabeverzeichnis angelegt: $outputDir"
}
else {
    Write-Info "Ausgabeverzeichnis vorhanden: $outputDir"
}

# ---------------------------------------------------------------------------
# Schritt 8: venv-Pfad in Run-Skript speichern (optional)
# ---------------------------------------------------------------------------
$venvConfigFile = Join-Path $ScriptDir ".mbdt_venv_path"
if (-not $NoVenv -and (Test-Path $VenvPath)) {
    $VenvPath | Out-File -FilePath $venvConfigFile -Encoding utf8 -NoNewline
    Write-Info "venv-Pfad gespeichert: $venvConfigFile"
}

# ---------------------------------------------------------------------------
# Abschluss
# ---------------------------------------------------------------------------
Write-Host ""
Write-Header "Setup erfolgreich abgeschlossen"
Write-Host "  Naechster Schritt:" -ForegroundColor White
Write-Host ""
Write-Host "  .\Run-MBDT-Validation.ps1 -Help" -ForegroundColor Green
Write-Host "  .\Run-MBDT-Validation.ps1 -InputXlsx 'MeinTemplate.xlsx' -Entity 'Musterbank AG'" -ForegroundColor Green
Write-Host "  .\Run-MBDT-Validation.ps1 -CsvDir '.\csv_export\' -Entity 'Musterbank AG'" -ForegroundColor Green
Write-Host ""
