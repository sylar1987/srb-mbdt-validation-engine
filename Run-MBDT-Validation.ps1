#Requires -Version 5.1
<#
.SYNOPSIS
    SRB MBDT Validierungsengine v1.4 - Hauptausfuehrungsskript (Windows PowerShell)

.DESCRIPTION
    Fuehrt die Validierung von SRB Minimum Bail-in Data Templates (MBDT 2.1)
    gemaess SRB-Regeln (L1/L2), EBA DPM 4.2 und MREL-Anforderungen durch.
    Unterstuetzt B01 bis B14 als XLSX- oder CSV-Eingabe.
    Ergebnis: mehrblaettiger Excel-Fehlerreport (Deckblatt, Fehlerdetails,
    Zusammenfassung, Regelkatalog).

.PARAMETER InputXlsx
    Pfad zur SRB-Original-XLSX-Template-Datei (einzelne Datei, alle B-Templates).

.PARAMETER CsvDir
    Pfad zu einem Verzeichnis mit CSV-Dateien (Dateiname-Konvention: B02.00_TypeA.csv).

.PARAMETER CsvFile
    Pfad zu einer einzelnen CSV-Datei.

.PARAMETER Template
    Template-ID fuer -CsvFile (Standard: B02.00). Z.B. "B05.01".

.PARAMETER Output
    Ausgabepfad fuer den Fehlerreport. Standard: .\output\MBDT_Fehlerreport_<Zeitstempel>.xlsx

.PARAMETER Entity
    Name der meldenden Einheit (erscheint auf dem Deckblatt). Standard: "Unbekannte Einheit"

.PARAMETER RefDate
    Meldestichtag im Format YYYY-MM-DD. Standard: heutiges Datum.

.PARAMETER DeAnnex
    DE Country Annex Modus aktivieren (zusaetzliche DE-Felder, erweiterte Codelisten
    fuer 'Nature of the liability', 'Type of master agreement' B03/B04 etc.).
    Nur fuer deutsche Institute relevant (BaFin/Bundesbank Meldungen).

.PARAMETER Quiet
    Minimale Konsolenausgabe (nur Fehler und Ergebnis).

.PARAMETER OpenReport
    Oeffnet den Fehlerreport automatisch in Excel nach erfolgreicher Validierung.

.PARAMETER Help
    Zeigt diese Hilfe an.

.EXAMPLE
    .\Run-MBDT-Validation.ps1 -InputXlsx ".\MBDT_Musterbank.xlsx" -Entity "Musterbank AG"

.EXAMPLE
    .\Run-MBDT-Validation.ps1 -CsvDir ".\csv_export" -Entity "Musterbank AG" -RefDate "2025-12-31" -OpenReport

.EXAMPLE
    .\Run-MBDT-Validation.ps1 -CsvFile ".\B02.00_TypeA.csv" -Template "B02.00" -Entity "Testbank"

.EXAMPLE
    .\Run-MBDT-Validation.ps1 -InputXlsx ".\MBDT_DE.xlsx" -Entity "Deutsche Bank AG" -DeAnnex

.EXAMPLE
    .\Run-MBDT-Validation.ps1 -Help

.NOTES
    Voraussetzungen:
      - Python 3.9+
      - pandas >= 1.5.0
      - openpyxl >= 3.0.10
    Einmalig ausfuehren: .\Setup-MBDT.ps1

    Falls das Skript nicht startet:
      Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#>

