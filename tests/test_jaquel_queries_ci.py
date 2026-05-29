"""CI-safe duplicate of test_jaquel_queries.py.

Uses tests/data/openatfx/asam600/Example_Simple.atfx, which is committed to the
repository and therefore runs in CI/CD.  The spec-file counterpart
(test_jaquel_queries.py) is marked ``devtest`` and skipped in CI because
docs/spec/ is listed in .gitignore.

The entity structure and instance data of the two files are identical, so all
assertions are the same.
"""

from pathlib import Path

import pytest

from wodson.atfx import AtfxFile

_SIMPLE = Path(__file__).resolve().parent / "data" / "openatfx" / "asam600" / "Example_Simple.atfx"

_S = "$"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def atfx():
    """Module-scoped AtfxFile for asam600/Example_Simple.atfx (checked in)."""
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
    q = _q("AoMeasurement", {})
    df = atfx.query(q)
    assert len(df) == 1
    assert "Measurement.Name" in df.columns


def test_query_all_local_columns(atfx):
    q = _q("AoLocalColumn", {}, attributes={"id": 1})
    df = atfx.query(q)
    assert len(df) == 5


def test_wildcard_attribute_selection(atfx):
    q = _q("AoMeasurement", {}, attributes={"*": 1})
    df = atfx.query(q)
    assert "Measurement.Name" in df.columns
    assert "Measurement.Id" in df.columns
    assert "Measurement.StartTime" in df.columns


def test_specific_attributes_selection(atfx):
    q = _q("AoMeasurement", {}, attributes={"id": 1, "name": 1})
    df = atfx.query(q)
    assert list(df.columns) == ["Measurement.Id", "Measurement.Name"]
    assert df["Measurement.Id"].iloc[0] == 93
    assert df["Measurement.Name"].iloc[0] == "MyMeasurement"


# ---------------------------------------------------------------------------
# 2. ID shorthand syntax
# ---------------------------------------------------------------------------


def test_entity_by_id_shorthand(atfx):
    q = {**{"AoMeasurement": 93}, _S + "attributes": {"id": 1, "name": 1}}
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


def test_entity_by_id_shorthand_no_match(atfx):
    q = {**{"AoMeasurement": 9999}, _S + "attributes": {"id": 1}}
    df = atfx.query(q)
    assert len(df) == 0


# ---------------------------------------------------------------------------
# 3. Equality filter
# ---------------------------------------------------------------------------


def test_filter_by_name_eq(atfx):
    q = _q("AoLocalColumn", {"name": "MyMqFloat"}, attributes={"id": 1, "name": 1})
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Localcolumn.Name"].iloc[0] == "MyMqFloat"


def test_filter_by_name_eq_no_match(atfx):
    q = _q("AoLocalColumn", {"name": "DoesNotExist"}, attributes={"id": 1})
    df = atfx.query(q)
    assert len(df) == 0


def test_filter_by_id_explicit_eq(atfx):
    q = _q("AoLocalColumn", {"id": {_S + "eq": 102}}, attributes={"id": 1, "name": 1})
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Localcolumn.Id"].iloc[0] == 102
    assert df["Localcolumn.Name"].iloc[0] == "MyMqFloat"


# ---------------------------------------------------------------------------
# 4. Comparison operators: $neq, $lt, $gt, $lte, $gte
# ---------------------------------------------------------------------------


def test_filter_neq(atfx):
    q = _q("AoLocalColumn", {"id": {_S + "neq": 100}}, attributes={"id": 1}, orderby={"id": 1})
    df = atfx.query(q)
    ids = list(df["Localcolumn.Id"])
    assert 100 not in ids
    assert len(ids) == 4


def test_filter_lt(atfx):
    q = _q("AoLocalColumn", {"id": {_S + "lt": 102}}, attributes={"id": 1}, orderby={"id": 1})
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [100, 101]


def test_filter_gt(atfx):
    q = _q("AoLocalColumn", {"id": {_S + "gt": 103}}, attributes={"id": 1})
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [104]


def test_filter_lte(atfx):
    q = _q("AoLocalColumn", {"id": {_S + "lte": 101}}, attributes={"id": 1}, orderby={"id": 1})
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [100, 101]


def test_filter_gte(atfx):
    q = _q("AoLocalColumn", {"id": {_S + "gte": 103}}, attributes={"id": 1}, orderby={"id": 1})
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [103, 104]


def test_filter_combined_gte_lte(atfx):
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "gte": 101, _S + "lte": 103}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [101, 102, 103]


def test_filter_combined_gt_lt(atfx):
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
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "in": [100, 102, 104]}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [100, 102, 104]


