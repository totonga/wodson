"""Model-based entity and attribute resolution for DataFrame → DataMatrix conversion."""

from __future__ import annotations

import odsbox.proto.ods_pb2 as ods
from odsbox.model_cache import ModelCache


def parse_column_prefix(col_name: str, separator: str = ".") -> tuple[str | None, str]:
    """Split ``'Entity.Attribute'`` into ``(entity_part, attribute_part)``.

    Returns ``(None, col_name)`` when the separator is absent.
    """
    if separator in col_name:
        entity_part, _, attr_part = col_name.partition(separator)
        return entity_part, attr_part
    return None, col_name


def resolve_entity_and_columns(
    columns: list[str],
    model_cache: ModelCache,
    entity_name: str | None,
    separator: str = ".",
) -> tuple[ods.Model.Entity, list[tuple[str, str, int]]]:
    """Map DataFrame column names to ``(entity, [(attr_name, base_name, data_type)])``.

    Entity and attribute lookup is delegated to :class:`~odsbox.model_cache.ModelCache`,
    which supports case-insensitive matching by application name **or** base name for
    both entity and attribute lookups.

    Rules:

    * When *entity_name* is given it wins over any ``Entity.Attribute`` prefix.
      Plain column names are resolved directly as attribute names.
    * When *entity_name* is ``None``, every column must carry an
      ``Entity.Attribute`` prefix and all prefixes must resolve to the
      **same** entity.

    Args:
        columns:      List of DataFrame column names to resolve.
        model_cache:  :class:`~odsbox.model_cache.ModelCache` wrapping the ODS
                      application model.
        entity_name:  Explicit entity application or base name.  When provided,
                      any prefix in the column names is ignored.
        separator:    Separator character for ``'Entity.Attribute'`` names.

    Returns:
        Tuple of ``(entity, [(attr_app_name, attr_base_name, data_type), ...])``.

    Raises:
        ValueError: If no columns are given, the entity is not found, an
                    attribute is not found, or columns resolve to different
                    entities when *entity_name* is ``None``.
    """
    if not columns:
        raise ValueError("No columns provided.")

    resolved_attrs: list[tuple[str, str, int]] = []
    entity: ods.Model.Entity | None = None

    for col in columns:
        parsed_entity_name, attr_name_raw = parse_column_prefix(col, separator)

        if entity_name is not None:
            ent_lookup = entity_name
            attr_lookup = attr_name_raw
        else:
            if parsed_entity_name is None:
                raise ValueError(
                    f"Column '{col}' has no entity prefix. "
                    "Use 'Entity.Attribute' format or provide entity_name parameter."
                )
            ent_lookup = parsed_entity_name
            attr_lookup = attr_name_raw

        # ModelCache.entity() raises ValueError with suggestions when not found
        resolved_entity = model_cache.entity(ent_lookup)

        if entity is None:
            entity = resolved_entity
        elif resolved_entity.aid != entity.aid:
            raise ValueError(
                f"Column '{col}' resolves to entity '{resolved_entity.name}', "
                f"but previous columns resolved to '{entity.name}'. "
                "All columns must belong to the same entity."
            )

        # ModelCache.attribute() raises ValueError with suggestions when not found
        attr = model_cache.attribute(entity, attr_lookup)
        resolved_attrs.append((attr.name, attr.base_name, int(attr.data_type)))

    assert entity is not None  # satisfied: columns is non-empty
    return entity, resolved_attrs