[CmdletBinding(DefaultParameterSetName = "Xlsx")]
param(
    # ---------- Eingabe ----------
    [Parameter(ParameterSetName = "Xlsx")]
    [string]$InputXlsx = "",

    [Parameter(ParameterSetName = "CsvDir")]
    [string]$CsvDir = "",

    [Parameter(ParameterSetName = "CsvFile")]
    [string]$CsvFile = "",

    [Parameter(ParameterSetName = "CsvFile")]
    [string]$Template = "B02.00",

    # ---------- Ausgabe ----------
    [string]$Output = "",

    # ---------- Metadaten ----------
    [string]$Entity    = "Unbekannte Einheit",
    [string]$RefDate   = "",

    # ---------- Verhalten ----------
    [switch]$DeAnnex,
    [switch]$Quiet,
    [switch]$OpenReport,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# UTF-8-Konsole (Umlaute korrekt darstellen)
# ---------------------------------------------------------------------------
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding             = [System.Text.Encoding]::UTF8
$null = chcp 65001 2>$null

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
function Write-Banner {
    $line = "=" * 70
    Write-Host $line -ForegroundColor Cyan
    Write-Host "  SRB MBDT Validierungsengine v1.4" -ForegroundColor Cyan
    Write-Host "  Single Resolution Board - Minimum Bail-in Data Template 2.1" -ForegroundColor Cyan
    Write-Host "  B01 - B14 | EBA DPM 4.2 | L1/L2/CL/DPM/CROSS-Regeln" -ForegroundColor Cyan
    Write-Host $line -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    if (-not $Quiet) { Write-Host "  >> $Text" -ForegroundColor Yellow }
}

function Write-OK {
    param([string]$Text)
    if (-not $Quiet) { Write-Host "  [OK] $Text" -ForegroundColor Green }
}

function Write-Info {
    param([string]$Text)
    if (-not $Quiet) { Write-Host "  [i] $Text" -ForegroundColor Gray }
}

function Write-Err {
    param([string]$Text)
    Write-Host "  [FEHLER] $Text" -ForegroundColor Red
}

function Show-Help {
    Get-Help $MyInvocation.ScriptName -Detailed
}

# ---------------------------------------------------------------------------
# Hilfe anzeigen
# ---------------------------------------------------------------------------
if ($Help) {
    Show-Help
    exit 0
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
if (-not $Quiet) { Write-Banner }

# ---------------------------------------------------------------------------
# Skriptverzeichnis
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ---------------------------------------------------------------------------
# Python-Interpreter ermitteln
# ---------------------------------------------------------------------------
Write-Step "Suche Python-Interpreter ..."

$pythonCmd = $null

# Pruefen ob venv konfiguriert wurde (durch Setup-MBDT.ps1)
$venvConfigFile = Join-Path $ScriptDir ".mbdt_venv_path"
if (Test-Path $venvConfigFile) {
    $venvPath = (Get-Content $venvConfigFile -Raw).Trim()
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (Test-Path $venvPython) {
        $pythonCmd = $venvPython
        Write-Info "Verwende venv-Python: $pythonCmd"
    }
}

# Fallback: System-Python suchen
if (-not $pythonCmd) {
    foreach ($candidate in @("python", "python3", "py")) {
        try {
            $ver = & $candidate --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 9)) {
                    $pythonCmd = $candidate
                    Write-Info "Verwende System-Python: $candidate ($major.$minor)"
                    break
                }
            }
        }
        catch { }
    }
}

