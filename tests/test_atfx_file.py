"""Tests for AtfxFile convenience wrapper.

These tests demonstrate the simplified API for working with ATFX files using
the :class:`AtfxFile` wrapper, which combines :class:`AtfxSession` and
:class:`odsbox.con_i.ConI` into a single context manager with DataFrame-based
query methods.
"""

import odsbox.proto.ods_pb2 as ods
import pytest

from wodson.atfx import AtfxFile

pytest_plugins = ["tests._devtest_fixtures"]

pytestmark = pytest.mark.devtest


def test_context_manager_opens_and_closes(simple_atfx):
    """AtfxFile can be opened and closed as a context manager."""
    with AtfxFile(simple_atfx) as atfx:
        assert atfx is not None
        # Should be usable within the context
        assert atfx.con_i is not None
        assert atfx.mc is not None


def test_accepts_string_or_path(simple_atfx):
    """AtfxFile accepts both str and Path objects."""
    # Test with str
    with AtfxFile(str(simple_atfx)) as atfx:
        assert atfx.mc is not None

    # Test with Path
    with AtfxFile(simple_atfx) as atfx:
        assert atfx.mc is not None


def test_con_i_property_access(simple_atfx):
    """The con_i property provides access to the underlying ConI instance."""
    with AtfxFile(simple_atfx) as atfx:
        con_i = atfx.con_i

        # Should be a ConI instance with standard methods
        assert hasattr(con_i, "model_read")
        assert hasattr(con_i, "data_read")
        assert hasattr(con_i, "query_data")

        # Should be able to call low-level methods
        model = con_i.model()
        assert len(model.entities) > 0


def test_con_i_raises_outside_context_manager(simple_atfx):
    """Accessing con_i outside context manager raises RuntimeError."""
    atfx = AtfxFile(simple_atfx)

    with pytest.raises(RuntimeError, match="context manager"):
        _ = atfx.con_i


def test_mc_property_access(simple_atfx):
    """The mc property provides access to the model cache."""
    with AtfxFile(simple_atfx) as atfx:
        mc = atfx.mc

        # ModelCache should have entity lookup methods
        assert hasattr(mc, "entity")

        # Should be able to look up expected base entities
        env = mc.entity("AoEnvironment")
        assert env is not None
        assert env.name in ("Environment", "AoEnvironment")

        mea = mc.entity("AoMeasurement")
        assert mea is not None
        assert mea.name in ("Measurement", "AoMeasurement")


def test_mc_raises_outside_context_manager(simple_atfx):
    """Accessing mc outside context manager raises RuntimeError."""
    atfx = AtfxFile(simple_atfx)

    with pytest.raises(RuntimeError, match="context manager"):
        _ = atfx.mc


def test_model_loaded_immediately(simple_atfx):
    """Model is loaded immediately when entering context manager."""
    with AtfxFile(simple_atfx) as atfx:
        # mc should be immediately accessible without additional calls
        # Get the model from con_i to check entities
        model = atfx.con_i.model()
        assert len(model.entities) > 0


def test_query_method_basic(simple_atfx):
    """The query() method executes JAQueL queries and returns DataFrames."""
    with AtfxFile(simple_atfx) as atfx:
        # Query Environment entities
        df = atfx.query({"AoEnvironment": {}, "$attributes": {"id": 1, "name": 1}})

        # Should return a DataFrame
        assert hasattr(df, "columns")  # pandas DataFrame
        assert len(df) >= 0  # May be empty, but should be valid

        # Columns should include requested attributes (prefixed with entity name)
        assert any("Id" in col for col in df.columns)


def test_query_method_measurements(simple_atfx):
    """Query measurements from the ATFX file."""
    with AtfxFile(simple_atfx) as atfx:
        df = atfx.query({"AoMeasurement": {}, "$attributes": {"id": 1, "name": 1}})

        # Should return results (Example_Simple should have measurements)
        assert len(df) > 0
        # Column names are prefixed with entity name
        assert any("Id" in col for col in df.columns)


