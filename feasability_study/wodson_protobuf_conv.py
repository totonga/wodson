#! /usr/bin/env python

import sys

import wodson_pb2
from google.protobuf import json_format

if len(sys.argv) != 2:
  print "Usage:", sys.argv[0], "No target given"
  sys.exit(-1)

data_matrix = wodson_pb2.DataMatrix()
data_matrix.name = "MyLocalColumn"
data_matrix.baseName = "AoLocalColumn"

column = data_matrix.columns.add()
column.name = "Name"
column.baseName = "name"
column.datatype = wodson_pb2.DataMatrix.Column.DT_STRING
column.dtString.values.extend(["Time", "Revs", "Description"])

column = data_matrix.columns.add()
column.name = "Id"
column.baseName = "id"
column.datatype = wodson_pb2.DataMatrix.Column.DT_LONGLONG
column.dtLonglong.values.extend([4711, 4712, 4713])

column = data_matrix.columns.add()
column.name = "Flags"
column.baseName = "flags"
column.datatype = wodson_pb2.DataMatrix.Column.DT_SHORT
column.dsLong.add().values.extend([15,15,15,15,15])
column.dsLong.add().values.extend([15,15,15,15,15])
column.dsLong.add().values.extend([15,15,15,15,15])

column = data_matrix.columns.add()
column.name = "Values"
column.baseName = "values"
column.datatype = wodson_pb2.DataMatrix.Column.DT_UNKNOWN

timeVals = column.dtUnknown.add()
timeVals.datatype = wodson_pb2.DataMatrix.Column.DT_DATE
timeVals.dtString.values.extend(["20160210164812", "20160210164813", "20160210164814", "20160210164815", "20160210164816"])

revsVals = column.dtUnknown.add()
revsVals.datatype = wodson_pb2.DataMatrix.Column.DT_DOUBLE
revsVals.dtDouble.values.extend([1.1, 1.2, 1.3])

desciptionVals = column.dtUnknown.add()
desciptionVals.datatype = wodson_pb2.DataMatrix.Column.DT_STRING
desciptionVals.dtString.values.extend(["first", "second", "third", "forth", "fifth"])

jsonStr = json_format.MessageToJson(data_matrix)
print jsonStr

f = open(sys.argv[1] + ".pb", "wb")
f.write(data_matrix.SerializeToString())
f.close()

f = open(sys.argv[1] + ".json", "wb")
f.write(jsonStr)
f.close()