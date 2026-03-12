# SRB MBDT Validierungsengine v1.5

**Single Resolution Board – Minimum Bail-in Data Template Validator**
MBDT 2.1 | B01–B14 | EBA DPM 4.2 | L1/L2/CL/DPM/CROSS-Regeln | **394 Regeln** | DE Country Annex

---

## Schnellstart (Windows PowerShell)

### 1. Einmaliges Setup (Python-Pakete installieren)

```powershell
# Falls Skripte noch nicht ausführbar sind:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Setup ausführen:
.\Setup-MBDT.ps1
```

### 2. Validierung ausführen

```powershell
# XLSX-Eingabe (SRB-Originaltemplate):
.\Run-MBDT-Validation.ps1 -InputXlsx ".\MeinTemplate.xlsx" -Entity "Musterbank AG"

# CSV-Verzeichnis (exportierte CSVs, Dateiname: B02.00_TypeA.csv usw.):
.\Run-MBDT-Validation.ps1 -CsvDir ".\csv_export" -Entity "Musterbank AG" -RefDate "2025-12-31"

# Einzelne CSV-Datei:
.\Run-MBDT-Validation.ps1 -CsvFile ".\B02.00_TypeA.csv" -Template "B02.00" -Entity "Testbank"

# Report automatisch in Excel öffnen:
.\Run-MBDT-Validation.ps1 -InputXlsx ".\MeinTemplate.xlsx" -Entity "Musterbank AG" -OpenReport
```

### 3. Hilfe anzeigen

```powershell
.\Run-MBDT-Validation.ps1 -Help
```

---

## Voraussetzungen

| Anforderung | Version |
|-------------|---------|
| Python      | >= 3.9  |
| pandas      | >= 1.5.0 |
| openpyxl    | >= 3.0.10 |
| PowerShell  | >= 5.1 (vorinstalliert ab Windows 8) |

Python herunterladen: https://www.python.org/downloads/
→ Beim Installer „Add Python to PATH" aktivieren.

---

## Projektstruktur

```
MBDT_Validierungsengine_v1.1/
│
├── Run-MBDT-Validation.ps1   ← Hauptskript (hier starten)
├── Setup-MBDT.ps1            ← Einmaliges Setup
├── requirements.txt          ← Python-Abhängigkeiten
│
├── mbdt_validator.py         ← Validierungsengine (1839 Zeilen)
├── run_validation.py         ← CLI-Wrapper (120 Zeilen)
├── rule_catalog.json         ← 230 Regeln + 24 Codelisten
├── field_structure.json      ← 151 Felder aller B-Templates
│
└── output/                   ← Fehlerreporte (automatisch angelegt)
    └── MBDT_Fehlerreport_<Einheit>_<Zeitstempel>.xlsx
```

---

## Regelumfang

| Ebene | Anzahl | Beschreibung |
|-------|--------|--------------|
| L1    | 54     | SRB Pflichtfelder (Annex II) |
| L2    | 57     | SRB Konsistenzregeln (Annex II) |
| CL    | 26     | Codelisten-Prüfungen (24 Codelisten, 126 Werte) |
| DPM   | 83     | EBA DPM 4.2 Datentypen & Formate |
| CROSS | 10     | Cross-Template + MREL-Konsistenz |
| **Gesamt** | **394** | |

---

## Fehlerreport (Excel-Ausgabe)

Der Report enthält 4 Tabellenblätter:

1. **Deckblatt** – Metadaten (Einheit, Datum, Engine-Version, Regelzähler)
2. **Fehlerdetails** – Alle Befunde: Template, Zeile, Feld, Regelcode, Schwere, Beschreibung
3. **Zusammenfassung** – Befunde pro Template und Regelkategorie (pivot-ähnlich)
4. **Regelkatalog** – Alle 230 implementierten Regeln mit Beschreibung

---

## CSV-Eingabeformat

- Trennzeichen: **Semikolon (`;`)** (SRB MBDT Annex II §1.1)
- Encoding: **UTF-8 with BOM** (`utf-8-sig`) für Windows-Excel-Kompatibilität
- Dateinamenmuster: `B02.00_TypeA.csv`, `B02.00_TypeB.csv`, `B90.00.csv`

---

## Quellen

- SRB MBDT 2.1 Annex I (Tabellenstruktur): https://www.srb.europa.eu/system/files/media/document/2024-11-05_Annex-I_Minimum-Bail-in-Data-Template-%28MBDT%29-tables.xlsx
- SRB MBDT 2.1 Annex II (Validierungsregeln): https://www.srb.europa.eu/system/files/media/document/2024-11-05_Annex-II_Facilititating-Instructions_Validation-rules.xlsx
- EBA DPM 4.2: https://www.eba.europa.eu/risk-analysis-and-data/data-point-model-and-taxonomies

---

## DE Country Annex Modus

Für deutsche Institute kann der **DE Country Annex** aktiviert werden. Dies ergänzt:
- **19 zusätzliche DE-spezifische Felder** (B02.00, B03.00, B04.00, B90.00)
- **8 zusätzliche CL-Regeln** (`v_CL_DE_0001`–`v_CL_DE_0008`) mit DE-spezifischen Codelisten
- Erweiterte Codeliste für *Nature of the liability* (inkl. DE_Silent partnership contribution, DE_Profit participation right)
- Erweiterte Codeliste für *Balance sheet item according to national GAAP* (9 Werte)
- Neue Codelisten für *Type of master agreement* (B03.00 + B04.00) und ISDA Resolution Stay (B04.00)

```powershell
# DE Country Annex Modus aktivieren:
.\Run-MBDT-Validation.ps1 -InputXlsx ".\MBDT_DE.xlsx" -Entity "Deutsche Bank AG" -DeAnnex
```

Quelle: SRB DE Country Annex (2024-11-05): https://www.srb.europa.eu/en/content/minimum-bail-data-template

