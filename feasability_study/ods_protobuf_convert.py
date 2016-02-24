#!/usr/bin/env python

import org
import odslib

import time
import wodson_pb2
from google.protobuf import json_format
from google.protobuf import timestamp_pb2


def content_type_binary():
    return 'application/x-wodson-protobuf'


def content_type_json():
    return 'application/x-wodson-protobuf-json'


def o2p_aggregate(aggrType):
    if aggrType == org.asam.ods.NONE:
        return wodson_pb2.DataMatrix.Column.NONE
    if aggrType == org.asam.ods.COUNT:
        return wodson_pb2.DataMatrix.Column.COUNT
    elif aggrType == org.asam.ods.DCOUNT:
        return wodson_pb2.DataMatrix.Column.DCOUNT
    elif aggrType == org.asam.ods.MIN:
        return wodson_pb2.DataMatrix.Column.MIN
    elif aggrType == org.asam.ods.MAX:
        return wodson_pb2.DataMatrix.Column.MAX
    elif aggrType == org.asam.ods.AVG:
        return wodson_pb2.DataMatrix.Column.AVG
    elif aggrType == org.asam.ods.STDDEV:
        return wodson_pb2.DataMatrix.Column.STDDEV
    elif aggrType == org.asam.ods.SUM:
        return wodson_pb2.DataMatrix.Column.SUM
    elif aggrType == org.asam.ods.DISTINCT:
        return wodson_pb2.DataMatrix.Column.DISTINCT
    elif aggrType == org.asam.ods.POINT:
        return wodson_pb2.DataMatrix.Column.POINT

    return None


def o2p_datatypeenum(arrayType):
    if arrayType == org.asam.ods.DT_UNKNOWN:
        return wodson_pb2.DT_UNKNOWN
    if arrayType == org.asam.ods.DT_BYTE:
        return wodson_pb2.DT_BYTE
    elif arrayType == org.asam.ods.DT_BOOLEAN:
        return wodson_pb2.DT_BOOLEAN
    elif arrayType == org.asam.ods.DT_SHORT:
        return wodson_pb2.DT_SHORT
    elif arrayType == org.asam.ods.DT_LONG:
        return wodson_pb2.DT_LONG
    elif arrayType == org.asam.ods.DT_LONGLONG:
        return wodson_pb2.DT_LONGLONG
    elif arrayType == org.asam.ods.DT_FLOAT:
        return wodson_pb2.DT_FLOAT
    elif arrayType == org.asam.ods.DT_DOUBLE:
        return wodson_pb2.DT_DOUBLE
    elif arrayType == org.asam.ods.DT_DATE:
        return wodson_pb2.DT_DATE
    elif arrayType == org.asam.ods.DT_STRING:
        return wodson_pb2.DT_STRING
    elif arrayType == org.asam.ods.DT_ENUM:
        return wodson_pb2.DT_ENUM
    elif arrayType == org.asam.ods.DT_COMPLEX:
        return wodson_pb2.DT_COMPLEX
    elif arrayType == org.asam.ods.DT_DCOMPLEX:
        return wodson_pb2.DT_DCOMPLEX
    elif arrayType == org.asam.ods.DT_BLOB:
        return wodson_pb2.DT_BLOB
    elif arrayType == org.asam.ods.DT_EXTERNALREFERENCE:
        return wodson_pb2.DT_EXTERNALREFERENCE
    elif arrayType == org.asam.ods.DS_BYTE:
        return wodson_pb2.DS_BYTE
    elif arrayType == org.asam.ods.DS_BOOLEAN:
        return wodson_pb2.DS_BOOLEAN
    elif arrayType == org.asam.ods.DS_SHORT:
        return wodson_pb2.DS_SHORT
    elif arrayType == org.asam.ods.DS_LONG:
        return wodson_pb2.DS_LONG
    elif arrayType == org.asam.ods.DS_LONGLONG:
        return wodson_pb2.DS_LONGLONG
    elif arrayType == org.asam.ods.DS_FLOAT:
        return wodson_pb2.DS_FLOAT
    elif arrayType == org.asam.ods.DS_DOUBLE:
        return wodson_pb2.DS_DOUBLE
    elif arrayType == org.asam.ods.DS_DATE:
        return wodson_pb2.DS_DATE
    elif arrayType == org.asam.ods.DS_STRING:
        return wodson_pb2.DS_STRING
    elif arrayType == org.asam.ods.DS_ENUM:
        return wodson_pb2.DS_ENUM
    elif arrayType == org.asam.ods.DS_COMPLEX:
        return wodson_pb2.DS_COMPLEX
    elif arrayType == org.asam.ods.DS_DCOMPLEX:
        return wodson_pb2.DS_DCOMPLEX
    elif arrayType == org.asam.ods.DS_EXTERNALREFERENCE:
        return wodson_pb2.DS_EXTERNALREFERENCE
    return None


