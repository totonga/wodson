#! /usr/bin/env python

import sys

import time
import wodson_pb2
from google.protobuf import json_format
from google.protobuf import timestamp_pb2

def get_time_stamp(timeVal):
  seconds = int(timeVal)
  nanos = int((timeVal - seconds) * 10**9) 
  return timestamp_pb2.Timestamp(seconds=seconds, nanos=nanos)


if len(sys.argv) != 2:
  print "Usage:", sys.argv[0], "No target given"
  sys.exit(-1)

data_matrices = wodson_pb2.DataMatrices()

data_matrix = data_matrices.tables.add()
data_matrix.name = "MyLocalColumn"
data_matrix.basename = "AoLocalColumn"

column = data_matrix.columns.add()
column.name = "Name"
column.basename = "name"
column.datatype = wodson_pb2.DT_STRING
column.dt_string.values.extend(["Time", "Revs", "Description"])

column = data_matrix.columns.add()
column.name = "Id"
column.basename = "id"
column.datatype = wodson_pb2.DT_LONGLONG
column.dt_longlong.values.extend([4711, 4712, 4713])

column = data_matrix.columns.add()
column.name = "Flags"
column.basename = "flags"
column.datatype = wodson_pb2.DS_SHORT
column.ds_long.values.add().values.extend([15,15,15,15,15])
column.ds_long.values.add().values.extend([15,15,15,15,15])
column.ds_long.values.add().values.extend([15,15,15,15,15])

column = data_matrix.columns.add()
column.name = "Values"
column.basename = "values"
column.datatype = wodson_pb2.DT_UNKNOWN

get_time_stamp(time.time())

timeVals = column.dt_unknown.values.add()
timeVals.datatype = wodson_pb2.DT_DATE
timeVals.dt_date.values.extend([get_time_stamp(time.time()), get_time_stamp(time.time() + 1), get_time_stamp(time.time() + 2), get_time_stamp(time.time() + 3), get_time_stamp(time.time() + 4)])

revsVals = column.dt_unknown.values.add()
revsVals.datatype = wodson_pb2.DT_DOUBLE
revsVals.dt_double.values.extend([1.1, 1.2, 1.3])

desciptionVals = column.dt_unknown.values.add()
desciptionVals.datatype = wodson_pb2.DT_STRING
desciptionVals.dt_string.values.extend(["first", "second", "third", "forth", "fifth"])

# Write all datatypes
data_matrix = data_matrices.tables.add()
data_matrix.name = "AllTypes"

# DT types
column = data_matrix.columns.add()
column.name = "DT_STRING"
column.datatype = wodson_pb2.DT_STRING
column.dt_string.values.extend(["a", "b", "c"])

column = data_matrix.columns.add()
column.name = "DT_SHORT"
column.datatype = wodson_pb2.DT_SHORT
column.dt_long.values.extend([1, 2, -1])

column = data_matrix.columns.add()
column.name = "DT_FLOAT"
column.datatype = wodson_pb2.DT_FLOAT
column.dt_float.values.extend([1.1, 2.1, -1.1])

column = data_matrix.columns.add()
column.name = "DT_BOOLEAN"
column.datatype = wodson_pb2.DT_BOOLEAN
column.dt_boolean.values.extend([True, False, True])

column = data_matrix.columns.add()
column.name = "DT_BYTE"
column.datatype = wodson_pb2.DT_BYTE
column.dt_byte.values = b'abc'

column = data_matrix.columns.add()
column.name = "DT_LONG"
column.datatype = wodson_pb2.DT_LONG
column.dt_long.values.extend([1, 2, -1])

column = data_matrix.columns.add()
column.name = "DT_DOUBLE"
column.datatype = wodson_pb2.DT_DOUBLE
column.dt_double.values.extend([1.1, 2.1, -1.1])

column = data_matrix.columns.add()
column.name = "DT_LONGLONG"
column.datatype = wodson_pb2.DT_DOUBLE
column.dt_longlong.values.extend([123, 345, 789])

column = data_matrix.columns.add()
column.name = "DT_ID"
column.datatype = wodson_pb2.DT_ID
column.dt_longlong.values.extend([123, 345, 789])

column = data_matrix.columns.add()
column.name = "DT_DATE"
column.datatype = wodson_pb2.DT_DATE
column.dt_date.values.extend([get_time_stamp(time.time()), get_time_stamp(time.time() + 1), get_time_stamp(time.time() + 2)])

column = data_matrix.columns.add()
column.name = "DT_BYTESTR"
column.datatype = wodson_pb2.DT_BYTESTR
column.dt_bytestr.values.extend([b'abc', b'def', b'hij'])