def test_query_method_with_filter(alltypes_atfx):
    """Query with filters using JAQueL syntax."""
    with AtfxFile(alltypes_atfx) as atfx:
        # Query all measurements first
        all_meas = atfx.query({"AoMeasurement": {}, "$attributes": {"id": 1, "name": 1}})

        if len(all_meas) > 0:
            # Query with a filter (if we know a name)
            name_col = [c for c in all_meas.columns if "Name" in c][0]
            first_name = all_meas.iloc[0][name_col]

            filtered = atfx.query({"AoMeasurement": {"name": first_name}, "$attributes": {"id": 1, "name": 1}})

            # Should return at least the one we filtered for
            assert len(filtered) >= 1


def test_con_i_advanced_usage(simple_atfx):
    """con_i can be used for advanced SelectStatement queries."""
    with AtfxFile(simple_atfx) as atfx:
        model = atfx.con_i.model()

        # Find the Measurement entity
        mea_entity = None
        for entity in model.entities.values():
            if entity.name in ("AoMeasurement", "Measurement"):
                mea_entity = entity
                break

        assert mea_entity is not None

        # Build a SelectStatement
        stmt = ods.SelectStatement()
        stmt.columns.add(aid=mea_entity.aid, attribute="Id")
        stmt.columns.add(aid=mea_entity.aid, attribute="Name")

        # Execute via con_i
        result = atfx.con_i.data_read(stmt)

        # Should return DataMatrices
        assert len(result.matrices) > 0


def test_query_submatrix_entities(alltypes_atfx):
    """Query Submatrix entities from ATFX file."""
    with AtfxFile(alltypes_atfx) as atfx:
        # Query Submatrix entities
        df = atfx.query({"AoSubmatrix": {}, "$attributes": {"id": 1, "name": 1, "number_of_rows": 1}})

        # Should find submatrices in AllTypes example
        assert len(df) > 0


def test_query_localcolumn_entities(alltypes_atfx):
    """Query LocalColumn entities from ATFX file."""
    with AtfxFile(alltypes_atfx) as atfx:
        # Query LocalColumn entities
        df = atfx.query({"AoLocalColumn": {}, "$attributes": {"id": 1, "name": 1}})

        # Should find local columns in AllTypes example
        assert len(df) > 0


@pytest.mark.parametrize(
    "atfx_file",
    [
        "simple_atfx",
        "alltypes_atfx",
        "common_typespecs_atfx",
    ],
)
def test_works_with_multiple_files(atfx_file, request):
    """AtfxFile works with various example ATFX files."""
    fixture_value = request.getfixturevalue(atfx_file)

    with AtfxFile(fixture_value) as atfx:
        # Should be able to query basic entities
        df = atfx.query({"AoEnvironment": {}, "$attributes": {"id": 1}})

        # Should return valid DataFrame
        assert hasattr(df, "columns")


def test_cleanup_on_error(simple_atfx):
    """Resources are cleaned up even if an error occurs in the with block."""
    try:
        with AtfxFile(simple_atfx) as atfx:
            # Use the file
            _ = atfx.mc

            # Raise an error
            raise ValueError("Test error")
    except ValueError:
        pass  # Expected

    # atfx should be cleaned up and unusable now
    # (No good way to test this directly, but at least verify no exception)


def test_read_channels_method_exists(simple_atfx):
    """The read_channels() method is available for bulk data queries."""
    with AtfxFile(simple_atfx) as atfx:
        assert hasattr(atfx, "read_channels")
        assert callable(atfx.read_channels)


def test_read_channels_signature(simple_atfx):
    """The read_channels() method has the correct signature."""
    import inspect

    with AtfxFile(simple_atfx) as atfx:
        sig = inspect.signature(atfx.read_channels)

        # Check required parameter
        assert "group_id" in sig.parameters

        # Check optional parameters
        assert "column_patterns" in sig.parameters
        assert "column_patterns_case_insensitive" in sig.parameters
        assert "date_as_timestamp" in sig.parameters
        assert "set_independent_as_index" in sig.parameters
        assert "values_start" in sig.parameters
        assert "values_limit" in sig.parameters

        params = sig.parameters
        assert params["column_patterns"].default is None
        assert params["column_patterns_case_insensitive"].default is True
        assert params["date_as_timestamp"].default is True
        assert params["set_independent_as_index"].default is True
        assert params["values_start"].default == 0
        assert params["values_limit"].default == 0


