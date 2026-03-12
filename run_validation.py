"""
SRB MBDT Validierungsengine — Ausführungsskript
================================================
Verwendung:

  # xlsx-Input (SRB-Original-Template):
  python run_validation.py --input path/to/MBDT_filled.xlsx

  # CSV-Verzeichnis:
  python run_validation.py --csvdir path/to/csv_folder/

  # Einzelne CSV-Datei:
  python run_validation.py --csv path/to/B02.00_TypeA.csv --template B02.00

  # Optionen:
  --output    Pfad der Ausgabedatei  (Standard: MBDT_Fehlerreport_<timestamp>.xlsx)
  --entity    Name der meldenden Entität
  --refdate   Referenzdatum (yyyy-mm-dd)
  --quiet     Nur Fehler/Warnungen ausgeben (kein Detail-Log)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Engine importieren (gleicher Ordner)
sys.path.insert(0, str(Path(__file__).parent))
from mbdt_validator import MBDTValidator


def main():
    parser = argparse.ArgumentParser(
        description="SRB MBDT Validierungsengine (v1.5)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--input",   help="MBDT xlsx-Datei (SRB-Originaltemplate)")
    grp.add_argument("--csvdir",  help="Verzeichnis mit CSV-Dateien (B02.00_TypeA.csv etc.)")
    grp.add_argument("--csv",     help="Einzelne CSV-Datei")
    parser.add_argument("--template", default="B02.00",
                        help="Template-ID für --csv (Standard: B02.00)")
    parser.add_argument("--output",   default="",
                        help="Ausgabepfad der xlsx-Fehlerdatei")
    parser.add_argument("--entity",   default="",
                        help="Name der meldenden Entität (für Deckblatt)")
    parser.add_argument("--refdate",  default="",
                        help="Referenzdatum yyyy-mm-dd (für Deckblatt)")
    parser.add_argument("--de-annex", action="store_true",
                        dest="de_annex",
                        help="DE Country Annex Modus aktivieren (zusätzliche DE-Felder, "
                             "erweiterte Codelisten für Nature of the liability, "
                             "Type of master agreement B03/B04, etc.)")
    parser.add_argument("--quiet",    action="store_true",
                        help="Minimale Konsolenausgabe")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output or f"MBDT_Fehlerreport_{ts}.xlsx"

    validator = MBDTValidator(de_annex=args.de_annex)

    # ── Laden ────────────────────────────────────────────────────────────────
    if args.input:
        if not args.quiet:
            print(f"Lade xlsx: {args.input}")
        templates = validator.load_xlsx(args.input)
        if not args.quiet:
            print(f"  Geladene Templates: {sorted(templates.keys())}")

    elif args.csvdir:
        if not args.quiet:
            print(f"Lade CSV-Verzeichnis: {args.csvdir}")
        templates = validator.load_csv_dir(args.csvdir)
        if not args.quiet:
            print(f"  Geladene Templates: {sorted(templates.keys())}")

    elif args.csv:
        if not args.quiet:
            print(f"Lade CSV: {args.csv} als {args.template}")
        validator.load_single_csv(args.csv, args.template)

    else:
        print("FEHLER: Kein Input angegeben. Nutze --input, --csvdir oder --csv.")
        print("Hilfe: python run_validation.py --help")
        sys.exit(1)

    # ── Validieren ───────────────────────────────────────────────────────────
    if not args.quiet:
        de_hint = " [DE Country Annex]" if args.de_annex else ""
        print(f"\nStarte Validierung ({len(validator.rules)} Regeln){de_hint} …")
    errors = validator.validate()
    summary = validator.get_summary()

    # ── Report ausgeben ──────────────────────────────────────────────────────
    report_path = validator.generate_error_report(
        output_path=output_path,
        entity_name=args.entity,
        reference_date=args.refdate,
    )

    # ── Konsolenausgabe ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"MBDT VALIDIERUNGSERGEBNIS")
    print(f"{'='*60}")
    print(f"Gesamt-Befunde:  {summary['total']}")
    print(f"  Fehler:        {summary['errors']}")
    print(f"  Warnungen:     {summary['warnings']}")
    print(f"\nReport:          {report_path}")

    if not args.quiet and errors:
        print(f"\nTop-Befunde (erste 10):")
        for e in sorted(errors, key=lambda x: (x['severity'] != 'ERROR', x['template']))[:10]:
            icon = "✗" if e['severity'] == 'ERROR' else "⚠"
            print(f"  {icon} [{e['rule_id']}] {e['template']} "
                  f"{'Zeile '+str(e['row']) if e['row'] else '     '} "
                  f"| {e['message'][:70]}")

    # Exit-Code: 1 wenn Fehler vorhanden
    sys.exit(1 if summary['errors'] > 0 else 0)


if __name__ == "__main__":
    main()