def o2p_column_flags(srcFlags, destFlags):
    nrOfFlags = len(srcFlags)
    if 0 == nrOfFlags:
        return

    flags = []
    containsInvalid = False
    for flag in srcFlags:
        if odslib.ValidFlag(flag):
            flags.append(True)
        else:
            flags.append(False)
            containsInvalid = True

    if containsInvalid:
        destFlags.extend(flags)


def o2p_date(timeStr):
    timeStrLen = len(timeStr)
    if 0 == timeStrLen:
        return timestamp_pb2.Timestamp(seconds=0, nanos=0)
    try:
        tStruct = time.strptime(timeStr[0:14].ljust(14,'0'), "%Y%I%d%H%M%S")
        seconds = int(time.mktime(tStruct))
        nanos = 0
        if timeStrLen > 14:
            nanos = int(timeStr[15:].ljust(6,'0'))

        return timestamp_pb2.Timestamp(seconds=seconds, nanos=nanos)
    except:
        logging.warning('Unable to convert "' + timeStr + '" to timeval')
        return timestamp_pb2.Timestamp(seconds=0, nanos=0)


def o2p_dateseq(dateSeq):
    rv = []
    for dateValue in dateSeq:
        rv.append(o2p_date(dateValue))
    return rv


def o2p_booleanseq(booleanSeq):
    rv = []
    for booleanValue in booleanSeq:
        rv.append(0 != booleanValue)
    return rv