if (-not $pythonCmd) {
    Write-Err "Kein geeignetes Python (>= 3.9) gefunden."
    Write-Host ""
    Write-Host "  Bitte zuerst Setup ausfuehren:" -ForegroundColor White
    Write-Host "  .\Setup-MBDT.ps1" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-OK "Python-Interpreter: $pythonCmd"

# ---------------------------------------------------------------------------
# run_validation.py pruefen
# ---------------------------------------------------------------------------
$runScript = Join-Path $ScriptDir "run_validation.py"
if (-not (Test-Path $runScript)) {
    Write-Err "run_validation.py nicht gefunden unter: $runScript"
    Write-Host "  Bitte sicherstellen, dass alle Projektdateien vorhanden sind." -ForegroundColor White
    exit 1
}

# ---------------------------------------------------------------------------
# Eingabeparameter validieren
# ---------------------------------------------------------------------------
Write-Step "Pruefe Eingabeparameter ..."

# Mindestens eine Eingabequelle muss angegeben sein
if ($InputXlsx -eq "" -and $CsvDir -eq "" -and $CsvFile -eq "") {
    Write-Err "Keine Eingabequelle angegeben."
    Write-Host ""
    Write-Host "  Verwendung:" -ForegroundColor White
    Write-Host "    .\Run-MBDT-Validation.ps1 -InputXlsx 'Datei.xlsx' -Entity 'Musterbank'" -ForegroundColor White
    Write-Host "    .\Run-MBDT-Validation.ps1 -CsvDir '.\csv\' -Entity 'Musterbank'" -ForegroundColor White
    Write-Host "    .\Run-MBDT-Validation.ps1 -CsvFile 'B02.00_TypeA.csv' -Template 'B02.00'" -ForegroundColor White
    Write-Host ""
    Write-Host "  Hilfe: .\Run-MBDT-Validation.ps1 -Help" -ForegroundColor White
    Write-Host ""
    exit 1
}

# XLSX pruefen
if ($InputXlsx -ne "") {
    if (-not (Test-Path $InputXlsx)) {
        Write-Err "XLSX-Datei nicht gefunden: $InputXlsx"
        exit 1
    }
    $InputXlsx = (Resolve-Path $InputXlsx).Path
    Write-OK "Eingabe (XLSX): $InputXlsx"
}

# CSV-Verzeichnis pruefen
if ($CsvDir -ne "") {
    if (-not (Test-Path $CsvDir)) {
        Write-Err "CSV-Verzeichnis nicht gefunden: $CsvDir"
        exit 1
    }
    $CsvDir = (Resolve-Path $CsvDir).Path
    $csvCount = (Get-ChildItem -Path $CsvDir -Filter "*.csv" -ErrorAction SilentlyContinue).Count
    Write-OK "Eingabe (CSV-Verzeichnis): $CsvDir ($csvCount CSV-Dateien gefunden)"
    if ($csvCount -eq 0) {
        Write-Err "Keine CSV-Dateien im Verzeichnis gefunden: $CsvDir"
        Write-Host "  Erwartetes Dateinamenmuster: B02.00_TypeA.csv, B05.01.csv usw." -ForegroundColor White
        exit 1
    }
}

# Einzelne CSV-Datei pruefen
if ($CsvFile -ne "") {
    if (-not (Test-Path $CsvFile)) {
        Write-Err "CSV-Datei nicht gefunden: $CsvFile"
        exit 1
    }
    $CsvFile = (Resolve-Path $CsvFile).Path
    Write-OK "Eingabe (CSV): $CsvFile (Template: $Template)"
}

# ---------------------------------------------------------------------------
# Ausgabepfad bestimmen
# ---------------------------------------------------------------------------
$outputDir = Join-Path $ScriptDir "output"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

if ($Output -eq "") {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $safeEntity = $Entity -replace '[\\/:*?"<>|]', '_'
    $Output = Join-Path $outputDir "MBDT_Fehlerreport_${safeEntity}_${timestamp}.xlsx"
}

Write-OK "Ausgabepfad: $Output"

# ---------------------------------------------------------------------------
# Referenzdatum
# ---------------------------------------------------------------------------
if ($RefDate -eq "") {
    $RefDate = Get-Date -Format "yyyy-MM-dd"
    Write-Info "Referenzdatum (Standard): $RefDate"
}
else {
    # Format pruefen
    if ($RefDate -notmatch "^\d{4}-\d{2}-\d{2}$") {
        Write-Err "Ungaeltiges Datumsformat: '$RefDate'. Erwartet: YYYY-MM-DD"
        exit 1
    }
    Write-OK "Referenzdatum: $RefDate"
}

# ---------------------------------------------------------------------------
# Python-Argumente zusammenstellen
# ---------------------------------------------------------------------------
$pyArgs = @($runScript)

if ($InputXlsx -ne "")  { $pyArgs += @("--input",    $InputXlsx) }
if ($CsvDir    -ne "")  { $pyArgs += @("--csvdir",   $CsvDir)    }
if ($CsvFile   -ne "")  { $pyArgs += @("--csv",      $CsvFile)   }
if ($CsvFile   -ne "")  { $pyArgs += @("--template", $Template)  }

$pyArgs += @("--output",  $Output)
$pyArgs += @("--entity",  $Entity)
$pyArgs += @("--refdate", $RefDate)

if ($DeAnnex) { $pyArgs += "--de-annex" }
if ($Quiet)   { $pyArgs += "--quiet"    }

# ---------------------------------------------------------------------------
# Validierung ausfuehren
# ---------------------------------------------------------------------------
Write-Step "Starte Validierungsengine ..."
Write-Info  "Meldende Einheit : $Entity"
Write-Info  "Referenzdatum    : $RefDate"
Write-Host ""

$startTime = Get-Date

try {
    # PYTHONIOENCODING setzen (Umlaute in Python-Ausgabe korrekt)
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONPATH       = $ScriptDir

    & $pythonCmd @pyArgs

    $exitCode = $LASTEXITCODE
}
catch {
    Write-Err "Unerwarteter Fehler beim Ausfuehren von Python: $_"
    exit 1
}

$elapsed = (Get-Date) - $startTime

# ---------------------------------------------------------------------------
# Ergebnis auswerten
# ---------------------------------------------------------------------------
Write-Host ""

if ($exitCode -eq 0) {
    Write-Host ("=" * 70) -ForegroundColor Green
    Write-Host "  Validierung erfolgreich abgeschlossen" -ForegroundColor Green
    Write-Host ("  Dauer : {0:mm}m {0:ss}s" -f $elapsed) -ForegroundColor Green
    Write-Host "  Report: $Output" -ForegroundColor Green
    Write-Host ("=" * 70) -ForegroundColor Green
    Write-Host ""

    # Pruefen ob Datei existiert
    if (Test-Path $Output) {
        $reportSize = [math]::Round((Get-Item $Output).Length / 1024, 1)
        Write-Info "Dateigroesse: ${reportSize} KB"

        # Optional: Excel oeffnen
        if ($OpenReport) {
            Write-Step "Oeffne Report in Excel ..."
            try {
                Start-Process -FilePath $Output
                Write-OK "Excel gestartet."
            }
            catch {
                Write-Info "Excel konnte nicht automatisch geoeffnet werden."
                Write-Info "Bitte manuell oeffnen: $Output"
            }
        }
        else {
            Write-Info "Tipp: -OpenReport Flag hinzufuegen, um Excel automatisch zu oeffnen."
        }
    }
    else {
        Write-Err "Reportdatei wurde nicht erstellt: $Output"
        exit 1
    }
}
elseif ($exitCode -eq 1) {
    Write-Host ("=" * 70) -ForegroundColor Yellow
    Write-Host "  Validierung abgeschlossen - Fehler gefunden" -ForegroundColor Yellow
    Write-Host ("  Dauer : {0:mm}m {0:ss}s" -f $elapsed) -ForegroundColor Yellow
    Write-Host "  Report: $Output" -ForegroundColor Yellow
    Write-Host ("=" * 70) -ForegroundColor Yellow
    Write-Host ""
    Write-Info "Exit-Code 1 = Validierungsfehler gefunden (normaler Ablauf)."

    if (Test-Path $Output) {
        Write-OK "Fehlerreport erstellt: $Output"
        if ($OpenReport) {
            try { Start-Process -FilePath $Output } catch { }
        }
    }
    # Exit 1 ist kein technischer Fehler - Skript mit 0 beenden
    exit 0
}
else {
    Write-Err "Python-Prozess endete mit Exit-Code $exitCode (unerwarteter Fehler)."
    Write-Host ""
    Write-Host "  Moegliche Ursachen:" -ForegroundColor White
    Write-Host "  - Fehlende Python-Pakete (bitte .\Setup-MBDT.ps1 ausfuehren)" -ForegroundColor White
    Write-Host "  - Beschaedigte oder leere Eingabedatei" -ForegroundColor White
    Write-Host "  - Unbekanntes Template-Format" -ForegroundColor White
    Write-Host ""
    exit $exitCode
}