column = data_matrix.columns.add()
column.name = "DT_COMPLEX"
column.datatype = wodson_pb2.DT_COMPLEX
column.dt_float.values.extend([1.1,0.0, 2.1,0.0, -1.1,0.0])

column = data_matrix.columns.add()
column.name = "DT_DCOMPLEX"
column.datatype = wodson_pb2.DT_DCOMPLEX
column.dt_double.values.extend([1.1,0.0, 2.1,0.0, -1.1,0.0])

column = data_matrix.columns.add()
column.name = "DT_ENUM"
column.datatype = wodson_pb2.DT_ENUM
column.dt_long.values.extend([1, 3, 7])

column = data_matrix.columns.add()
column.name = "DT_EXTERNALREFERENCE"
column.datatype = wodson_pb2.DT_EXTERNALREFERENCE
column.dt_string.values.extend(["first picture", "image/jpg", "data/firstPic.jpg", "second picture", "image/jpg", "data/secondPic.jpg", "third picture", "image/jpg", "data/thirdPic.jpg"])

# DS types
column = data_matrix.columns.add()
column.name = "DS_STRING"
column.datatype = wodson_pb2.DS_STRING
column.ds_string.values.add().values.extend(["a", "b", "c"])
column.ds_string.values.add().values.extend(["a", "b", "c"])
column.ds_string.values.add().values.extend(["a", "b", "c"])

column = data_matrix.columns.add()
column.name = "DS_SHORT"
column.datatype = wodson_pb2.DS_SHORT
column.ds_long.values.add().values.extend([1, 2, -1])
column.ds_long.values.add().values.extend([1, 2, -1])
column.ds_long.values.add().values.extend([1, 2, -1])

column = data_matrix.columns.add()
column.name = "DS_FLOAT"
column.datatype = wodson_pb2.DS_FLOAT
column.ds_float.values.add().values.extend([1.1, 2.1, -1.1])
column.ds_float.values.add().values.extend([1.1, 2.1, -1.1])
column.ds_float.values.add().values.extend([1.1, 2.1, -1.1])

column = data_matrix.columns.add()
column.name = "DS_BOOLEAN"
column.datatype = wodson_pb2.DS_BOOLEAN
column.ds_boolean.values.add().values.extend([True, False, True])
column.ds_boolean.values.add().values.extend([True, False, True])
column.ds_boolean.values.add().values.extend([True, False, True])

column = data_matrix.columns.add()
column.name = "DS_BYTE"
column.datatype = wodson_pb2.DS_BYTE
column.ds_byte.values.add().values = b'abc'
column.ds_byte.values.add().values = b'abc'
column.ds_byte.values.add().values = b'abc'

column = data_matrix.columns.add()
column.name = "DS_LONG"
column.datatype = wodson_pb2.DS_LONG
column.ds_long.values.add().values.extend([1, 2, -1])
column.ds_long.values.add().values.extend([1, 2, -1])
column.ds_long.values.add().values.extend([1, 2, -1])

column = data_matrix.columns.add()
column.name = "DS_DOUBLE"
column.datatype = wodson_pb2.DS_DOUBLE
column.ds_double.values.add().values.extend([1.1, 2.1, -1.1])
column.ds_double.values.add().values.extend([1.1, 2.1, -1.1])
column.ds_double.values.add().values.extend([1.1, 2.1, -1.1])

column = data_matrix.columns.add()
column.name = "DS_LONGLONG"
column.datatype = wodson_pb2.DS_DOUBLE
column.ds_longlong.values.add().values.extend([123, 345, 789])
column.ds_longlong.values.add().values.extend([123, 345, 789])
column.ds_longlong.values.add().values.extend([123, 345, 789])

column = data_matrix.columns.add()
column.name = "DS_ID"
column.datatype = wodson_pb2.DS_ID
column.ds_longlong.values.add().values.extend([123, 345, 789])
column.ds_longlong.values.add().values.extend([123, 345, 789])
column.ds_longlong.values.add().values.extend([123, 345, 789])

column = data_matrix.columns.add()
column.name = "DS_DATE"
column.datatype = wodson_pb2.DS_DATE
column.ds_date.values.add().values.extend([get_time_stamp(time.time()), get_time_stamp(time.time() + 1), get_time_stamp(time.time() + 2)])
column.ds_date.values.add().values.extend([get_time_stamp(time.time()), get_time_stamp(time.time() + 1), get_time_stamp(time.time() + 2)])
column.ds_date.values.add().values.extend([get_time_stamp(time.time()), get_time_stamp(time.time() + 1), get_time_stamp(time.time() + 2)])