def o2p_datamatrices(model, elem, result, rowSkipCount, seqSkipCount, seqMaxCount, wantsProtoJson):

    rv = wodson_pb2.DataMatrices()

    for table in result:

        tableElem = model.GetElemByAid(table.aid)

        data_matrix = rv.matrices.add()
        data_matrix.name = tableElem.aeName
        data_matrix.base_name = tableElem.beName
        data_matrix.row_skip_count = rowSkipCount
        data_matrix.seq_skip_count = seqSkipCount

        for column in table.values:

            aName, aAggrType = odslib.ExtractAttributeNameFromColumnName(column.valName)

            destColumn = data_matrix.columns.add()
            destColumn.aggregate = o2p_aggregate(aAggrType)

            o2p_column_flags(column.value.flag, destColumn.flags)

            columnValues = odslib.ColumnGetSeq(column)
            for rowIndex, row in enumerate(columnValues):
                if isinstance(row, list):
                    # we should do this using value matrix but actually we are emulating it
                    rowNumAvailable = len(row)
                    if(rowNumAvailable > 0 and (seqSkipCount > 0 or seqMaxCount < rowNumAvailable)):
                        if(seqSkipCount >= rowNumAvailable):
                            columnValues = []
                        else:
                            numtakeable = rowNumAvailable - seqSkipCount
                            if(numtakeable > seqMaxCount):
                                numtakeable = seqMaxCount
                            columnValues[rowIndex] = row[seqSkipCount:(seqSkipCount + numtakeable)]

            attr = model.GetAttribute(tableElem.aeName, aName)
            if not attr is None:
                columnType = attr.dType
                destColumn.datatype = o2p_datatypeenum(columnType) if 'id' != attr.baName else wodson_pb2.DT_ID
                destColumn.name = attr.aaName
                destColumn.base_name = attr.baName
                if columnType == org.asam.ods.DT_BYTE:
                    destColumn.dt_byte.values = b''.join(columnValues)
                elif columnType == org.asam.ods.DT_BOOLEAN:
                    destColumn.dt_boolean.values.extend(o2p_booleanseq(columnValues))
                elif columnType == org.asam.ods.DT_SHORT:
                    destColumn.dt_long.values.extend(columnValues)
                elif columnType == org.asam.ods.DT_LONG:
                    destColumn.dt_long.values.extend(columnValues)
                elif columnType == org.asam.ods.DT_LONGLONG:
                    destColumn.dt_longlong.values.extend(columnValues)
                elif columnType == org.asam.ods.DT_FLOAT:
                    destColumn.dt_float.values.extend(columnValues)
                elif columnType == org.asam.ods.DT_DOUBLE:
                    destColumn.dt_double.values.extend(columnValues)
                elif columnType == org.asam.ods.DT_DATE:
                    destColumn.dt_date.values.extend(o2p_dateseq(columnValues))
                elif columnType == org.asam.ods.DT_STRING:
                    destColumn.dt_string.values.extend(columnValues)
                elif columnType == org.asam.ods.DT_ENUM:
                    destColumn.dt_long.values.extend(columnValues)
                elif columnType == org.asam.ods.DT_COMPLEX:
                    destColumn.dt_float.values.extend(columnValues)
                elif columnType == org.asam.ods.DT_DCOMPLEX:
                    destColumn.dt_double.values.extend(columnValues)
                elif columnType == org.asam.ods.DT_EXTERNALREFERENCE:
                    destColumn.dt_string.values.extend(columnValues)
                elif columnType == org.asam.ods.DT_BLOB:
                    destColumn.dt_string.values.extend(columnValues)
                elif columnType == org.asam.ods.DS_BYTE:
                    for columnValue in columnValues:
                        destColumn.ds_byte.values.add().values = b''.join(columnValue)
                elif columnType == org.asam.ods.DS_BOOLEAN:
                    for columnValue in columnValues:
                        destColumn.ds_boolean.values.add().values.extend(o2p_booleanseq(columnValue))
                elif columnType == org.asam.ods.DS_SHORT:
                    for columnValue in columnValues:
                        destColumn.ds_long.values.add().values.extend(columnValue)
                elif columnType == org.asam.ods.DS_LONG:
                    for columnValue in columnValues:
                        destColumn.ds_long.values.add().values.extend(columnValue)
                elif columnType == org.asam.ods.DS_LONGLONG:
                    for columnValue in columnValues:
                        destColumn.ds_longlong.values.add().values.extend(columnValue)
                elif columnType == org.asam.ods.DS_FLOAT:
                    for columnValue in columnValues:
                        destColumn.ds_float.values.add().values.extend(columnValue)
                elif columnType == org.asam.ods.DS_DOUBLE:
                    for columnValue in columnValues:
                        destColumn.ds_double.values.add().values.extend(columnValue)
                elif columnType == org.asam.ods.DS_DATE:
                    for columnValue in columnValues:
                        destColumn.ds_date.values.add().values.extend(o2p_dateSeq(columnValue))
                elif columnType == org.asam.ods.DS_STRING:
                    for columnValue in columnValues:
                        destColumn.ds_string.values.add().values.extend(columnValue)
                elif columnType == org.asam.ods.DS_ENUM:
                    for columnValue in columnValues:
                        destColumn.ds_long.values.add().values.extend(columnValue)
                elif columnType == org.asam.ods.DS_COMPLEX:
                    for columnValue in columnValues:
                        destColumn.ds_float.values.add().values.extend(columnValue)
                elif columnType == org.asam.ods.DS_DCOMPLEX:
                    for columnValue in columnValues:
                        destColumn.ds_double.values.add().values.extend(columnValue)
                elif columnType == org.asam.ods.DS_EXTERNALREFERENCE:
                    for columnValue in columnValues:
                        destColumn.ds_string.values.add().values.extend(columnValue)
                elif columnType == org.asam.ods.DT_UNKNOWN:
                    for columnValue in columnValues:
                        columnValueDataType = odslib.get_scalar_type(column.value.u._d)
                        unknownVals = destColumn.dt_unknown.values.add()
                        unknownVals.datatype = o2p_datatypeenum(columnValueDataType)
                        if columnValueDataType == org.asam.ods.DT_BYTE:
                            unknownVals.dt_byte.values = b''.join(columnValue)
                        elif columnValueDataType == org.asam.ods.DT_BOOLEAN:
                            unknownVals.dt_boolean.values.extend(o2p_booleanseq(columnValue))
                        elif columnValueDataType == org.asam.ods.DT_SHORT:
                            unknownVals.dt_long.values.extend(columnValue)
                        elif columnValueDataType == org.asam.ods.DT_LONG:
                            unknownVals.dt_long.values.extend(columnValue)
                        elif columnValueDataType == org.asam.ods.DT_LONGLONG:
                            unknownVals.dt_longlong.values.extend(columnValue)
                        elif columnValueDataType == org.asam.ods.DT_FLOAT:
                            unknownVals.dt_float.values.extend(columnValue)
                        elif columnValueDataType == org.asam.ods.DT_DOUBLE:
                            unknownVals.dt_double.values.extend(columnValue)
                        elif columnValueDataType == org.asam.ods.DT_DATE:
                            unknownVals.dt_date.values.extend(o2p_dateseq(columnValue))
                        elif columnValueDataType == org.asam.ods.DT_STRING:
                            unknownVals.dt_string.values.extend(columnValue)
                        elif columnValueDataType == org.asam.ods.DT_ENUM:
                            unknownVals.dt_long.values.extend(columnValue)
                        elif columnValueDataType == org.asam.ods.DT_COMPLEX:
                            unknownVals.dt_float.values.extend(columnValue)
                        elif columnValueDataType == org.asam.ods.DT_DCOMPLEX:
                            unknownVals.dt_double.values.extend(columnValue)
                        elif columnValueDataType == org.asam.ods.DT_EXTERNALREFERENCE:
                            unknownVals.dt_string.values.extend(columnValue)
            else:
                # set relations
                relAttr = model.GetRelation(tableElem.aeName, aName)
                destColumn.name = relAttr.arName
                destColumn.base_name = relAttr.brName
                if 1 == relAttr.arRelationRange.max:
                    destColumn.datatype = wodson_pb2.DT_ID
                    destColumn.dt_longlong.values.extend(columnValues)
                else:
                    destColumn.datatype = wodson_pb2.DS_ID
                    for columnValue in columnValues:
                        destColumn.ds_longlong.values.add().values.extend(columnValue)

    if wantsProtoJson:
        return json_format.MessageToJson(rv, True)

    return rv.SerializeToString()