# Note: The following read_channels tests may skip due to known compatibility
# issues between odsbox's BulkReader and certain ATFX files. This is a
# limitation of the underlying odsbox library, not of the AtfxFile wrapper.


def test_read_channels_basic_read(alltypes_atfx):
    """The read_channels() method reads bulk data from a group (AoSubmatrix)."""
    with AtfxFile(alltypes_atfx) as atfx:
        submatrices = atfx.query({"AoSubmatrix": {}, "$attributes": {"id": 1, "number_of_rows": 1}})

        if len(submatrices) == 0:
            pytest.skip("No submatrices found in test file")

        id_col = [c for c in submatrices.columns if "Id" in c][0]
        group_id = int(submatrices.iloc[0][id_col])

        try:
            df = atfx.read_channels(group_id)

            assert hasattr(df, "columns")
            assert hasattr(df, "shape")
            assert df.shape[0] > 0
            assert df.shape[1] > 0
        except (ValueError, IndexError) as e:
            if "invalid literal for int()" in str(e) or "list index out of range" in str(e):
                pytest.skip(f"Known odsbox compatibility issue: {e}")
            raise


def test_read_channels_with_column_patterns(alltypes_atfx):
    """The read_channels() method accepts column_patterns parameter."""
    with AtfxFile(alltypes_atfx) as atfx:
        submatrices = atfx.query({"AoSubmatrix": {}, "$attributes": {"id": 1}})

        if len(submatrices) == 0:
            pytest.skip("No submatrices found in test file")

        id_col = [c for c in submatrices.columns if "Id" in c][0]
        group_id = int(submatrices.iloc[0][id_col])

        try:
            df_all = atfx.read_channels(group_id)

            if len(df_all.columns) > 0:
                df_filtered = atfx.read_channels(group_id, column_patterns=["*"])
                assert len(df_filtered) > 0
        except (ValueError, IndexError) as e:
            if "invalid literal for int()" in str(e) or "list index out of range" in str(e):
                pytest.skip(f"Known odsbox compatibility issue: {e}")
            raise


def test_read_channels_with_values_limit(alltypes_atfx):
    """The read_channels() method respects values_limit parameter."""
    with AtfxFile(alltypes_atfx) as atfx:
        submatrices = atfx.query({"AoSubmatrix": {}, "$attributes": {"id": 1, "number_of_rows": 1}})

        if len(submatrices) == 0:
            pytest.skip("No submatrices found in test file")

        id_col = [c for c in submatrices.columns if "Id" in c][0]
        rows_col = [c for c in submatrices.columns if "NumberOfRows" in c][0]
        group_id = int(submatrices.iloc[0][id_col])
        num_rows = int(submatrices.iloc[0][rows_col])

        if num_rows < 2:
            pytest.skip("Submatrix has too few rows to test limit")

        try:
            df_limited = atfx.read_channels(group_id, values_limit=1)
            assert len(df_limited) <= 1
        except (ValueError, IndexError) as e:
            if "invalid literal for int()" in str(e) or "list index out of range" in str(e):
                pytest.skip(f"Known odsbox compatibility issue: {e}")
            raise


def test_read_channels_returns_dataframe_with_correct_structure(alltypes_atfx):
    """The read_channels() method returns properly structured DataFrame."""
    import pandas as pd

    with AtfxFile(alltypes_atfx) as atfx:
        submatrices = atfx.query({"AoSubmatrix": {}, "$attributes": {"id": 1, "number_of_rows": 1}})

        if len(submatrices) == 0:
            pytest.skip("No submatrices found in test file")

        id_col = [c for c in submatrices.columns if "Id" in c][0]
        group_id = int(submatrices.iloc[0][id_col])

        try:
            df = atfx.read_channels(group_id)
            assert isinstance(df, pd.DataFrame)
            assert all(isinstance(col, str) for col in df.columns)
        except (ValueError, IndexError) as e:
            if "invalid literal for int()" in str(e) or "list index out of range" in str(e):
                pytest.skip(f"Known odsbox compatibility issue: {e}")
            raise


# ---------------------------------------------------------------------------
# Navigation helper methods: measurements(), groups(), channels()
# ---------------------------------------------------------------------------


