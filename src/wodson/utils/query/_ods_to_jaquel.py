"""Convert ASAM ODS :class:`SelectStatement` messages back into JAQueL queries.

The odsbox package ships :func:`odsbox.jaquel.jaquel_to_ods` which converts a
JAQueL query (a ``dict``) into an ODS ``SelectStatement``. This module implements
the inverse direction. There is no single canonical JAQueL representation for a
given ``SelectStatement``; this converter emits a readable canonical form and
guarantees semantic round-trip stability::

    jaquel_1 -> select_1 -> jaquel_2 -> select_2   =>   select_1 == select_2

To achieve that guarantee, every candidate root entity is verified by feeding the
generated JAQueL back through :func:`jaquel_to_ods` and comparing the result with
the input ``SelectStatement``. The most readable verified candidate is returned.
Constructs that cannot be expressed in JAQueL raise a :class:`ValueError`.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from odsbox.jaquel import jaquel_to_ods
from odsbox.model_cache import ModelCache
from odsbox.proto import ods

_OperatorEnum = ods.SelectStatement.ConditionItem.Condition.OperatorEnum
_ConjuctionEnum = ods.SelectStatement.ConditionItem.ConjuctionEnum
_JoinTypeEnum = ods.SelectStatement.JoinItem.JoinTypeEnum
_OrderEnum = ods.SelectStatement.OrderByItem.OrderEnum

# Operators that map to a single JAQueL operator keyword.
_OP_TO_JAQUEL: dict[int, str] = {
    _OperatorEnum.OP_NEQ: "$neq",
    _OperatorEnum.OP_LT: "$lt",
    _OperatorEnum.OP_GT: "$gt",
    _OperatorEnum.OP_LTE: "$lte",
    _OperatorEnum.OP_GTE: "$gte",
    _OperatorEnum.OP_INSET: "$in",
    _OperatorEnum.OP_NOTINSET: "$notinset",
    _OperatorEnum.OP_LIKE: "$like",
    _OperatorEnum.OP_NOTLIKE: "$notlike",
    _OperatorEnum.OP_BETWEEN: "$between",
}

# Case-insensitive operator variants map back to their base operator plus the
# ``"$options": "i"`` flag.
_CI_TO_BASE: dict[int, int] = {
    _OperatorEnum.OP_CI_EQ: _OperatorEnum.OP_EQ,
    _OperatorEnum.OP_CI_NEQ: _OperatorEnum.OP_NEQ,
    _OperatorEnum.OP_CI_LT: _OperatorEnum.OP_LT,
    _OperatorEnum.OP_CI_GT: _OperatorEnum.OP_GT,
    _OperatorEnum.OP_CI_LTE: _OperatorEnum.OP_LTE,
    _OperatorEnum.OP_CI_GTE: _OperatorEnum.OP_GTE,
    _OperatorEnum.OP_CI_INSET: _OperatorEnum.OP_INSET,
    _OperatorEnum.OP_CI_NOTINSET: _OperatorEnum.OP_NOTINSET,
    _OperatorEnum.OP_CI_LIKE: _OperatorEnum.OP_LIKE,
    _OperatorEnum.OP_CI_NOTLIKE: _OperatorEnum.OP_NOTLIKE,
}

_AGG_TO_JAQUEL: dict[int, str] = {
    ods.AggregateEnum.AG_COUNT: "$count",
    ods.AggregateEnum.AG_DCOUNT: "$dcount",
    ods.AggregateEnum.AG_MIN: "$min",
    ods.AggregateEnum.AG_MAX: "$max",
    ods.AggregateEnum.AG_AVG: "$avg",
    ods.AggregateEnum.AG_STDDEV: "$stddev",
    ods.AggregateEnum.AG_SUM: "$sum",
    ods.AggregateEnum.AG_DISTINCT: "$distinct",
    ods.AggregateEnum.AG_VALUES_POINT: "$point",
    ods.AggregateEnum.AG_INSTANCE_ATTRIBUTE: "$ia",
}

_ARRAY_FIELDS = (
    "string_array",
    "long_array",
    "float_array",
    "boolean_array",
    "byte_array",
    "double_array",
    "longlong_array",
)


class _Unsupported(Exception):
    """Raised internally when a candidate root cannot express the statement."""


class _Leaf:
    __slots__ = ("condition",)

    def __init__(self, condition: ods.SelectStatement.ConditionItem.Condition) -> None:
        self.condition = condition


class _Not:
    __slots__ = ("child",)

    def __init__(self, child: Any) -> None:
        self.child = child


class _And:
    __slots__ = ("children", "explicit")

    def __init__(self, children: list[Any], explicit: bool) -> None:
        self.children = children
        self.explicit = explicit


class _Or:
    __slots__ = ("children",)

    def __init__(self, children: list[Any]) -> None:
        self.children = children


def _candidate_root_aids(select_statement: ods.SelectStatement) -> list[int]:
    """Collect entity aids that could act as the query root, ordered by likelihood."""
    condition_aids: list[int] = []
    for item in select_statement.where:
        if item.HasField("condition"):
            condition_aids.append(item.condition.aid)

    column_aids = [column.aid for column in select_statement.columns]

    seen: set[int] = set()
    ordered: list[int] = []
    # Target is normally the columns, so try them first.
    for aid in column_aids + condition_aids:
        if aid not in seen:
            seen.add(aid)
            ordered.append(aid)
    for join in select_statement.joins:
        for aid in (join.aid_from, join.aid_to):
            if aid not in seen:
                seen.add(aid)
                ordered.append(aid)
    return ordered


def _build_for_root(
    mc: ModelCache,
    select_statement: ods.SelectStatement,
    root_aid: int,
    use_base_names: bool,
) -> dict[str, Any]:
    """Build a JAQueL query using ``root_aid`` as the query root entity."""
    root_entity = mc.entity_by_aid(root_aid)
    adjacency = _build_adjacency(mc, select_statement.joins, use_base_names)

    root_body = _build_conditions(mc, select_statement, root_aid, adjacency, use_base_names)

    query: dict[str, Any] = {root_entity.name: root_body}

    attributes = _build_attributes(mc, select_statement, root_aid, adjacency, use_base_names)
    if attributes is not None:
        query["$attributes"] = attributes

    order_by = _build_order_by(mc, select_statement, root_aid, adjacency, use_base_names)
    if order_by:
        query["$orderby"] = order_by

    group_by = _build_group_by(mc, select_statement, root_aid, adjacency, use_base_names)
    if group_by:
        query["$groupby"] = group_by

    options = _build_options(select_statement)
    if options:
        query["$options"] = options

    return query


def _build_adjacency(mc: ModelCache, joins: Any, use_base_names: bool) -> dict[int, list[tuple[int, str]]]:
    """Build a navigable graph from the join items, keyed by entity aid.

    Each edge yields the relation token (application or base name, optionally
    suffixed with ``:OUTER``) required to navigate from one entity to the neighbour.
    """
    adjacency: dict[int, list[tuple[int, str]]] = {}
    for join in joins:
        outer = join.join_type == _JoinTypeEnum.JT_OUTER
        suffix = ":OUTER" if outer else ""
        entity_from = mc.entity_by_aid(join.aid_from)
        entity_to = mc.entity_by_aid(join.aid_to)
        relation = mc.relation(entity_from, join.relation)
        if use_base_names:
            forward = _safe_base_relation(mc, entity_from, relation)
            inverse_relation = mc.relation(entity_to, relation.inverse_name)
            backward = _safe_base_relation(mc, entity_to, inverse_relation)
        else:
            forward = relation.name
            backward = relation.inverse_name
        adjacency.setdefault(join.aid_from, []).append((join.aid_to, forward + suffix))
        adjacency.setdefault(join.aid_to, []).append((join.aid_from, backward + suffix))
    return adjacency


def _safe_base_relation(mc: ModelCache, entity: ods.Model.Entity, relation: ods.Model.Relation) -> str:
    """Return ``relation``'s base name if it unambiguously resolves back to it.

    Multiple relations of an entity may share a base name (e.g. several ``children``
    relations). Emitting an ambiguous base name would resolve to a different
    relation and break the round-trip, so fall back to the application name.
    """
    if relation.base_name:
        resolved = mc.relation_no_throw(entity, relation.base_name)
        if resolved is not None and resolved.name == relation.name:
            return relation.base_name
    return relation.name


def _navigate(adjacency: dict[int, list[tuple[int, str]]], root_aid: int, target_aid: int) -> list[str]:
    """Return the relation tokens to navigate from ``root_aid`` to ``target_aid``."""
    if root_aid == target_aid:
        return []
    queue: deque[tuple[int, list[str]]] = deque([(root_aid, [])])
    seen = {root_aid}
    while queue:
        current, path = queue.popleft()
        for neighbour, token in adjacency.get(current, []):
            if neighbour in seen:
                continue
            new_path = path + [token]
            if neighbour == target_aid:
                return new_path
            seen.add(neighbour)
            queue.append((neighbour, new_path))
    raise _Unsupported(f"No relation path from entity {root_aid} to entity {target_aid}.")


def _path_segments(
    mc: ModelCache,
    adjacency: dict[int, list[tuple[int, str]]],
    root_aid: int,
    aid: int,
    attribute: str,
    use_base_names: bool,
) -> list[str]:
    return _navigate(adjacency, root_aid, aid) + [_attribute_name(mc, aid, attribute, use_base_names)]


def _attribute_name(mc: ModelCache, aid: int, attribute: str, use_base_names: bool) -> str:
    """Resolve the JAQueL token for ``attribute`` on entity ``aid``."""
    if not use_base_names:
        return attribute
    entity = mc.entity_by_aid(aid)
    found = mc.attribute_no_throw(entity, attribute)
    if found is not None and found.base_name:
        # Only use the base name when it unambiguously resolves back to this
        # attribute, otherwise the round-trip would break.
        resolved = mc.attribute_no_throw(entity, found.base_name)
        if resolved is not None and resolved.name == found.name:
            return found.base_name
    return attribute


def _build_conditions(
    mc: ModelCache,
    select_statement: ods.SelectStatement,
    root_aid: int,
    adjacency: dict[int, list[tuple[int, str]]],
    use_base_names: bool,
) -> dict[str, Any]:
    tokens = _condition_tokens(select_statement)
    if not tokens:
        return {}
    tree = _WhereParser(tokens).parse()
    return _render_condition(tree, mc, root_aid, adjacency, use_base_names)


def _condition_tokens(select_statement: ods.SelectStatement) -> list[tuple[str, Any]]:
    tokens: list[tuple[str, Any]] = []
    for item in select_statement.where:
        if item.HasField("condition"):
            tokens.append(("cond", item.condition))
        else:
            tokens.append(("conj", item.conjunction))
    return tokens


class _WhereParser:
    """Recursive-descent parser turning a where token stream into a boolean tree."""

    def __init__(self, tokens: list[tuple[str, Any]]) -> None:
        self._tokens = tokens
        self._pos = 0

    def parse(self) -> Any:
        node = self._parse_expression()
        if self._pos != len(self._tokens):
            raise _Unsupported("Unbalanced where clause token stream.")
        return node

    def _peek(self) -> tuple[str, Any] | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _parse_term(self) -> tuple[Any, bool]:
        token = self._peek()
        if token is None:
            raise _Unsupported("Unexpected end of where clause.")
        kind, value = token
        if kind == "conj" and value == _ConjuctionEnum.CO_NOT:
            self._pos += 1
            child, _ = self._parse_term()
            return _Not(child), False
        if kind == "conj" and value == _ConjuctionEnum.CO_OPEN:
            self._pos += 1
            node = self._parse_expression()
            close = self._peek()
            if close is None or close[0] != "conj" or close[1] != _ConjuctionEnum.CO_CLOSE:
                raise _Unsupported("Missing closing parenthesis in where clause.")
            self._pos += 1
            return node, True
        if kind == "cond":
            self._pos += 1
            return _Leaf(value), False
        raise _Unsupported("Unexpected token in where clause.")

    def _parse_expression(self) -> Any:
        node, parenthesised = self._parse_term()
        nodes = [node]
        child_parenthesised = [parenthesised]
        connectors: list[int] = []
        while True:
            token = self._peek()
            if token is None or token[0] != "conj":
                break
            if token[1] not in (_ConjuctionEnum.CO_AND, _ConjuctionEnum.CO_OR):
                break
            connectors.append(token[1])
            self._pos += 1
            child, child_paren = self._parse_term()
            nodes.append(child)
            child_parenthesised.append(child_paren)
        if not connectors:
            return nodes[0]
        if all(connector == _ConjuctionEnum.CO_AND for connector in connectors):
            # Explicit ``$and`` arrays wrap each element in parentheses; implicit
            # AND (multiple keys in one dict) does not.
            explicit = any(child_parenthesised)
            return _And(nodes, explicit)
        if all(connector == _ConjuctionEnum.CO_OR for connector in connectors):
            return _Or(nodes)
        raise _Unsupported("Mixed AND/OR connectors at the same level.")


def _render_condition(
    node: Any,
    mc: ModelCache,
    root_aid: int,
    adjacency: dict[int, list[tuple[int, str]]],
    use_base_names: bool,
) -> dict[str, Any]:
    if isinstance(node, _Leaf):
        segments = _path_segments(
            mc,
            adjacency,
            root_aid,
            node.condition.aid,
            node.condition.attribute,
            use_base_names,
        )
        return _nest(segments, _condition_value(node.condition))
    if isinstance(node, _Not):
        return {"$not": _render_condition(node.child, mc, root_aid, adjacency, use_base_names)}
    if isinstance(node, _Or):
        return {"$or": [_render_condition(child, mc, root_aid, adjacency, use_base_names) for child in node.children]}
    if isinstance(node, _And):
        parts = [_render_condition(child, mc, root_aid, adjacency, use_base_names) for child in node.children]
        if not node.explicit:
            merged: dict[str, Any] = {}
            if all(_deep_merge(merged, part) for part in parts):
                return merged
        return {"$and": parts}
    raise _Unsupported("Unknown condition node.")


def _condition_value(condition: ods.SelectStatement.ConditionItem.Condition) -> Any:
    operator: int = condition.operator
    options = ""
    if operator in _CI_TO_BASE:
        options = "i"
        operator = _CI_TO_BASE[operator]

    if operator == _OperatorEnum.OP_IS_NULL:
        return {"$null": 1}
    if operator == _OperatorEnum.OP_IS_NOT_NULL:
        return {"$notnull": 1}

    values = _condition_values(condition)
    unit = condition.unit_id

    if operator == _OperatorEnum.OP_EQ and unit == 0 and options == "":
        return values[0]

    node: dict[str, Any] = {}
    if unit != 0:
        node["$unit"] = unit

    if operator == _OperatorEnum.OP_BETWEEN:
        node["$between"] = values
    elif operator in (_OperatorEnum.OP_INSET, _OperatorEnum.OP_NOTINSET):
        node[_OP_TO_JAQUEL[operator]] = values
    elif operator == _OperatorEnum.OP_EQ:
        node["$eq"] = values[0]
    else:
        node[_OP_TO_JAQUEL[operator]] = values[0]

    if options:
        node["$options"] = options
    return node


def _condition_values(
    condition: ods.SelectStatement.ConditionItem.Condition,
) -> list[Any]:
    for field in _ARRAY_FIELDS:
        if condition.HasField(field):
            return list(getattr(condition, field).values)
    return []


def _is_default_wildcard(select_statement: ods.SelectStatement, root_aid: int) -> bool:
    if len(select_statement.columns) != 1:
        return False
    column = select_statement.columns[0]
    return (
        column.aid == root_aid
        and column.attribute == "*"
        and column.aggregate == ods.AggregateEnum.AG_NONE
        and column.unit_id == 0
    )


def _build_attributes(
    mc: ModelCache,
    select_statement: ods.SelectStatement,
    root_aid: int,
    adjacency: dict[int, list[tuple[int, str]]],
    use_base_names: bool,
) -> dict[str, Any] | None:
    if _is_default_wildcard(select_statement, root_aid):
        return None

    attributes: dict[str, Any] = {}
    for column in select_statement.columns:
        segments = _path_segments(mc, adjacency, root_aid, column.aid, column.attribute, use_base_names)
        value = _attribute_value(column)
        if not _deep_merge(attributes, _nest(segments, value)):
            raise _Unsupported("Conflicting attribute selection.")
    return attributes


def _attribute_value(column: ods.SelectStatement.AttributeItem) -> Any:
    if column.aggregate == ods.AggregateEnum.AG_NONE:
        if column.unit_id != 0:
            raise _Unsupported("Column with a unit but no aggregate is not expressible in JAQueL.")
        return 1
    value: dict[str, Any] = {}
    if column.unit_id != 0:
        value["$unit"] = column.unit_id
    value[_AGG_TO_JAQUEL[column.aggregate]] = 1
    return value


def _build_order_by(
    mc: ModelCache,
    select_statement: ods.SelectStatement,
    root_aid: int,
    adjacency: dict[int, list[tuple[int, str]]],
    use_base_names: bool,
) -> dict[str, Any]:
    order_by: dict[str, Any] = {}
    for item in select_statement.order_by:
        segments = _path_segments(mc, adjacency, root_aid, item.aid, item.attribute, use_base_names)
        value = 1 if item.order == _OrderEnum.OD_ASCENDING else 0
        if not _deep_merge(order_by, _nest(segments, value)):
            raise _Unsupported("Conflicting orderby selection.")
    return order_by


def _build_group_by(
    mc: ModelCache,
    select_statement: ods.SelectStatement,
    root_aid: int,
    adjacency: dict[int, list[tuple[int, str]]],
    use_base_names: bool,
) -> dict[str, Any]:
    group_by: dict[str, Any] = {}
    for item in select_statement.group_by:
        segments = _path_segments(mc, adjacency, root_aid, item.aid, item.attribute, use_base_names)
        if not _deep_merge(group_by, _nest(segments, 1)):
            raise _Unsupported("Conflicting groupby selection.")
    return group_by


def _build_options(select_statement: ods.SelectStatement) -> dict[str, Any]:
    options: dict[str, Any] = {}
    if select_statement.row_limit != 0:
        options["$rowlimit"] = select_statement.row_limit
    if select_statement.row_start != 0:
        options["$rowskip"] = select_statement.row_start
    if select_statement.values_limit != 0:
        options["$seqlimit"] = select_statement.values_limit
    if select_statement.values_start != 0:
        options["$seqskip"] = select_statement.values_start
    return options


def _nest(segments: list[str], value: Any) -> dict[str, Any]:
    """Build a nested dict from path ``segments`` assigning ``value`` at the leaf."""
    result: dict[str, Any] = {}
    current = result
    for segment in segments[:-1]:
        nested: dict[str, Any] = {}
        current[segment] = nested
        current = nested
    current[segments[-1]] = value
    return result


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> bool:
    """Merge ``source`` into ``target`` in place. Return ``False`` on conflict."""
    for key, value in source.items():
        if key in target:
            if isinstance(target[key], dict) and isinstance(value, dict):
                if not _deep_merge(target[key], value):
                    return False
            else:
                return False
        else:
            target[key] = value
    return True


def ods_to_jaquel(
    mc: ModelCache,
    select_statement: ods.SelectStatement,
    *,
    use_base_names: bool = False,
    complement_joins: bool = True,
) -> dict[str, Any]:
    """Convert a :class:`SelectStatement` into a readable JAQueL query dict.

    Args:
        mc: Model cache wrapping the application model used for the statement.
        select_statement: The ODS select statement to convert.
        use_base_names: When ``True``, emit the base name of attributes and
            relations instead of their application name whenever a base name is
            available. Falls back to the application name otherwise.
        complement_joins: When ``True``, automatically complement joins in the query.

    Returns:
        A JAQueL query as ``dict`` that reproduces ``select_statement`` when
        passed through :func:`odsbox.jaquel.jaquel_to_ods`.

    Raises:
        ValueError: If the statement cannot be expressed as a JAQueL query.
    """
    model = mc.model()

    if complement_joins:
        from . import ensure_required_joins

        select_statement = ensure_required_joins(mc, select_statement)

    candidates = _candidate_root_aids(select_statement)

    verified: list[tuple[int, int, dict[str, Any]]] = []
    for root_aid in candidates:
        try:
            query = _build_for_root(mc, select_statement, root_aid, use_base_names)
        except _Unsupported, ValueError:
            continue
        try:
            _entity, rebuilt = jaquel_to_ods(model, query)
        except Exception:  # noqa: BLE001, S112 - a parser error only means this candidate is invalid
            continue
        if rebuilt == select_statement:
            verified.append((len(repr(query)), root_aid, query))

    if not verified:
        raise ValueError(
            "Unable to convert SelectStatement to a JAQueL query. The statement "
            "may contain constructs that have no JAQueL representation."
        )

    # Prefer the shortest (most readable) representation, deterministic by aid.
    verified.sort(key=lambda item: (item[0], item[1]))
    return verified[0][2]
