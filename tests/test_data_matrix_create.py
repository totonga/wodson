
"""
Test creation of matrices for write
"""

from datetime import datetime
import logging
from pathlib import Path

from google.protobuf.json_format import MessageToDict
import numpy as np
from odsbox.model_cache import ModelCache
from odsbox.proto import ods
from odsbox.bulk_reader import SeqRepEnum
import pandas as pd
import pytest

from wodson.atfx._atfx_store import AtfxStore
from wodson.data_matrix import dataframe_to_datamatrix as to_dm

TEST_DATA_DIR = Path(__file__).resolve().parent / "data"

@pytest.fixture
def open_mdm_atfx():
    return TEST_DATA_DIR / "openMDM" / "ASAM_ODS_AS_for-openMDM-model_V1-0-0.atfx"

@pytest.fixture
def open_mdm_store(open_mdm_atfx):
    with AtfxStore(open_mdm_atfx) as store:
        yield store

def test_create_hierarchy(open_mdm_store: AtfxStore) -> None:
    """Test that the local column values are correct for non-numeric columns."""
    store = open_mdm_store
    mc = ModelCache(store.model())

    dm = to_dm({
        "name": ["MyProject"],
        "mime_type": ["application/x-asam.aotest"]
    }, mc, "Project")
    logging.info(f"Created DataMatrix: {MessageToDict(dm)}")

    dm = to_dm({
        "name": ["MyStructureLevel"],
        "mime_type": ["application/x-asam.aosubtest"],
        "parent_test": [1234]
    }, mc, "StructureLevel")
    logging.info(f"Created DataMatrix: {MessageToDict(dm)}")

    dm = to_dm({
        "name": ["MyTest"],
        "mime_type": ["application/x-asam.aosubtest"],
        "parent_test": [12345],
        "DateClosed": [datetime(2024, 6, 1, 12, 1, 2)],
        "version_date": [datetime(2024, 6, 1, 12, 1, 3)],
        "description": ["This is a test description"],
        "MDMLinks": [["Nice picture", "application/octet-stream", "http://www.test.de/data/test.jpg"]]
    }, mc, "Test")
    logging.info(f"Created DataMatrix: {MessageToDict(dm)}")

    dm = to_dm({
        "name": ["MyTestStep"],
        "mime_type": ["application/x-asam.aosubtest"],
        "parent_test": [12345],
        "DateCreated": [datetime(2024, 6, 1, 12, 1, 3)],
        "description": ["This is a teststep description"],
        "Optional": [False],
        "SortIndex": [1],
        "MDMLinks": [["Nice picture", "application/octet-stream", "http://www.test.de/data/test.jpg", "Nice picture number two", "application/octet-stream", "http://www.test.de/data/test2.jpg"]]
    }, mc, "TestStep")
    logging.info(f"Created DataMatrix: {MessageToDict(dm)}")

    dm = to_dm({
        "name": ["MyMeaResult1", "MyMeaResult2"],
        "mime_type": ["application/x-asam.aomeasurement", "application/x-asam.aomeasurement"],
        "test": [123456, 123456],
        "DateCreated": [datetime(2024, 6, 1, 12, 1, 3), datetime(2024, 6, 1, 12, 2, 3)],
        "description": ["This is a measurement description", "This is another measurement description"],
        "measurement_begin": [datetime(2024, 6, 1, 12, 1, 4, 123456), datetime(2024, 6, 1, 12, 2, 4, 123457)],
        "measurement_end": [datetime(2024, 6, 1, 12, 1, 5, 123456), datetime(2024, 6, 1, 12, 2, 5, 123457)],
    }, mc, "MeaResult")
    logging.info(f"Created DataMatrix: {MessageToDict(dm)}")


    dm = to_dm({
        "name": ["My1Mq1", "My1Mq2","My2Mq1", "My2Mq2", "My2Mq3"],
        "mime_type": ["application/x-asam.aomeasurementquantity"] * 5,
        "measurement": [1234567] * 2 + [1234568] * 3,
        "description": ["Mq description", np.nan, "Mq description 2", np.nan, "Mq description 3"],
        "datatype": [ods.DT_LONG, ods.DT_DOUBLE, ods.DT_LONG, ods.DT_DATE, ods.DT_STRING],
        "rank": [1] * 5,
        "dimension": [[] for _ in range(5)],
        "maximum": [1.1, 2.2, 3.3, 4.4, 5.5],
        "minimum": [1.1, np.nan, 3.3, np.nan, 5.5],
    }, mc, "MeaQuantity")
    logging.info(f"Created DataMatrix: {MessageToDict(dm)}")

    dm = to_dm({
        "name": ["MySubMatrix1", "MySubMatrix2"],
        "mime_type": ["application/x-asam.aosubmatrix", "application/x-asam.aosubmatrix"],
        "measurement": [1234567, 1234568],
        "number_of_rows": [2, 3],
    }, mc, "SubMatrix")
    logging.info(f"Created DataMatrix: {MessageToDict(dm)}")

    dm = to_dm({
        "name": ["My1Mq1", "My1Mq2","My2Mq1", "My2Mq2", "My2Mq3"],
        "mime_type": ["application/x-asam.aolocalcolumn"] * 5,
        "measurement_quantity": [11, 12, 23, 24, 25],
        "submatrix": [11, 11, 22, 22, 22],
        "global_flag": [15, 15, np.nan, np.nan, np.nan],
        "raw_datatype": [ods.DT_LONG, np.nan, ods.DT_LONG, np.nan, ods.DT_STRING],
        "sequence_representation": [SeqRepEnum.implicit_linear, SeqRepEnum.explicit,SeqRepEnum.implicit_linear, SeqRepEnum.explicit, SeqRepEnum.explicit],
        "axistype": [0, 1, 0, 1, 1],
        "independent": [1, 0, 1, 0, 0],
    }, mc, "LocalColumn")
    logging.info(f"Created DataMatrix: {MessageToDict(dm)}")

    dm = to_dm({
        "id": [11, 12, 23, 24, 25],
        "flags": [np.nan, np.nan, [15,15,15], [15,0,15], [0,15,0]],
        "generation_parameters": [[0.0, 1.0], np.nan, [1.0, 0.5], np.nan, np.nan],
        "values": [np.nan, [1.2, 2.3], np.nan, [datetime(2024, 6, 1, 12, 1, 4), datetime(2024, 6, 1, 12, 1, 5), datetime(2024, 6, 1, 12, 1, 6)], ["a", "b", "c"]],
    }, mc, "LocalColumn")
    logging.info(f"Created DataMatrix: {MessageToDict(dm)}")
