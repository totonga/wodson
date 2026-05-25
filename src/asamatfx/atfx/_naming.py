"""Naming utilities for mapping ODS names to SQLite identifiers."""

from __future__ import annotations


def _table_name(entity_name: str) -> str:
    """Convert entity name to SQLite table name."""
    return entity_name.lower()


def _col_name(name: str) -> str:
    """Convert attribute/relation name to SQLite column name."""
    return name.lower()
