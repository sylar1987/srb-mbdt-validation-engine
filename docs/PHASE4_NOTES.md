# Phase 4 – Operationalisierung und Governance (MVP)

Status: **Initial-MVP umgesetzt** auf Basis von Phase 3
(`phase3-metadata-export-pipeline`). Branch: `phase4-governance-operations`.

Phase 4 macht aus dem technischen Phase-3-MVP eine kontrollierbare,
auditierbare und versionsfähige Plattform. Dieser Stand setzt den
priorisierten Initial-Scope aus
`phase4_operationalisierung_governance_erweiterung.md` um.

## Scope des Initial-MVP

Neu sind drei Pakete und eine erweiterte Dokumentation:

### `app/governance/`

- `release_registry.py` – `ReleaseRegistry` mit `ReleaseRecord`,
  `ReleaseStatus`, deterministischer Auflösung über Reporting-Stichtag
  und Überlappungsschutz für gleichzeitig aktive Releases.
- `approval_workflow.py` – `ApprovalWorkflow` mit Statusmodell
  `imported → validated → reviewed → approved` plus `rejected` und
  `deprecated`. Übergänge sind strikt; `ensure_approved` ist der
  Hard-Gate gegen stille produktive Nutzung.
- `rule_review.py` – `RuleReviewRegistry`, `RuleReview`,
  `RuleReviewStatus`, `RuleTestStatus`, fachlesbare `rule_summary`,
  `diff_rules` zur Erkennung regressionsrelevanter Regeländerungen.
- `override_registry.py` – `OverrideRegistry` und `OverrideEntry` für
  kontrollierte fachliche Overrides; Pflichtfelder Grund, Autor,
  Gültigkeitsfenster; Revocation mit Audit-Log.
- `change_control.py` – `ChangeControlReport` aggregiert Phase-3-
  `PackageDelta`, Rule-Diff und betroffene Templates/Codelists und
  leitet daraus die nötigen Freigaben ab.

### `app/operations/`

- `run_history.py` – Append-only `RunHistory` mit optionaler
  JSON-Lines-Persistenz. Verknüpft Run-ID, Submission, Reporting-Datum,
  Metadata-/Rule-Version, Input-Hash, Artefakte, Fehler/Warnings und
  Fehlerklassen.
- `submission_registry.py` – `SubmissionRegistry` mit Status,
  Reporting-Datum, Framework-Version, Artefaktanhang; Terminalstatus
  `accepted` ist gegen unbeabsichtigte Rückkehr geschützt,
  `resubmitted` ist explizit erlaubt.
- `resubmission_tracker.py` – `ResubmissionTracker` verknüpft
  Resubmissions mit Ursprungslauf, Grund (Pflicht) und Änderungen.
- `monitoring.py` – `OperationsMonitor` mit aggregiertem
  `MonitoringSnapshot` (Runs nach Status, Fehlerklassen, Erfolgsrate)
  und `top_error_classes` für Priorisierung.
- `audit_query.py` – `AuditQuery` als schreibgeschützte Sicht über
  Run/Submission/Resubmission, mit `run_detail`,
  `submission_history`, `search_runs`.

### `app/quality/`

- `export_conformance.py` – `ExportConformanceChecker` über
  Phase-3-Exportverzeichnisse. Liefert kontrollierte Findings:
  Pflichtfelder in `metadata.json`, fehlende `filing_indicators` oder
  `taxonomy_reference`, fehlendes `report.json` (OIM-Hinweis),
  Parsefehler im Manifest. Kein harter OIM-Killer.
- `metadata_acceptance.py` – `MetadataAcceptanceChecker` als
  Vorgate für den Approval-Workflow: framework_version,
  Datapoint-/Template-Minimum, unbekannte Codelist-Referenzen,
  nicht übersetzbare Regeln.
- `rule_test_generator.py` – `generate_rule_test_requirements`
  erzeugt Positiv-/Negativ-/Condition-False-Anforderungen je Regel;
  nicht übersetzbare Regeln werden als „manuell" markiert.
