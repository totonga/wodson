import html
import json
from pathlib import Path
from typing import Any

import pytest
from google.protobuf.json_format import MessageToJson, Parse
from odsbox.jaquel import jaquel_to_ods
from odsbox.model_cache import ModelCache
from odsbox.proto import ods

from wodson.utils.query import ensure_required_joins, ods_to_jaquel


@pytest.fixture(scope="module")
def model() -> ods.Model:
    model_file = Path(__file__).parent / "data" / "application_model.json"
    return Parse(model_file.read_text(encoding="utf-8"), ods.Model())


# JAQueL queries taken from the odsbox documentation and test corpus. They all
# resolve against the bundled ASAM ODS application model.
JAQUEL_QUERIES: list[dict[str, Any]] = [
    # --- basic access --------------------------------------------------------
    {"AoTest": {}},
    {"Unit": {}},
    {"AoUnit": {}},
    {
        "Unit": {},
        "$attributes": {"name": 1, "factor": 1, "offset": 1},
    },
    {
        "Unit": {},
        "$attributes": {
            "name": 1,
            "factor": 1,
            "offset": 1,
            "phys_dimension.name": 1,
            "phys_dimension.length_exp": 1,
            "phys_dimension.mass_exp": 1,
        },
    },
    {
        "Unit": {},
        "$attributes": {
            "name": 1,
            "factor": 1,
            "offset": 1,
            "phys_dimension": {"name": 1, "length_exp": 1, "mass_exp": 1},
        },
    },
    {
        "Unit": {},
        "$attributes": {"name": 1, "factor": 1, "offset": 1, "phys_dimension.*": 1},
    },
    # --- ordering and limits -------------------------------------------------
    {
        "AoUnit": {},
        "$attributes": {"id": 1, "name": 1},
        "$orderby": {"name": 1},
    },
    {"AoUnit": {}, "$options": {"$rowlimit": 5}},
    {"AoUnit": {}, "$options": {"$rowlimit": 5, "$rowskip": 10}},
    # --- query by id ---------------------------------------------------------
    {"AoUnit": {"id": 3}},
    {"AoUnit": {"id": {"$eq": 3}}},
    {"AoUnit": 3},
    {"AoUnit": {"id": {"$in": [1, 2, 3]}}},
    # --- query by name -------------------------------------------------------
    {"AoUnit": {"name": "s"}},
    {"AoUnit": {"name": "s", "$options": "i"}},
    {"AoUnit": {"name": {"$eq": "s"}, "$options": "i"}},
    {"AoUnit": {"name": {"$like": "k*"}}},
    {"AoUnit": {"name": {"$like": "k*"}, "$options": "i"}},
    {"AoUnit": {"name": {"$neq": "s"}}},
    # --- conjunctions --------------------------------------------------------
    {
        "AoUnit": {
            "phys_dimension": {
                "length_exp": 1,
                "mass_exp": 0,
                "time_exp": -1,
                "current_exp": 0,
                "temperature_exp": 0,
                "molar_amount_exp": 0,
                "luminous_intensity_exp": 0,
            }
        },
        "$attributes": {"name": 1, "factor": 1, "offset": 1, "phys_dimension.name": 1},
    },
    {
        "AoUnit": {
            "phys_dimension": {
                "$and": [
                    {"length_exp": 1},
                    {"mass_exp": 0},
                    {"time_exp": -1},
                ]
            }
        },
    },
    {
        "AoUnit": {
            "phys_dimension": {
                "$or": [
                    {"length_exp": 1, "time_exp": -1},
                    {"length_exp": 0, "time_exp": 1},
                ]
            }
        },
    },
    # --- between and comparison ----------------------------------------------
    {
        "AoMeasurement": {"measurement_begin": {"$between": ["20001223000000", "20241224000000"]}},
        "$options": {"$rowlimit": 5},
    },
    {"AoUnit": {"factor": {"$gt": 1.0, "$lt": 10.0}}},
    {"AoUnit": {"factor": {"$gte": 1.0, "$lte": 10.0}}},
    # --- aggregates ----------------------------------------------------------
    {"AoUnit": {}, "$attributes": {"description": {"$dcount": 1}}},
    {"AoUnit": {}, "$attributes": {"description": {"$distinct": 1}}},
    {"AoUnit": {}, "$attributes": {"factor": {"$max": 1, "$min": 1}}},
    {
        "AoUnit": {},
        "$attributes": {
            "factor": {"$max": 1, "$min": 1},
            "offset": {"$max": 1, "$min": 1},
        },
    },
    # --- inner and outer joins ----------------------------------------------
    {
        "AoMeasurementQuantity": {},
        "$attributes": {"name": 1, "unit.name": 1, "quantity.name": 1},
        "$options": {"$rowlimit": 5},
    },
    {
        "AoMeasurementQuantity": {},
        "$attributes": {"name": 1, "unit:OUTER.name": 1, "quantity:OUTER.name": 1},
        "$options": {"$rowlimit": 5},
    },
    # --- groupby -------------------------------------------------------------
    {
        "AoMeasurement": {},
        "$attributes": {"name": 1, "description": 1},
        "$orderby": {"name": 1},
        "$groupby": {"name": 1, "description": 1},
    },
    # --- openMDM hierarchy / tree browsing -----------------------------------
    {"AoTest": {}, "$options": {"$rowlimit": 5}},
    {"MeaResult": {}, "$options": {"$rowlimit": 5}},
    {
        "MeaResult": {"test": 4},
        "$attributes": {"name": 1, "id": 1},
        "$options": {"$rowlimit": 5},
    },
    # --- bulk access ---------------------------------------------------------
    {
        "AoMeasurementQuantity": {"measurement": 153},
        "$attributes": {"name": 1, "id": 1},
        "$options": {"$rowlimit": 5},
    },
    {
        "AoSubmatrix": {"measurement": 153},
        "$attributes": {"name": 1, "id": 1, "number_of_rows": 1},
        "$options": {"$rowlimit": 5},
    },
    {
        "AoLocalColumn": {"submatrix.measurement": 153},
        "$attributes": {"id": 1, "flags": 1, "generation_parameters": 1, "values": 1},
        "$options": {"$rowlimit": 5},
    },
]