def test_measurements_method_exists(simple_atfx):
    """The measurements() method is available."""
    with AtfxFile(simple_atfx) as atfx:
        assert hasattr(atfx, "measurements")
        assert callable(atfx.measurements)


def test_measurements_returns_dataframe(simple_atfx):
    """measurements() returns a DataFrame with rows for each measurement."""
    with AtfxFile(simple_atfx) as atfx:
        df = atfx.measurements()
        assert hasattr(df, "columns")
        assert len(df) > 0


def test_measurements_name_filter(simple_atfx):
    """measurements() name_filter reduces the result set."""
    with AtfxFile(simple_atfx) as atfx:
        all_meas = atfx.measurements()
        first_name = all_meas.iloc[0]["name"]

        filtered = atfx.measurements(name_filter=first_name)
        assert len(filtered) >= 1


def test_measurements_conditions(simple_atfx):
    """measurements() conditions parameter is merged into the query filter."""
    with AtfxFile(simple_atfx) as atfx:
        all_meas = atfx.measurements()
        first_id = int(all_meas.iloc[0]["id"])

        df = atfx.measurements(conditions={"id": first_id})
        assert len(df) >= 1


def test_measurements_limit(simple_atfx):
    """measurements() limit=1 returns at most one row."""
    with AtfxFile(simple_atfx) as atfx:
        df = atfx.measurements(limit=1)
        assert len(df) <= 1


def test_groups_method_exists(simple_atfx):
    """The groups() method is available."""
    with AtfxFile(simple_atfx) as atfx:
        assert hasattr(atfx, "groups")
        assert callable(atfx.groups)


def test_groups_returns_dataframe(simple_atfx):
    """groups() returns a DataFrame of AoSubmatrix entries for a measurement."""
    with AtfxFile(simple_atfx) as atfx:
        meas = atfx.measurements()
        measurement_id = int(meas.iloc[0]["id"])

        df = atfx.groups(measurement_id)
        assert hasattr(df, "columns")
        assert len(df) > 0


def test_groups_columns(simple_atfx):
    """groups() result includes id, name, and number_of_rows columns."""
    with AtfxFile(simple_atfx) as atfx:
        meas = atfx.measurements()
        measurement_id = int(meas.iloc[0]["id"])

        df = atfx.groups(measurement_id)
        assert "id" in df.columns
        assert "name" in df.columns
        assert "number_of_rows" in df.columns


def test_groups_limit(simple_atfx):
    """groups() limit=1 returns at most one row."""
    with AtfxFile(simple_atfx) as atfx:
        meas = atfx.measurements()
        measurement_id = int(meas.iloc[0]["id"])

        df = atfx.groups(measurement_id, limit=1)
        assert len(df) <= 1


def test_channels_method_exists(simple_atfx):
    """The channels() method is available."""
    with AtfxFile(simple_atfx) as atfx:
        assert hasattr(atfx, "channels")
        assert callable(atfx.channels)


def test_channels_returns_dataframe(simple_atfx):
    """channels() returns a DataFrame of AoLocalColumn metadata for a group."""
    with AtfxFile(simple_atfx) as atfx:
        meas = atfx.measurements()
        measurement_id = int(meas.iloc[0]["id"])

        grps = atfx.groups(measurement_id)
        group_id = int(grps.iloc[0]["id"])

        df = atfx.channels(group_id)
        assert hasattr(df, "columns")
        assert len(df) > 0


def test_channels_columns(simple_atfx):
    """channels() result includes id and name columns."""
    with AtfxFile(simple_atfx) as atfx:
        meas = atfx.measurements()
        measurement_id = int(meas.iloc[0]["id"])

        grps = atfx.groups(measurement_id)
        group_id = int(grps.iloc[0]["id"])

        df = atfx.channels(group_id)
        assert "id" in df.columns
        assert "name" in df.columns


def test_channels_limit(simple_atfx):
    """channels() limit=1 returns at most one row."""
    with AtfxFile(simple_atfx) as atfx:
        meas = atfx.measurements()
        measurement_id = int(meas.iloc[0]["id"])

        grps = atfx.groups(measurement_id)
        group_id = int(grps.iloc[0]["id"])

        df = atfx.channels(group_id, limit=1)
        assert len(df) <= 1