- `regression_suite.py` – `RegressionSuite` mit `RegressionCase`,
  `RegressionRunResult`, Summary inkl. fehlender Ausführungen.

### Tests

- `tests/test_phase4_governance.py` (27 Tests)
- `tests/test_phase4_operations.py` (13 Tests)
- `tests/test_phase4_quality.py` (13 Tests)
- `tests/test_phase4_hardening.py` (22 Tests, Folge-Härtung)
- `tests/test_utils_hashing.py` (15 Tests)

Bestehende Phase-1- bis Phase-3-Tests bleiben unverändert grün.
Gesamt 239 Tests.

## Was der MVP konkret unterstützt

- Mehrere Framework- und Package-Versionen lassen sich parallel
  registrieren; pro Reporting-Stichtag wird deterministisch die
  passende, freigegebene Version aufgelöst.
- Ein Package muss explizit den Pfad
  `imported → validated → reviewed → approved` durchlaufen, bevor
  `ensure_approved` für produktive Nutzung greift. Approval und
  Rejection erfordern Begründung und Akteur.
- Regeländerungen werden je `(rule_id, fingerprint)` gemerkt; ein
  Review läuft nicht stillschweigend auf einen geänderten Regelkörper
  mit, sondern wird ungültig.
- Fachliche Overrides erfordern Grund, Autor und Gültigkeit; Revocation
  ist nachvollziehbar.
- ChangeControlReports fassen Package-Deltas, Rule-Diffs und
  betroffene Artefakte zusammen und nennen die erforderlichen
  Review-Schritte.
- Jeder Lauf kann mit Submission, Reporting-Datum, Metadata-/Rule-
  Version und Input-Hash protokolliert werden, optional persistent
  als JSON-Lines.
- Resubmissions sind mit Ursprungslauf, Grund und Änderungen verknüpft.
- Audit-Queries beantworten typische Fragen ohne erneuten Komplettlauf.
- Exportverzeichnisse aus Phase 3 werden konformitätsgeprüft und
  zeigen OIM-Lücken (`report.json`, `filing_indicators`,
  `taxonomy_reference`) als kontrollierte Findings.
- Für jede Regel werden Testanforderungen generiert; nicht
  übersetzbare Regeln werden als manuelle Testarbeit markiert.

## Nicht-Ziele (bewusst offen gelassen)

- Kein Enterprise-UI, keine Workflow-Engine; Statusmodelle leben im
  Code und in Artefakten.
- Keine produktive OIM-Vollvalidierung — Conformance-Checks markieren
  Lücken, ohne ein gültiges xBRL-CSV im strengen OIM-Sinn zu erzwingen.
- Keine echten regulatorischen Einreichungen.
- Kein externer Paketdownload; `app/integrations/` wurde im MVP
  bewusst nicht eingeführt, weil ohne echte externe Anbindung nur
  Not-Implemented-Stubs entstanden wären, ohne fachlichen Wert. Wird
  in der nächsten Phase-4-Iteration auf Basis eines konkreten
  Paketszenarios geöffnet.
- Keine Regressionssuite mit echten Submissions; der MVP liefert nur
  das Modell.
- Keine zweite Reporting-Domäne; Gap-Analyse folgt in einer späteren
  Iteration.