@pytest.mark.parametrize("jaquel_query", JAQUEL_QUERIES)
def test_roundtrip_select_to_jaquel(model: ods.Model, jaquel_query: dict[str, Any]) -> None:
    mc = ModelCache(model)

    _entity, select = jaquel_to_ods(model, jaquel_query)

    jaquel_query_new = ods_to_jaquel(mc, select)

    _entity_new, select_new = jaquel_to_ods(model, jaquel_query_new)

    assert select_new == select


@pytest.mark.parametrize("jaquel_query", JAQUEL_QUERIES)
def test_roundtrip_select_to_jaquel_base_names(model: ods.Model, jaquel_query: dict[str, Any]) -> None:
    mc = ModelCache(model)

    _entity, select = jaquel_to_ods(model, jaquel_query)

    jaquel_query_new = ods_to_jaquel(mc, select, use_base_names=True)

    _entity_new, select_new = jaquel_to_ods(model, jaquel_query_new)

    assert select_new == select


def test_use_base_names_emits_base_names(model: ods.Model) -> None:
    mc = ModelCache(model)

    # ``Domain.MimeType`` has the base name ``mime_type`` (application and base
    # name differ), so the two modes produce distinguishable attribute tokens.
    _entity, select = jaquel_to_ods(model, {"Domain": {}, "$attributes": {"MimeType": 1}})

    default_query = ods_to_jaquel(mc, select)
    base_query = ods_to_jaquel(mc, select, use_base_names=True)

    assert "MimeType" in default_query["$attributes"]
    assert "mime_type" in base_query["$attributes"]


def test_convert_select_statement_to_jaquel(model: ods.Model) -> None:
    mc = ModelCache(model)

    jaquel_query: dict[str, Any] = {"AoTest": {}}

    _entity, select = jaquel_to_ods(model, jaquel_query)
    assert select is not None

    jaquel_query_new: dict[str, Any] = ods_to_jaquel(mc, select)

    _entity_new, select_new = jaquel_to_ods(model, jaquel_query_new)
    assert select_new is not None

    assert select_new == select