def test_filter_notinset(atfx):
    q = _q(
        "AoLocalColumn",
        {"id": {_S + "notinset": [100, 101]}},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [102, 103, 104]


def test_filter_between(atfx):
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
    q = _q("AoLocalColumn", {"name": {_S + "like": "MyMq%"}}, attributes={"name": 1}, orderby={"id": 1})
    df = atfx.query(q)
    assert len(df) == 5
    assert all(n.startswith("MyMq") for n in df["Localcolumn.Name"])


def test_filter_like_substring(atfx):
    q = _q("AoLocalColumn", {"name": {_S + "like": "%Float%"}}, attributes={"id": 1, "name": 1})
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Localcolumn.Name"].iloc[0] == "MyMqFloat"


def test_filter_notlike(atfx):
    q = _q("AoLocalColumn", {"name": {_S + "notlike": "%Float%"}}, attributes={"id": 1}, orderby={"id": 1})
    df = atfx.query(q)
    assert len(df) == 4
    assert 102 not in list(df["Localcolumn.Id"])


# ---------------------------------------------------------------------------
# 7. Null tests: $notnull
# ---------------------------------------------------------------------------


def test_filter_notnull_string(atfx):
    q = _q("AoMeasurement", {"name": {_S + "notnull": True}}, attributes={"id": 1, "name": 1})
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Name"].iloc[0] == "MyMeasurement"


# ---------------------------------------------------------------------------
# 8. Logical operators: $and, $or, $not
# ---------------------------------------------------------------------------


def test_filter_or(atfx):
    q = _q(
        "AoLocalColumn",
        {_S + "or": [{"id": {_S + "lt": 101}}, {"id": {_S + "gt": 103}}]},
        attributes={"id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [100, 104]


def test_filter_not(atfx):
    q = _q("AoLocalColumn", {_S + "not": {"id": 100}}, attributes={"id": 1}, orderby={"id": 1})
    df = atfx.query(q)
    ids = list(df["Localcolumn.Id"])
    assert 100 not in ids
    assert len(ids) == 4


def test_filter_and_explicit(atfx):
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
    q = _q("AoLocalColumn", {}, attributes={"id": 1}, orderby={"id": 1})
    df = atfx.query(q)
    ids = list(df["Localcolumn.Id"])
    assert ids == sorted(ids)


def test_orderby_descending(atfx):
    q = _q("AoLocalColumn", {}, attributes={"id": 1}, orderby={"id": 0})
    df = atfx.query(q)
    ids = list(df["Localcolumn.Id"])
    assert ids == sorted(ids, reverse=True)


def test_orderby_name_ascending(atfx):
    q = _q("AoMeasurementQuantity", {}, attributes={"name": 1}, orderby={"name": 1})
    df = atfx.query(q)
    names = list(df["Measurementquantity.Name"])
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# 10. Pagination: $options $rowlimit / $rowskip
# ---------------------------------------------------------------------------


def test_rowlimit(atfx):
    q = _q("AoLocalColumn", {}, attributes={"id": 1}, options={_S + "rowlimit": 3}, orderby={"id": 1})
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
    assert list(df_skip["Localcolumn.Id"]) == list(df_all["Localcolumn.Id"])[2:]


def test_rowlimit_and_rowskip_together(atfx):
    q = _q(
        "AoLocalColumn",
        {},
        attributes={"id": 1},
        options={_S + "rowlimit": 2, _S + "rowskip": 2},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert list(df["Localcolumn.Id"]) == [102, 103]


# ---------------------------------------------------------------------------
# 11. Aggregates: $count, $sum
# ---------------------------------------------------------------------------


def test_aggregate_count(atfx):
    q = _q("AoLocalColumn", {}, attributes={"id": {_S + "count": 1}})
    df = atfx.query(q)
    assert df.iloc[0, 0] == 5


def test_aggregate_count_with_filter(atfx):
    q = _q("AoLocalColumn", {"id": {_S + "gte": 102}}, attributes={"id": {_S + "count": 1}})
    df = atfx.query(q)
    assert df.iloc[0, 0] == 3


def test_aggregate_sum(atfx):
    q = _q("AoLocalColumn", {}, attributes={"id": {_S + "sum": 1}})
    df = atfx.query(q)
    assert df.iloc[0, 0] == 510


# ---------------------------------------------------------------------------
# 12. Forward parent-to-child join (Measurement → Submatrix)
# ---------------------------------------------------------------------------


def test_join_measurement_to_submatrix(atfx):
    q = _q(
        "AoMeasurement",
        {"submatrices": {"*": {}}},
        attributes={"id": 1, "name": 1, "Submatrices.id": 1, "Submatrices.name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert "Measurement.Id" in df.columns
    assert "Submatrix.Id" in df.columns
    assert df["Measurement.Id"].iloc[0] == 93
    assert df["Submatrix.Id"].iloc[0] == 99


def test_join_measurement_to_measurement_quantity(atfx):
    q = _q(
        "AoMeasurement",
        {"measurement_quantities": {"*": {}}},
        attributes={"id": 1, "Measurementquantities.id": 1, "Measurementquantities.name": 1},
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
# ---------------------------------------------------------------------------


def test_join_submatrix_to_measurement(atfx):
    q = _q(
        "AoSubmatrix",
        {"measurement": {"*": {}}},
        attributes={"id": 1, "name": 1, "Measurement.id": 1, "Measurement.name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Submatrix.Id"].iloc[0] == 99
    assert df["Measurement.Id"].iloc[0] == 93
    assert df["Measurement.Name"].iloc[0] == "MyMeasurement"


def test_join_local_column_to_submatrix_to_measurement(atfx):
    q = _q(
        "AoLocalColumn",
        {"submatrix": {"measurement": {"*": {}}}},
        attributes={"id": 1, "name": 1, "Submatrix.Measurement.id": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 5
    assert all(df["Measurement.Id"] == 93)
    assert list(df["Localcolumn.Id"]) == [100, 101, 102, 103, 104]


# ---------------------------------------------------------------------------
# 14. Reversed traversal filter (joined_aids fix)
# ---------------------------------------------------------------------------


def test_reversed_join_filter_by_submatrix_id(atfx):
    q = _q("AoMeasurement", {"submatrices": {"id": 99}}, attributes={"id": 1, "name": 1})
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


def test_reversed_join_filter_by_submatrix_id_no_match(atfx):
    q = _q("AoMeasurement", {"submatrices": {"id": 9999}}, attributes={"id": 1})
    df = atfx.query(q)
    assert len(df) == 0


def test_reversed_join_filter_by_submatrix_name(atfx):
    q = _q("AoMeasurement", {"submatrices": {"name": "MyMeasurement"}}, attributes={"id": 1, "name": 1})
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


def test_reversed_join_filter_by_mq_name(atfx):
    q = _q(
        "AoMeasurement",
        {"measurement_quantities": {"name": "MyMqFloat"}},
        attributes={"id": 1, "name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


def test_reversed_join_filter_by_mq_id_gte(atfx):
    """Five MeasurementQuantities (ids 94-98) match $gte 94, yielding five joined rows."""
    q = _q("AoMeasurement", {"measurement_quantities": {"id": {_S + "gte": 94}}}, attributes={"id": 1})
    df = atfx.query(q)
    assert len(df) == 5
    assert all(df["Measurement.Id"] == 93)


def test_reversed_join_select_parent_and_child(atfx):
    q = _q(
        "AoMeasurement",
        {"submatrices": {"id": 99}},
        attributes={"id": 1, "name": 1, "Submatrices.id": 1, "Submatrices.name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93
    assert df["Submatrix.Id"].iloc[0] == 99


# ---------------------------------------------------------------------------
# 15. Deep reversed-path filter
# ---------------------------------------------------------------------------


def test_deep_reversed_filter_by_local_column_name(atfx):
    q = _q(
        "AoMeasurement",
        {"submatrices": {"local_columns": {"name": "MyMqLong"}}},
        attributes={"id": 1, "name": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


def test_deep_reversed_filter_by_local_column_like(atfx):
    q = _q(
        "AoMeasurement",
        {"submatrices": {"local_columns": {"name": {_S + "like": "%Time%"}}}},
        attributes={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 1


def test_deep_reversed_filter_no_match(atfx):
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
    q = _q("AoMeasurement", {"test": {"name": "MySubtest"}}, attributes={"id": 1, "name": 1})
    df = atfx.query(q)
    assert len(df) == 1
    assert df["Measurement.Id"].iloc[0] == 93


# ---------------------------------------------------------------------------
# 17. Ordering by joined-entity attribute
# ---------------------------------------------------------------------------


def test_orderby_joined_entity_column(atfx):
    q = _q("AoLocalColumn", {"submatrix": {"*": {}}}, attributes={"id": 1}, orderby={"id": 0})
    df = atfx.query(q)
    ids = list(df["Localcolumn.Id"])
    assert ids == sorted(ids, reverse=True)


def test_orderby_mq_name_via_join(atfx):
    q = _q("AoMeasurementQuantity", {}, attributes={"id": 1, "name": 1}, orderby={"name": 1})
    df = atfx.query(q)
    names = list(df["Measurementquantity.Name"])
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# 18. Submatrix → Measurement reversed join with filter on parent
# ---------------------------------------------------------------------------


def test_join_submatrix_filter_by_measurement_name(atfx):
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
    q = _q("AoSubmatrix", {"measurement": {"name": "NoSuchMeasurement"}}, attributes={"id": 1})
    df = atfx.query(q)
    assert len(df) == 0


# ---------------------------------------------------------------------------
# 19. MeasurementQuantity → Measurement reversed filter
# ---------------------------------------------------------------------------


def test_join_mq_to_measurement(atfx):
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
    q = _q(
        "AoMeasurementQuantity",
        {"measurement": {"name": "MyMeasurement"}},
        attributes={"id": 1, "name": 1},
        orderby={"id": 1},
    )
    df = atfx.query(q)
    assert len(df) == 5
    assert list(df["Measurementquantity.Id"]) == [94, 95, 96, 97, 98]
