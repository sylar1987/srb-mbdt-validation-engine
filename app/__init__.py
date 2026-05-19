"""
SRB MBDT Validierungsengine – modulare App-Architektur (Phase 1).

Diese Package-Struktur entkoppelt Input, Normalisierung, Konfiguration,
Validierung, Reporting und Hilfsfunktionen gemäß Soll-Aufbau Phase 1.
Bestehende Fachlogik aus ``mbdt_validator.py`` bleibt unverändert; die
neuen Module liefern Orchestrierung, typsichere Datenmodelle und
explizite Validatoren.
"""

__version__ = "1.5-phase1"