_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>JAQueL conversion comparison</title>
<style>
  body {{ font-family: sans-serif; margin: 0; padding: 1rem; }}
  h2 {{ font-size: 0.95rem; word-break: break-all; }}
  .row {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap: 1rem;
    border-bottom: 2px solid #ccc;
    padding-bottom: 1rem;
    margin-bottom: 1rem;
  }}
  .row.mismatch {{ background: #fff3f3; }}
  .col h3 {{ margin: 0 0 0.25rem; font-size: 0.8rem; color: #555; }}
  pre {{
    background: #f5f5f5;
    padding: 0.5rem;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 0.8rem;
  }}
</style>
</head>
<body>
<h1>JAQueL conversion comparison</h1>
{rows}
</body>
</html>
"""

_ROW_TEMPLATE = """<section class="row{mismatch_class}">
  <div class="col">
    <h3>JAQueL query (source)</h3>
    <pre>{left}</pre>
  </div>
  <div class="col">
    <h3>SelectStatement (source .proto)</h3>
    <pre>{middle}</pre>
  </div>
  <div class="col">
    <h3>JAQueL query (generated)</h3>
    <pre>{right}</pre>
  </div>
  <div class="col">
    <h3>JAQueL query (generated, base names)</h3>
    <pre>{right_base}</pre>
  </div>
</section>
"""


def _render_comparison_row(title: str, left: str, middle: str, right: str, right_base: str, mismatch: bool) -> str:
    return f"<h2>{html.escape(title)}</h2>" + _ROW_TEMPLATE.format(
        mismatch_class=" mismatch" if mismatch else "",
        left=html.escape(left),
        middle=html.escape(middle),
        right=html.escape(right),
        right_base=html.escape(right_base),
    )


def test_display_results(model: ods.Model) -> None:
    mc = ModelCache(model)

    example_folder = Path(__file__).parent.joinpath("data", "jaquel")
    assert example_folder.exists()

    jaquel_files = sorted(example_folder.rglob("*.json"))
    assert jaquel_files

    rows: list[str] = []
    mismatches: list[str] = []

    for jaquel_file in jaquel_files:
        jaquel_query = json.loads(jaquel_file.read_text(encoding="utf-8"))

        _, select_statement = jaquel_to_ods(mc.model(), jaquel_query)

        jaquel_query_new = ods_to_jaquel(mc, select_statement)
        jaquel_query_new_base = ods_to_jaquel(mc, select_statement, use_base_names=True)

        title = jaquel_file.relative_to(example_folder).as_posix()
        mismatch = jaquel_query_new != jaquel_query
        if mismatch:
            mismatches.append(title)

        rows.append(
            _render_comparison_row(
                title=title,
                left=json.dumps(jaquel_query, indent=2),
                middle=MessageToJson(select_statement),
                right=json.dumps(jaquel_query_new, indent=2),
                right_base=json.dumps(jaquel_query_new_base, indent=2),
                mismatch=mismatch,
            )
        )

    report_file = Path(__file__).parent / "output" / "jaquel_conversion_comparison_report.html"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(_REPORT_TEMPLATE.format(rows="\n".join(rows)), encoding="utf-8")


_JOIN_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>JAQueL join extension comparison</title>
<style>
  body {{ font-family: sans-serif; margin: 0; padding: 1rem; }}
  h2 {{ font-size: 0.95rem; word-break: break-all; }}
  .row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    border-bottom: 2px solid #ccc;
    padding-bottom: 1rem;
    margin-bottom: 1rem;
  }}
  .row.mismatch {{ background: #fff3f3; }}
  .col h3 {{ margin: 0 0 0.25rem; font-size: 0.8rem; color: #555; }}
  pre {{
    background: #f5f5f5;
    padding: 0.5rem;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 0.8rem;
  }}
</style>
</head>
<body>
<h1>JAQueL join extension comparison</h1>
{rows}
</body>
</html>
"""

_JOIN_ROW_TEMPLATE = """<section class="row{mismatch_class}">
  <div class="col">
    <h3>JAQueL query (source)</h3>
    <pre>{left}</pre>
  </div>
  <div class="col">
    <h3>JAQueL query (joins cleared, then derived)</h3>
    <pre>{right}</pre>
  </div>
</section>
"""


def _render_join_row(title: str, left: str, right: str, mismatch: bool) -> str:
    return f"<h2>{html.escape(title)}</h2>" + _JOIN_ROW_TEMPLATE.format(
        mismatch_class=" mismatch" if mismatch else "",
        left=html.escape(left),
        right=html.escape(right),
    )


def test_add_joins(model: ods.Model) -> None:
    mc = ModelCache(model)

    example_folder = Path(__file__).parent.joinpath("data", "jaquel")
    assert example_folder.exists()

    jaquel_files = sorted(example_folder.rglob("*.json"))
    assert jaquel_files

    rows: list[str] = []

    for jaquel_file in jaquel_files:
        jaquel_query = json.loads(jaquel_file.read_text(encoding="utf-8"))

        _, select_statement = jaquel_to_ods(mc.model(), jaquel_query)

        select_statement.joins.clear()

        # The extended statement must be a valid, convertible JAQueL query.
        jaquel_query_extended = ods_to_jaquel(mc, select_statement, complement_joins=True)
        assert jaquel_query_extended

        title = jaquel_file.relative_to(example_folder).as_posix()
        rows.append(
            _render_join_row(
                title=title,
                left=json.dumps(jaquel_query, indent=2),
                right=json.dumps(jaquel_query_extended, indent=2),
                mismatch=jaquel_query_extended != jaquel_query,
            )
        )

    report_file = Path(__file__).parent / "output" / "jaquel_conversion_join_comparison_report.html"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(_JOIN_REPORT_TEMPLATE.format(rows="\n".join(rows)), encoding="utf-8")


def test_jaquel_does_not_add_joins(model: ods.Model) -> None:
    mc = ModelCache(model)

    example_folder = Path(__file__).parent.joinpath("data", "jaquel")
    assert example_folder.exists()

    jaquel_files = sorted(example_folder.rglob("*.json"))
    assert jaquel_files

    for jaquel_file in jaquel_files:
        jaquel_query = json.loads(jaquel_file.read_text(encoding="utf-8"))

        _, select_statement = jaquel_to_ods(mc.model(), jaquel_query)

        validated_statement = ensure_required_joins(mc, select_statement)

        assert select_statement.joins == validated_statement.joins

        jaquel_query_complemented = ods_to_jaquel(mc, select_statement, complement_joins=True)
        jaquel_query = ods_to_jaquel(mc, select_statement, complement_joins=False)
        assert jaquel_query_complemented == jaquel_query
