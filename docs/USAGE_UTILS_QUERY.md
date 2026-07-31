# utils.query Usage Guide

This document describes the utilities in [../src/wodson/utils/query/__init__.py](../src/wodson/utils/query/__init__.py):

- `ods_to_jaquel`
- `ensure_required_joins`
- `ModelRelationPathFinder`

## 1. Prerequisites

```python
from odsbox.model_cache import ModelCache
from odsbox.proto import ods

from wodson.utils.query import ModelRelationPathFinder, ensure_required_joins, ods_to_jaquel
```

You need an `ods.Model` and a `ModelCache`:

```python
mc = ModelCache(model)
```

## 2. Convert ODS SelectStatement to JAQueL

Use `ods_to_jaquel` to convert a `SelectStatement` into a readable, canonical JAQueL dictionary.

```python
from odsbox.jaquel import jaquel_to_ods

source_query = {
    "AoUnit": {"name": {"$like": "k*"}},
    "$attributes": {"id": 1, "name": 1},
}

_entity, select_statement = jaquel_to_ods(mc.model(), source_query)

jaquel_query = ods_to_jaquel(mc, select_statement)
```

### Important options

- `use_base_names=False` (default): emits application names.
- `use_base_names=True`: emits base names where unambiguous.
- `complement_joins=True` (default): auto-adds required joins before conversion.

```python
jaquel_query = ods_to_jaquel(
    mc,
    select_statement,
    use_base_names=True,
    complement_joins=True,
)
```

### Behavior notes

- The function validates candidate roots by converting generated JAQueL back with `jaquel_to_ods`.
- It returns a candidate whose rebuilt statement equals the input statement.
- If no JAQueL representation is possible, it raises `ValueError`.

## 3. Ensure Required Joins

`ensure_required_joins` complements missing joins in a statement using model relation paths.
It returns a deep-copied statement, so the original input is not mutated.

```python
fixed_statement = ensure_required_joins(mc, select_statement)
```

### What it uses as entity references

The utility inspects these sections in order:

1. `where` conditions
2. `columns`
3. `order_by`
4. `group_by`

It then computes cheapest relation paths from the root reference to all other referenced entities and appends missing joins.

## 4. Find Relation Paths Explicitly

`ModelRelationPathFinder` computes the shortest weighted path between entities.

```python
finder = ModelRelationPathFinder(mc)
path = finder.find_path("AoLocalColumn", "AoMeasurement")
# Example output: ["submatrix", "measurement"]
```

### Weighting strategy

The algorithm is Dijkstra-based with these weights:

- child relations: `1`
- base-name relations: `3`
- regular relations: `13`
- n:m relations: `33` (strongly penalized)

Lower total weight is preferred.

## 5. Typical Workflow


### Create Jaquel query

```python
# 1) Start from an existing SelectStatement
statement = select_statement

# 2) Convert to JAQueL
query = ods_to_jaquel(mc, statement, use_base_names=False)
```

### Add joins to SelectStatement

```python
# 1) Start from an existing SelectStatement
statement = select_statement

# 2) Ensure required joins are present
fixed_statement = ensure_required_joins(mc, statement)
```

## 6. Testing Commands

```powershell
uv run pytest -q
uv run ruff check .
uv run mypy ods_to_jaquel.py tests/test_utils_query.py tests/test_model_relation_path_finder.py
```

## 7. Related Tests

- [tests/test_utils_query.py](../tests/test_utils_query.py): end-to-end round-trip and join complement behavior.
- [tests/test_model_relation_path_finder.py](../tests/test_model_relation_path_finder.py): direct unit tests for path finding and join enrichment behavior.
