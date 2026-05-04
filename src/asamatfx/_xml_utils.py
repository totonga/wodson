"""XML helper utilities for namespace-aware element lookups."""

from __future__ import annotations

import xml.etree.ElementTree as ET


def _extract_ns(tag: str) -> str | None:
    """Extract namespace URI from a Clark-notation tag like {ns}localname."""
    if tag.startswith("{"):
        return tag[1 : tag.index("}")]
    return None


def _find(parent: ET.Element, tag: str) -> ET.Element | None:
    """Find a child element using the parent's own namespace, with no-namespace fallback."""
    ns = _extract_ns(parent.tag)
    if ns is not None:
        el = parent.find(f"{{{ns}}}{tag}")
        if el is not None:
            return el
    return parent.find(tag)


def _findall(parent: ET.Element, tag: str) -> list[ET.Element]:
    """Find all child elements using the parent's own namespace, with no-namespace fallback."""
    ns = _extract_ns(parent.tag)
    if ns is not None:
        results = parent.findall(f"{{{ns}}}{tag}")
        if results:
            return results
    return parent.findall(tag)


def _text(parent: ET.Element, tag: str) -> str:
    """Get text content of a named child element, or empty string."""
    el = _find(parent, tag)
    if el is not None and el.text is not None:
        return el.text.strip()
    return ""