- Keine Anbindung der neuen Governance-Layer an `app/runner.py` oder
  `app/main.py` — der Aufruf erfolgt heute explizit aus
  Anwendungscode/Tests. Eine Engine-Integration ist ein Folgeschritt
  (siehe „Offene Punkte").

## Folge-Härtung nach Fix-Commit `deeffe9`

Über den Review-Fix hinaus wurden die folgenden Phase-4-Punkte umgesetzt,
ohne Phase-3-Pfade umzubauen:

- **Zentrale Hashing-Hilfe** (`app/utils/hashing.py`):
  - `hash_bytes`, `hash_text`, `hash_file`, `hash_directory`,
    `hash_object`, `hash_iterable` mit stabilem, kanonischem JSON
    (`sort_keys`, kompakte Separatoren) und chunked File-Read.
  - Verzeichnis-Hash sortiert nach POSIX-Pfad und mixt Dateinamen mit,
    sodass Umbenennungen den Hash ändern.
  - 15 dedizierte Tests.
- **RunHistory härten** (`app/operations/run_history.py`):
  - Append-Schreibvorgänge sind durch `threading.RLock` serialisiert und
    auf POSIX zusätzlich durch `fcntl.flock` zwischen Prozessen geschützt.
  - `flush + os.fsync` nach jedem Eintrag, damit Crash-Resistenz gegeben
    ist.
  - Neuer Status `RunStatus.ABANDONED`.
  - `find_orphan_runs()` als reine Diagnose, `mark_orphans_failed(...)`
    schließt offene Runs kontrolliert mit Reason/Actor und schreibt ein
    `recovery`-Event in die JSONL-Persistenz.
- **ResubmissionTracker referenziell härten**
  (`app/operations/resubmission_tracker.py`):
  - `record_checked(...)` und freistehende `validate_resubmission(...)`
    prüfen Existenz und Konsistenz gegen `RunHistory` und
    `SubmissionRegistry` (origin/new run, Submission, offener Origin,
    optional Submission-Status `resubmitted`).
  - Bestehende `record(...)` bleibt unverändert verfügbar — kein hartes
    Brechen freier Aufrufer.
- **Acceptance-Gate typisieren**
  (`app/governance/approval_workflow.py`):
  - Neues `Protocol AcceptanceReportLike` (runtime-checkable) statt
    `Any` für `acceptance_report`. Kein zyklischer Import zu
    `app.quality.metadata_acceptance`.
  - `isinstance`-Check liefert klaren `TypeError` statt stiller Annahme.
- **EngineGate-Service** (`app/governance/engine_gate.py`):
  - Bündelt `ReleaseRegistry.resolve` + `ApprovalWorkflow.status` +
    `MetadataAcceptanceChecker.check` zu einer auditierbaren
    `GateDecision`.
  - Modi `enforce` (Default, hart blockierend) und `warn` (Findings
    werden in `decision.warnings` markiert, niemals stillgeschluckt).
  - Aufruferseitig integrierbar; **noch nicht** in
    `ValidationEngine.run` verdrahtet — bewusst.
- **Monitoring offene/abandoned Runs**
  (`app/operations/monitoring.py`):
  - `MonitoringSnapshot` mit `open_runs`, `abandoned_runs`,
    `blocked_runs`.
  - `OperationsMonitor.orphan_run_ids()` direkter Draht zur Recovery.
- **RegressionSuite-Vergleich**
  (`app/quality/regression_suite.py`):
  - `RegressionSuite.evaluate(case_id, actual_error_count, actual_status)`
    vergleicht gegen `expected_status`/`expected_error_count` und setzt
    `status` automatisch (`passed`/`failed`) inkl. Diagnostik in
    `notes`. `record_result` bleibt für manuelle Pfade verfügbar.

## Behobene Review-Findings aus PR #5

- **ReleaseRegistry.resolve**: Framework-spezifische Releases haben jetzt
  strikten Vorrang vor generischen (`framework_version=""`). Generic dient
  nur als Fallback, wenn keine spezifische Variante für den Stichtag
  freigegeben ist. Overlap-Check ist konsistent: Generic und spezifische
  Releases kollidieren nicht, gleichartige Generic/Generic und
  Specific/Specific desselben Frameworks dagegen schon.
- **RuleReview-Fingerprint**: `_fingerprint` und `diff_rules` teilen sich
  jetzt dasselbe Feldset `_RULE_COMPARABLE_FIELDS` inklusive `message`.
  Eine reine Message-Änderung verwirft den Review.
- **SubmissionRegistry-State-Machine**: Explizite Übergangsmap mit
  `REJECTED` als Terminalstatus. `REJECTED → DRAFT → ACCEPTED` ist
  ausgeschlossen; Korrekturen erfordern eine neue Submission-ID.
  `RESUBMITTED` bleibt explizite Ausnahme aus `ACCEPTED` heraus.
- **OverrideRegistry.find_for_target**: Widerrufene Overrides werden
  standardmäßig ausgeblendet, auch wenn kein `reporting_date` übergeben
  wird. Über `include_revoked=True` lässt sich der Audit-Blick explizit
  öffnen.
- **Approval + Acceptance-Gate**: `transition(..., acceptance_report=...)`
  blockt eine `APPROVED`-Transition, wenn der Report Errors enthält.
  Convenience `approve_if_accepted(...)` macht das Gate zu einem
  expliziten Codeschritt; die `acceptance_report.to_dict()` wandert in
  die Event-Metadaten und ist damit auditierbar.
- **Reason-Pflicht für DEPRECATED**: Übergang nach `DEPRECATED` erzwingt
  jetzt einen Grund analog zu `APPROVED`/`REJECTED`.

## Offene Punkte / Risiken

- **Verdrahtung in `ValidationEngine.run`**: `EngineGate` existiert und
  ist isoliert testbar, ist aber bewusst noch nicht im Default-Pfad der
  Engine eingehängt. Vor der Aktivierung braucht es eine fachliche
  Entscheidung über Modus (`enforce` vs. `warn`) je Umgebung.
- **Automatischer Run-Lifecycle**: `RunHistory.start/complete` wird
  heute nur explizit aus Test/Anwendungscode aufgerufen. Eine Engine-
  seitige Auto-Protokollierung (Run-ID, Metadata-/Rule-Version,
  Artefakte) steht aus.
- **Persistenzmodell** (Entscheidung A im Konzept): JSON-Lines ist nun
  per Lock + fsync abgesichert, bleibt aber index-frei. SQLite/DuckDB
  bleibt offene Option für hohe Run-Zahlen.
- **OIM-Tiefe** (Entscheidung C): MVP liefert Findings, kein echter
  OIM-Validator. Folge-Iteration wählt einen konkreten Pilotreport.
- **Zweite Domäne** (Entscheidung D): noch nicht angefasst.
- **Integrationsschicht**: `app/integrations/` ist nicht angelegt;
  bei Einführung muss klar sein, wo der Paket-Eingang läuft und wie
  Quellsignaturen geprüft werden.
- **Rule-Review-Workflow**: Reviewer und Approver sind heute freie
  Strings — vor produktivem Einsatz braucht es ein Identitätsmodell.
- **Hash-Hilfe vollständig adoptieren**: `app/utils/hashing.py` steht
  bereit; eine spätere, nicht-invasive Migration von
  `MetadataPackage.content_hash` und ähnlichen lokalen
  `hashlib.sha256`-Aufrufen auf `hash_object` ist sinnvoll, sobald ein
  konsistenter Hash-Vertrag dokumentiert ist.
- **Regressionssuite-Datenbasis**: `RegressionSuite.evaluate` vergleicht
  jetzt tatsächlich gegen Expectations — echte Submission-Fixtures als
  Cases fehlen aber weiterhin.
- **UI / externe Workflow-Engine**: bewusst nicht vorgesehen; Phase 4
  bleibt headless.
- **Echte regulatorische Submissions**: weiterhin außerhalb des Scopes.

## Empfohlene nächste Schritte

1. ChangeControlReport im Approval-Pfad verpflichtend machen.
2. `ValidationEngine.run` an `RunHistory` koppeln, Run-ID,
   Metadata-/Rule-Version und Artefakte automatisch protokollieren.
3. Pilot-Submission auswählen und gegen
   `ExportConformanceChecker` schärfen (echtes
   `report.json`/Filing-Indicator).
4. Persistenzmodell (Entscheidung A) konkret entscheiden.
5. Erstes echtes Technical Package inventarisieren und ggf.
   `app/integrations/` aufsetzen.