column = data_matrix.columns.add()
column.name = "DS_BYTESTR"
column.datatype = wodson_pb2.DS_BYTESTR
column.ds_bytestr.values.add().values.extend([b'abc', b'def', b'hij'])
column.ds_bytestr.values.add().values.extend([b'abc', b'def', b'hij'])
column.ds_bytestr.values.add().values.extend([b'abc', b'def', b'hij'])

column = data_matrix.columns.add()
column.name = "DS_COMPLEX"
column.datatype = wodson_pb2.DS_COMPLEX
column.ds_float.values.add().values.extend([1.1,0.0, 2.1,0.0, -1.1,0.0])
column.ds_float.values.add().values.extend([1.1,0.0, 2.1,0.0, -1.1,0.0])
column.ds_float.values.add().values.extend([1.1,0.0, 2.1,0.0, -1.1,0.0])

column = data_matrix.columns.add()
column.name = "DS_DCOMPLEX"
column.datatype = wodson_pb2.DS_DCOMPLEX
column.ds_double.values.add().values.extend([1.1,0.0, 2.1,0.0, -1.1,0.0])
column.ds_double.values.add().values.extend([1.1,0.0, 2.1,0.0, -1.1,0.0])
column.ds_double.values.add().values.extend([1.1,0.0, 2.1,0.0, -1.1,0.0])

column = data_matrix.columns.add()
column.name = "DS_ENUM"
column.datatype = wodson_pb2.DS_ENUM
column.ds_long.values.add().values.extend([1, 3, 7])
column.ds_long.values.add().values.extend([1, 3, 7])
column.ds_long.values.add().values.extend([1, 3, 7])

column = data_matrix.columns.add()
column.name = "DS_EXTERNALREFERENCE"
column.datatype = wodson_pb2.DS_EXTERNALREFERENCE
column.ds_string.values.add().values.extend(["first picture", "image/jpg", "data/firstPic.jpg", "second picture", "image/jpg", "data/secondPic.jpg", "third picture", "image/jpg", "data/thirdPic.jpg"])
column.ds_string.values.add().values.extend(["first picture", "image/jpg", "data/firstPic.jpg", "second picture", "image/jpg", "data/secondPic.jpg", "third picture", "image/jpg", "data/thirdPic.jpg"])
column.ds_string.values.add().values.extend(["first picture", "image/jpg", "data/firstPic.jpg", "second picture", "image/jpg", "data/secondPic.jpg", "third picture", "image/jpg", "data/thirdPic.jpg"])


# UNKNOWN

data_matrix = data_matrices.tables.add()
data_matrix.name = "UnkownTypes"

column = data_matrix.columns.add()
column.name = "Values"
column.basename = "values"
column.datatype = wodson_pb2.DT_UNKNOWN

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_STRING
unknownVals.dt_string.values.extend(["a", "b", "c"])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_SHORT
unknownVals.dt_long.values.extend([1, 2, -1])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_FLOAT
unknownVals.dt_float.values.extend([1.1, 2.1, -1.1])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_BOOLEAN
unknownVals.dt_boolean.values.extend([True, False, True])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_BYTE
unknownVals.dt_byte.values = b'abc'

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_LONG
unknownVals.dt_long.values.extend([1, 2, -1])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_DOUBLE
unknownVals.dt_double.values.extend([1.1, 2.1, -1.1])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_DOUBLE
unknownVals.dt_longlong.values.extend([123, 345, 789])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_ID
unknownVals.dt_longlong.values.extend([123, 345, 789])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_DATE
unknownVals.dt_date.values.extend([get_time_stamp(time.time()), get_time_stamp(time.time() + 1), get_time_stamp(time.time() + 2)])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_BYTESTR
unknownVals.dt_bytestr.values.extend([b'abc', b'def', b'hij'])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_COMPLEX
unknownVals.dt_float.values.extend([1.1,0.0, 2.1,0.0, -1.1,0.0])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_DCOMPLEX
unknownVals.dt_double.values.extend([1.1,0.0, 2.1,0.0, -1.1,0.0])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_ENUM
unknownVals.dt_long.values.extend([1, 3, 7])

unknownVals = column.dt_unknown.values.add()
unknownVals.datatype = wodson_pb2.DT_EXTERNALREFERENCE
unknownVals.dt_string.values.extend(["first picture", "image/jpg", "data/firstPic.jpg", "second picture", "image/jpg", "data/secondPic.jpg", "third picture", "image/jpg", "data/thirdPic.jpg"])


jsonStr = json_format.MessageToJson(data_matrices, True)
print jsonStr

f = open(sys.argv[1] + ".pb", "wb")
f.write(data_matrices.SerializeToString())
f.close()

f = open(sys.argv[1] + ".json", "wb")
f.write(jsonStr)
f.close()