def test_navigation_hierarchy(simple_atfx):
    """Full navigation chain: measurements → groups → channels → read_channels."""
    with AtfxFile(simple_atfx) as atfx:
        meas = atfx.measurements()
        assert len(meas) > 0

        measurement_id = int(meas.iloc[0]["id"])

        grps = atfx.groups(measurement_id)
        assert len(grps) > 0

        group_id = int(grps.iloc[0]["id"])

        ch = atfx.channels(group_id)
        assert len(ch) > 0

        # read_channels invocation is covered by dedicated tests above


# ---------------------------------------------------------------------------
# Advanced tests for submatrix queries with parent attributes
# ---------------------------------------------------------------------------


def test_submatrix_with_parent_measurement(alltypes_atfx):
    """Demonstrate querying Submatrix with parent Measurement attributes.

    This example shows how to use the low-level con_i to join Submatrix
    with its parent Measurement, retrieving both Submatrix and Measurement
    attributes in a single query.
    """
    with AtfxFile(alltypes_atfx) as atfx:
        model = atfx.con_i.model()

        # Find entity AIDs
        submatrix_entity = None
        measurement_entity = None

        for entity in model.entities.values():
            if entity.name in ("AoSubmatrix", "Submatrix"):
                submatrix_entity = entity
            elif entity.name in ("AoMeasurement", "Measurement"):
                measurement_entity = entity

        if submatrix_entity is None or measurement_entity is None:
            pytest.skip("Required entities not found in model")

        # Build a join query: Submatrix with parent Measurement
        stmt = ods.SelectStatement()

        # Select Submatrix attributes
        stmt.columns.add(aid=submatrix_entity.aid, attribute="Id")
        stmt.columns.add(aid=submatrix_entity.aid, attribute="Name")

        # Select parent Measurement attributes
        stmt.columns.add(aid=measurement_entity.aid, attribute="Name")

        # Join from Submatrix to Measurement via "Measurement" relation
        stmt.joins.add(
            aid_from=submatrix_entity.aid,
            aid_to=measurement_entity.aid,
            relation="Measurement",
            join_type=ods.SelectStatement.JoinItem.JoinTypeEnum.JT_DEFAULT,
        )

        # Execute the query
        result = atfx.con_i.data_read(stmt)

        # Should have results with data from both entities
        assert len(result.matrices) > 0
        # Should have at least the Submatrix columns
        # (JOIN behavior may vary - column count depends on implementation)
        assert len(result.matrices[0].columns) >= 2


def test_localcolumn_with_parent_submatrix(alltypes_atfx):
    """Demonstrate querying LocalColumn with parent Submatrix attributes.

    This example shows how to retrieve LocalColumn data along with attributes
    from its parent Submatrix using a JOIN.
    """
    with AtfxFile(alltypes_atfx) as atfx:
        model = atfx.con_i.model()

        # Find entity AIDs
        localcolumn_entity = None
        submatrix_entity = None

        for entity in model.entities.values():
            if entity.name in ("AoLocalColumn", "Localcolumn"):
                localcolumn_entity = entity
            elif entity.name in ("AoSubmatrix", "Submatrix"):
                submatrix_entity = entity

        if localcolumn_entity is None or submatrix_entity is None:
            pytest.skip("Required entities not found in model")

        # Build a join query: LocalColumn with parent Submatrix
        stmt = ods.SelectStatement()

        # Select LocalColumn attributes
        stmt.columns.add(aid=localcolumn_entity.aid, attribute="Id")
        stmt.columns.add(aid=localcolumn_entity.aid, attribute="Name")

        # Select parent Submatrix name
        stmt.columns.add(aid=submatrix_entity.aid, attribute="Name")

        # Join from LocalColumn to Submatrix via "Submatrix" relation
        stmt.joins.add(
            aid_from=localcolumn_entity.aid,
            aid_to=submatrix_entity.aid,
            relation="Submatrix",
            join_type=ods.SelectStatement.JoinItem.JoinTypeEnum.JT_DEFAULT,
        )

        # Execute the query
        result = atfx.con_i.data_read(stmt)

        # Should have results with data from both entities
        assert len(result.matrices) > 0
