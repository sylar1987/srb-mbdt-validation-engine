"""Serialisiert ``CanonicalFact``-Listen als XML-Dokument.

MVP: ein einfaches, namensraumiges XML mit ``<facts>``-Root, je Fakt ein
``<fact>``-Element mit Attributen für technische Identifier, Kontext,
Einheit und Dimensionen.
"""

from __future__ import annotations

import os
from typing import Iterable
from xml.etree import ElementTree as ET

from app.models import CanonicalFact, MetadataPackage


class XmlWriter:
    NAMESPACE = "https://srb.example/mbdt/phase3"

    def render(
        self,
        facts: Iterable[CanonicalFact],
        package: MetadataPackage,
        run_id: str = "",
    ) -> str:
        ET.register_namespace("", self.NAMESPACE)
        root = ET.Element(f"{{{self.NAMESPACE}}}facts")
        root.set("framework_version", package.framework_version)
        root.set("package_id", package.package_id)
        if run_id:
            root.set("run_id", run_id)

        dp_index = {dp.datapoint_id: dp for dp in package.datapoints}

        for fact in facts:
            elem = ET.SubElement(root, f"{{{self.NAMESPACE}}}fact")
            elem.set("fact_id", fact.fact_id)
            elem.set("datapoint_id", fact.datapoint_id)
            dp = dp_index.get(fact.datapoint_id)
            if dp is not None and dp.technical_identifier:
                elem.set("qname", dp.technical_identifier)
            elem.set("template_id", fact.template_id)
            elem.set("field_code", fact.field_code)
            elem.set("data_type", fact.data_type)
            if fact.unit:
                elem.set("unit", fact.unit)

            ctx = ET.SubElement(elem, f"{{{self.NAMESPACE}}}context")
            if fact.context.entity:
                ctx.set("entity", fact.context.entity)
            if fact.context.reference_date:
                ctx.set("reference_date", fact.context.reference_date)
            if fact.context.period_start:
                ctx.set("period_start", fact.context.period_start)
            if fact.context.period_end:
                ctx.set("period_end", fact.context.period_end)

            for dim_id, dim_val in sorted(fact.dimensions.items()):
                d = ET.SubElement(elem, f"{{{self.NAMESPACE}}}dimension")
                d.set("id", dim_id)
                d.set("value", dim_val)

            value_el = ET.SubElement(elem, f"{{{self.NAMESPACE}}}value")
            value_el.text = "" if fact.value is None else str(fact.value)

            audit = ET.SubElement(elem, f"{{{self.NAMESPACE}}}audit")
            audit.set("source_row", str(fact.source_row))
            if fact.source_file:
                audit.set("source_file", fact.source_file)

        ET.indent(root, space="  ")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
            root, encoding="unicode"
        )

    def write(
        self,
        path: str,
        facts: Iterable[CanonicalFact],
        package: MetadataPackage,
        run_id: str = "",
    ) -> str:
        xml = self.render(facts, package, run_id=run_id)
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(xml)
        return path
