"""CLI-Einstiegspunkt der modularen App.

Die historische CLI ``run_validation.py`` bleibt unverändert nutzbar. Diese
Variante ist die neue, modulare Variante (``python -m app.main``) – sie
arbeitet ausschließlich über ``Runner`` und liefert dasselbe Verhalten.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Repo-Root in sys.path aufnehmen, damit ``mbdt_validator`` importierbar bleibt.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.runner import Runner
from app.settings import EngineSettings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SRB MBDT Validierungsengine (modulare CLI – Phase 1)",
    )
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--input", help="MBDT xlsx-Datei (SRB-Originaltemplate)")
    grp.add_argument("--csvdir", help="Verzeichnis mit CSV-Dateien")
    grp.add_argument("--csv", help="Einzelne CSV-Datei")
    parser.add_argument("--template", default="B02.00")
    parser.add_argument("--output", default="")
    parser.add_argument("--entity", default="")
    parser.add_argument("--refdate", default="")
    parser.add_argument("--de-annex", dest="de_annex", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output or f"MBDT_Fehlerreport_{ts}.xlsx"

    runner = Runner(EngineSettings(
        de_annex=args.de_annex,
        entity_name=args.entity,
        reference_date=args.refdate,
        quiet=args.quiet,
    ))

    if args.input:
        runner.load_xlsx(args.input)
    elif args.csvdir:
        runner.load_csv_dir(args.csvdir)
    elif args.csv:
        runner.load_single_csv(args.csv, args.template)

    summary = runner.validate()
    report = runner.write_report(output_path)

    if not args.quiet:
        print(f"\nGesamt-Befunde: {summary.total}")
        print(f"  Fehler:       {summary.errors}")
        print(f"  Warnungen:    {summary.warnings}")
        print(f"Report:         {report}")

    return 1 if summary.errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
