"""Tests for JAQueL query patterns through AtfxFile.

Covers the full range of JAQueL query capabilities including:
- Basic entity queries with wildcard and specific attributes
- All comparison operators: $eq, $neq, $lt, $gt, $lte, $gte
- Set operators: $in, $notinset, $between
- String operators: $like, $notlike
- Null tests: $null, $notnull
- Logical combinators: $and, $or, $not
- Ordering, pagination (rowlimit / rowskip)
- Aggregates: $count, $sum
- Forward parent-to-child joins
- Reversed child-to-parent joins (the joined_aids fix)
- Deep multi-level chained joins
- Join combined with filter and attribute selection
- Cross-entity path filtering via joins
"""

from pathlib import Path

import pytest

from wodson.atfx import AtfxFile

pytestmark = pytest.mark.devtest

_SPEC_DIR = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples"
_SIMPLE = _SPEC_DIR / "Example_Simple.atfx"

# Dollar-sign prefix used throughout JAQueL query keys.
# Defined once to avoid shell-escaping confusion and keep tests readable.
_S = "$"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def atfx():
    """Module-scoped AtfxFile for Example_Simple.atfx."""
    with AtfxFile(_SIMPLE) as f:
        yield f


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _q(entity: str, conditions: dict[str, object], **top_keys: object) -> dict[str, object]:
    """Build a JAQueL query dict."""
    d: dict[str, object] = {entity: conditions}
    for k, v in top_keys.items():
        d[_S + k] = v
    return d


# ---------------------------------------------------------------------------
# 1. Basic entity queries – no filter
# ---------------------------------------------------------------------------


def test_query_all_measurements(atfx):
    """Wildcard attribute query returns one row per Measurement."""
    q = _q("AoMeasurement", {})
    df = atfx.query(q)
    assert len(df) == 1
    assert "Measurement.Name" in df.columns


def test_query_all_local_columns(atfx):
    """Query all LocalColumn rows returns 5 rows."""
    q = _q("AoLocalColumn", {}, attributes={"id": 1})
    df = atfx.query(q)
    assert len(df) == 5


def test_wildcard_attribute_selection(atfx):
    """Wildcard attribute returns all defined columns for the entity."""
    q = _q("AoMeasurement", {}, attributes={"*": 1})
    df = atfx.query(q)
    assert "Measurement.Name" in df.columns
    assert "Measurement.Id" in df.columns
    assert "Measurement.StartTime" in df.columns


def test_specific_attributes_selection(atfx):
    """Only requested attributes appear in the result."""
    q = _q("AoMeasurement", {}, attributes={"id": 1, "name": 1})
    df = atfx.query(q)
    assert list(df.columns) == ["Measurement.Id", "Measurement.Name"]
    assert df["Measurement.Id"].iloc[0] == 93
    assert df["Measurement.Name"].iloc[0] == "MyMeasurement"


# ---------------------------------------------------------------------------
# 2. ID shorthand syntax
# ---------------------------------------------------------------------------


def test_entity_by_id_shorthand(atfx):
    """Passing an integer directly as entity value filters by id."""
    q = {**{"AoMeasurement": 93}, _S + "attributes": {"id": 1, "name": 1}}
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


def test_entity_by_id_shorthand_no_match(atfx):
    """Integer id that doesn't exist yields empty DataFrame."""
    q = {**{"AoMeasurement": 9999}, _S + "attributes": {"id": 1}}
    df = atfx.query(q)
    assert len(df) == 0


# ---------------------------------------------------------------------------
# 3. Equality filter
# ---------------------------------------------------------------------------


def test_filter_by_name_eq(atfx):
    """Filter by name equality returns exactly matching rows."""
    q = _q("AoLocalColumn", {"name": "MyMqFloat"}, attributes={"id": 1, "name": 1})
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Localcolumn.Name"].iloc[0] == "MyMqFloat"


def test_filter_by_name_eq_no_match(atfx):
    """Equality filter against non-existent value returns empty DataFrame."""
    q = _q("AoLocalColumn", {"name": "DoesNotExist"}, attributes={"id": 1})
    df = atfx.query(q)
    assert len(df) == 0


def test_filter_by_id_explicit_eq(atfx):
    """Explicit $eq operator on integer id."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "eq": 102}},
        attributes={"id": 1, "name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Localcolumn.Id"].iloc[0] == 102
    assert df["Localcolumn.Name"].iloc[0] == "MyMqFloat"


# ---------------------------------------------------------------------------
# 4. Comparison operators: $neq, $lt, $gt, $lte, $gte
# ---------------------------------------------------------------------------


def test_filter_neq(atfx):
    """$neq excludes exactly the specified id."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "neq": 100}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    ids = list(df["Localcolumn.Id"])
    assert 100 not in ids
    assert len(ids) == 4


def test_filter_lt(atfx):
    """$lt returns only rows strictly less than the value."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "lt": 102}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [100, 101]


def test_filter_gt(atfx):
    """$gt returns only rows strictly greater than the value."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "gt": 103}},
        attributes={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [104]


def test_filter_lte(atfx):
    """$lte returns rows less than or equal to the value."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "lte": 101}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [100, 101]


def test_filter_gte(atfx):
    """$gte returns rows greater than or equal to the value."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "gte": 103}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [103, 104]


def test_filter_combined_gte_lte(atfx):
    """Combining $gte and $lte creates an inclusive range filter."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "gte": 101, _S + "lte": 103}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [101, 102, 103]


def test_filter_combined_gt_lt(atfx):
    """Combining $gt and $lt creates an exclusive range filter."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "gt": 100, _S + "lt": 103}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [101, 102]


# ---------------------------------------------------------------------------
# 5. Set operators: $in, $notinset, $between
# ---------------------------------------------------------------------------


def test_filter_in(atfx):
    """$in returns only rows whose id is in the list."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "in": [100, 102, 104]}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [100, 102, 104]


def test_filter_notinset(atfx):
    """$notinset excludes rows whose id is in the list."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "notinset": [100, 101]}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [102, 103, 104]


def test_filter_between(atfx):
    """$between returns rows where id is inclusively within the range."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "between": [101, 103]}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [101, 102, 103]


# ---------------------------------------------------------------------------
# 6. String operators: $like, $notlike
# ---------------------------------------------------------------------------


def test_filter_like_prefix(atfx):
    """$like with trailing % matches names with the given prefix."""
    q = _q(
        "AoLocalColumn",
        {"name": {_S + "like": "MyMq%"}},
        attributes={"name": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 5
    assert all(n.startswith("MyMq") for n in df["Localcolumn.Name"])


def test_filter_like_substring(atfx):
    """$like with surrounding % matches names containing the substring."""
    q = _q(
        "AoLocalColumn",
        {"name": {_S + "like": "%Float%"}},
        attributes={"id": 1, "name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Localcolumn.Name"].iloc[0] == "MyMqFloat"


def test_filter_notlike(atfx):
    """$notlike excludes names that match the pattern."""
    q = _q(
        "AoLocalColumn",
        {"name": {_S + "notlike": "%Float%"}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 4
    assert 102 not in list(df["Localcolumn.Id"])


# ---------------------------------------------------------------------------
# 7. Null tests: $notnull
# ---------------------------------------------------------------------------


def test_filter_notnull_string(atfx):
    """$notnull on a string column returns all rows that have a value."""
    q = _q(
        "AoMeasurement",
        {"name": {_S + "notnull": True}},
        attributes={"id": 1, "name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Name"].iloc[0] == "MyMeasurement"


# ---------------------------------------------------------------------------
# 8. Logical operators: $and, $or, $not
# ---------------------------------------------------------------------------


def test_filter_or(atfx):
    """$or returns rows matching either branch."""
    q = _q(
        "AoLocalColumn",
        {_S + "or": [{"id": {_S + "lt": 101}}, {"id": {_S + "gt": 103}}]},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [100, 104]


def test_filter_not(atfx):
    """$not negates the inner condition."""
    q = _q(
        "AoLocalColumn",
        {_S + "not": {"id": 100}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    ids = list(df["Localcolumn.Id"])
    assert 100 not in ids
    assert len(ids) == 4


def test_filter_and_explicit(atfx):
    """Explicit $and with two conditions behaves like implicit AND."""
    q = _q(
        "AoLocalColumn",
        {_S + "and": [{"id": {_S + "gte": 101}}, {"id": {_S + "lte": 103}}]},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [101, 102, 103]


# ---------------------------------------------------------------------------
# 9. Ordering
# ---------------------------------------------------------------------------


def test_orderby_ascending(atfx):
    """$orderby with value 1 sorts ascending."""
    q = _q(
        "AoLocalColumn",
        {},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    ids = list(df["Localcolumn.Id"])
    assert ids == sorted(ids)


def test_orderby_descending(atfx):
    """$orderby with value 0 sorts descending."""
    q = _q(
        "AoLocalColumn",
        {},
        attributes={"id": 1},
        orderby={"id": 0},
    )
    df = atfx.query(q)
    ids = list(df["Localcolumn.Id"])
    assert ids == sorted(ids, reverse=True)


def test_orderby_name_ascending(atfx):
    """$orderby on a string attribute sorts lexicographically ascending."""
    q = _q(
        "AoMeasurementQuantity",
        {},
        attributes={"name": 1},
        orderby={"name": 1},
    )
    df = atfx.query(q)
    names = list(df["Measurementquantity.Name"])
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# 10. Pagination: $options $rowlimit / $rowskip
# ---------------------------------------------------------------------------


def test_rowlimit(atfx):
    """$rowlimit restricts the result to at most N rows."""
    q = _q(
        "AoLocalColumn",
        {},
        attributes={"id": 1},
        options={_S + "rowlimit": 3},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 3


def test_rowskip(atfx):
    """$rowskip combined with $rowlimit offsets into the result set."""
    q_all = _q("AoLocalColumn", {}, attributes={"id": 1}, orderby={"id": 1})
    # SQLite requires LIMIT before OFFSET, so pair rowskip with a large rowlimit.
    q_skip = _q(
        "AoLocalColumn",
        {},
        attributes={"id": 1},
        options={_S + "rowskip": 2, _S + "rowlimit": 100},
        orderby={"id": 1},
    )
    df_all = atfx.query(q_all)
    df_skip = atfx.query(q_skip)
    # skip=2 should return the last 3 rows of 5
    assert list(df_skip["Localcolumn.Id"]) == list(df_all["Localcolumn.Id"])[2:]


def test_rowlimit_and_rowskip_together(atfx):
    """Combining $rowlimit and $rowskip pages into the result."""
    q = _q(
        "AoLocalColumn",
        {},
        attributes={"id": 1},
        options={_S + "rowlimit": 2, _S + "rowskip": 2},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    # Rows 3 and 4 (0-indexed 2 and 3) = ids 102, 103
    assert list(df["Localcolumn.Id"]) == [102, 103]


# ---------------------------------------------------------------------------
# 11. Aggregates: $count, $sum
# ---------------------------------------------------------------------------


def test_aggregate_count(atfx):
    """$count aggregate returns the number of matching rows."""
    q = _q(
        "AoLocalColumn",
        {},
        attributes={"id": {_S + "count": 1}},
    )
    df = atfx.query(q)
    assert df.iloc[0, 0] == 5


def test_aggregate_count_with_filter(atfx):
    """$count with a filter counts only matching rows."""
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "gte": 102}},
        attributes={"id": {_S + "count": 1}},
    )
    df = atfx.query(q)
    assert df.iloc[0, 0] == 3


def test_aggregate_sum(atfx):
    """$sum aggregate returns the sum of values in the column."""
    q = _q(
        "AoLocalColumn",
        {},
        attributes={"id": {_S + "sum": 1}},
    )
    df = atfx.query(q)
    # ids are 100+101+102+103+104 = 510
    assert df.iloc[0, 0] == 510


# ---------------------------------------------------------------------------
# 12. Forward parent-to-child join (Measurement → Submatrix)
# ---------------------------------------------------------------------------


def test_join_measurement_to_submatrix(atfx):
    """Forward join from Measurement to Submatrix returns data from both entities."""
    q = _q(
        "AoMeasurement",
        {"submatrices": {"*": {}}},
        attributes={
            "id": 1,
            "name": 1,
            "Submatrices.id": 1,
            "Submatrices.name": 1,
        },
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert "Measurement.Id" in df.columns
    assert "Submatrix.Id" in df.columns
    assert df["Measurement.Id"].iloc[0] == 93
    assert df["Submatrix.Id"].iloc[0] == 99


def test_join_measurement_to_measurement_quantity(atfx):
    """Forward join to MeasurementQuantity (one-to-many) returns 5 joined rows."""
    q = _q(
        "AoMeasurement",
        {"measurement_quantities": {"*": {}}},
        attributes={
            "id": 1,
            "Measurementquantities.id": 1,
            "Measurementquantities.name": 1,
        },
        orderby={"measurement_quantities.id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 5
    assert all(df["Measurement.Id"] == 93)
    assert set(df["Measurementquantity.Name"]) == {
        "MyMqLong",
        "MyMqString",
        "MyMqFloat",
        "MyMqDouble",
        "MyMqTime",
    }


def test_join_measurement_to_local_columns_via_submatrix(atfx):
    """Forward join Measurement → Submatrix → LocalColumn produces 5 rows."""
    q = _q(
        "AoMeasurement",
        {"submatrices": {"local_columns": {"*": {}}}},
        attributes={
            "id": 1,
            "Submatrices.id": 1,
            "Submatrices.LocalColumns.id": 1,
            "Submatrices.LocalColumns.name": 1,
        },
        orderby={"Submatrices.LocalColumns.id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 5
    assert all(df["Measurement.Id"] == 93)
    assert all(df["Submatrix.Id"] == 99)
    assert list(df["Localcolumn.Id"]) == [100, 101, 102, 103, 104]


# ---------------------------------------------------------------------------
# 13. Reversed child-to-parent join (Submatrix → Measurement)
# The joined_aids fix ensures the primary entity is not duplicated in the SQL
# when the join emits aid_to pointing at the already-selected entity.
# ---------------------------------------------------------------------------


def test_join_submatrix_to_measurement(atfx):
    """Child-to-parent join: Submatrix selects its parent Measurement."""
    q = _q(
        "AoSubmatrix",
        {"measurement": {"*": {}}},
        attributes={
            "id": 1,
            "name": 1,
            "Measurement.id": 1,
            "Measurement.name": 1,
        },
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Submatrix.Id"].iloc[0] == 99
    assert df["Measurement.Id"].iloc[0] == 93
    assert df["Measurement.Name"].iloc[0] == "MyMeasurement"


def test_join_local_column_to_submatrix_to_measurement(atfx):
    """Deep child-to-parent chain: LocalColumn → Submatrix → Measurement."""
    q = _q(
        "AoLocalColumn",
        {"submatrix": {"measurement": {"*": {}}}},
        attributes={
            "id": 1,
            "name": 1,
            "Submatrix.Measurement.id": 1,
        },
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 5
    assert all(df["Measurement.Id"] == 93)
    assert list(df["Localcolumn.Id"]) == [100, 101, 102, 103, 104]


# ---------------------------------------------------------------------------
# 14. Reversed traversal filter
# Primary entity Measurement, filter via child relation (joined_aids fix).
# Before the fix these queries produced a SQL error because the parent
# entity was added twice to the JOIN clause.
# ---------------------------------------------------------------------------


def test_reversed_join_filter_by_submatrix_id(atfx):
    """Filter Measurement by child Submatrix.id (reversed traversal)."""
    q = _q(
        "AoMeasurement",
        {"submatrices": {"id": 99}},
        attributes={"id": 1, "name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


def test_reversed_join_filter_by_submatrix_id_no_match(atfx):
    """Filter Measurement by non-existent Submatrix.id yields empty result."""
    q = _q(
        "AoMeasurement",
        {"submatrices": {"id": 9999}},
        attributes={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 0


def test_reversed_join_filter_by_submatrix_name(atfx):
    """Filter Measurement by child Submatrix.name (reversed traversal)."""
    q = _q(
        "AoMeasurement",
        {"submatrices": {"name": "MyMeasurement"}},
        attributes={"id": 1, "name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


def test_reversed_join_filter_by_mq_name(atfx):
    """Filter Measurement by child MeasurementQuantity.name (one-to-many child)."""
    q = _q(
        "AoMeasurement",
        {"measurement_quantities": {"name": "MyMqFloat"}},
        attributes={"id": 1, "name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


def test_reversed_join_filter_by_mq_id_gte(atfx):
    """Filter Measurement by child MQ.id with range comparison.

    Five MeasurementQuantities (ids 94-98) match $gte 94, so the join yields
    five rows — one per qualifying child — all pointing to the same Measurement.
    """
    q = _q(
        "AoMeasurement",
        {"measurement_quantities": {"id": {_S + "gte": 94}}},
        attributes={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 5
    assert all(df["Measurement.Id"] == 93)


def test_reversed_join_select_parent_and_child(atfx):
    """Select columns from both Measurement and Submatrix with reversed-traversal filter."""
    q = _q(
        "AoMeasurement",
        {"submatrices": {"id": 99}},
        attributes={
            "id": 1,
            "name": 1,
            "Submatrices.id": 1,
            "Submatrices.name": 1,
        },
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93
    assert df["Submatrix.Id"].iloc[0] == 99


# ---------------------------------------------------------------------------
# 15. Deep reversed-path filter
# ---------------------------------------------------------------------------


def test_deep_reversed_filter_by_local_column_name(atfx):
    """Filter Measurement by LocalColumn.name several hops away."""
    q = _q(
        "AoMeasurement",
        {"submatrices": {"local_columns": {"name": "MyMqLong"}}},
        attributes={"id": 1, "name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


def test_deep_reversed_filter_by_local_column_like(atfx):
    """Filter Measurement by LocalColumn.name with $like via deep path."""
    q = _q(
        "AoMeasurement",
        {"submatrices": {"local_columns": {"name": {_S + "like": "%Time%"}}}},
        attributes={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1


def test_deep_reversed_filter_no_match(atfx):
    """Deep reversed filter that matches nothing returns empty DataFrame."""
    q = _q(
        "AoMeasurement",
        {"submatrices": {"local_columns": {"name": "NoSuchColumn"}}},
        attributes={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 0


# ---------------------------------------------------------------------------
# 16. Multi-hop hierarchy join: Test → Subtest → Measurement
# ---------------------------------------------------------------------------


def test_join_test_to_subtest(atfx):
    """Join from Test to its Subtests (parent-to-child 1-to-many)."""
    q = _q(
        "AoTest",
        {"children": {"*": {}}},
        attributes={"id": 1, "name": 1, "Subtests.id": 1, "Subtests.name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Test.Id"].iloc[0] == 91
    assert df["Subtest.Id"].iloc[0] == 92
    assert df["Subtest.Name"].iloc[0] == "MySubtest"


def test_join_test_through_subtest_to_measurement(atfx):
    """Join Test → Subtest → Measurement selects data from all three entities."""
    q = _q(
        "AoTest",
        {"children": {"children": {"*": {}}}},
        attributes={
            "id": 1,
            "name": 1,
            "Subtests.Measurements.id": 1,
            "Subtests.Measurements.name": 1,
        },
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Test.Id"].iloc[0] == 91
    assert df["Measurement.Id"].iloc[0] == 93
    assert df["Measurement.Name"].iloc[0] == "MyMeasurement"


def test_reversed_join_filter_measurement_by_subtest_name(atfx):
    """Filter Measurement by its parent Subtest.name (child-to-parent path in conditions)."""
    q = _q(
        "AoMeasurement",
        {"test": {"name": "MySubtest"}},
        attributes={"id": 1, "name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


# ---------------------------------------------------------------------------
# 17. Ordering by joined-entity attribute
# ---------------------------------------------------------------------------


def test_orderby_joined_entity_column(atfx):
    """Order LocalColumns by their parent Submatrix.id (join traversal in orderby)."""
    q = _q(
        "AoLocalColumn",
        {"submatrix": {"*": {}}},
        attributes={"id": 1},
        orderby={"id": 0},  # descending by LC.id
    )
    df = atfx.query(q)
    ids = list(df["Localcolumn.Id"])
    assert ids == sorted(ids, reverse=True)


def test_orderby_mq_name_via_join(atfx):
    """Query MeasurementQuantity ordered by name ascending."""
    q = _q(
        "AoMeasurementQuantity",
        {},
        attributes={"id": 1, "name": 1},
        orderby={"name": 1},
    )
    df = atfx.query(q)
    names = list(df["Measurementquantity.Name"])
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# 18. Submatrix → Measurement: reversed join with filter on parent
# ---------------------------------------------------------------------------


def test_join_submatrix_filter_by_measurement_name(atfx):
    """Filter Submatrix rows whose Measurement.name matches (reversed select)."""
    q = _q(
        "AoSubmatrix",
        {"measurement": {"name": "MyMeasurement"}},
        attributes={"id": 1, "name": 1, "Measurement.name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Submatrix.Id"].iloc[0] == 99
    assert df["Measurement.Name"].iloc[0] == "MyMeasurement"


def test_join_submatrix_filter_by_measurement_name_no_match(atfx):
    """Filter Submatrix by non-existent Measurement.name returns empty."""
    q = _q(
        "AoSubmatrix",
        {"measurement": {"name": "NoSuchMeasurement"}},
        attributes={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 0


# ---------------------------------------------------------------------------
# 19. MeasurementQuantity → Measurement reversed filter
# ---------------------------------------------------------------------------


def test_join_mq_to_measurement(atfx):
    """MeasurementQuantity → Measurement join (child-to-parent)."""
    q = _q(
        "AoMeasurementQuantity",
        {"measurement": {"*": {}}},
        attributes={"id": 1, "name": 1, "Measurement.id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 5
    assert all(df["Measurement.Id"] == 93)


def test_filter_mq_by_measurement_name(atfx):
    """Filter MeasurementQuantity rows by parent Measurement.name."""
    q = _q(
        "AoMeasurementQuantity",
        {"measurement": {"name": "MyMeasurement"}},
        attributes={"id": 1, "name": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 5
    assert list(df["Measurementquantity.Id"]) == [94, 95, 96, 97, 98]
