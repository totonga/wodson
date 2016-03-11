import jaquel_to_ods_convert
import ods_to_protobuf_select

import odslib

import json

def _RunQueriesAndAddToFile(header, params, f, queryArray):

    def _writeLine(f, line):
        print line
        f.write(line + "\n")

    _session = odslib.CSessionAutoReconnect(params)
    _model = _session.Model()

    _writeLine(f, '')
    _writeLine(f, '=== ' + header)

    for index, testQuery in enumerate(queryArray):
        _writeLine(f, '')
        _writeLine(f, '==== Example ' + str(index))
        _writeLine(f, '')
        _writeLine(f, '================================')
        _writeLine(f, '.input')
        _writeLine(f, '[source,json]')
        _writeLine(f, '----')
        _writeLine(f, json.dumps(json.loads(testQuery), indent=4))
        _writeLine(f, '----')
        applElem, qse, options = jaquel_to_ods_convert.JaquelToQueryStructureExt(_model, testQuery)
        _writeLine(f, '.corba')
        _writeLine(f, '----')
        _writeLine(f, str(qse).replace('org.asam.ods.', '').replace("anuSeq=", "\n  anuSeq=").replace("condSeq=", "\n  condSeq=").replace("joinSeq=", "\n  joinSeq=").replace("orderBy=", "\n  orderBy=").replace("groupBy=", "\n  groupBy=").replace("SelItem(", "\n    SelItem(").replace("SelAIDNameUnitId(", "\n    SelAIDNameUnitId(").replace("SelOrder(", "\n    SelOrder(").replace("JoinDef(", "\n    JoinDef("))
        _writeLine(f, '----')
        protoSelect = ods_to_protobuf_select.ods_to_protobuf_select_json(_model, qse, options)
        _writeLine(f, '.protobuf')
        _writeLine(f, '[source,json]')
        _writeLine(f, '----')
        _writeLine(f, str(protoSelect))
        _writeLine(f, '----')
        result = _session.GetInstancesEx(qse, options['rowlimit'])
        _writeLine(f, '================================')



_queriesMedaMak = []

_queriesMedaMak.append('''{
                        "AoTest":{"name":"a","id":1}
                       }''')

_queriesMedaMak.append('''{
                        "AoTest":{"name":{"$in":["a","b","c"]},"id":{"$in":[1,2,3]}}
                       }''')

_queriesMedaMak.append('''{
                        "AoTest":{"name":{"$in":["a","b","c"]},"id":{"$in":["1","2","3"]}}
                       }''')

_queriesMedaMak.append('''{
                        "AoTest":{"name":{"$like":"abc","$options":"i"}},
                        "$options":{"$seqskip":5}
                       }''')

_queriesMedaMak.append('''{
                        "AoTest":{"name":{"$eq":"abc","$options":"i"}}
                       }''')


_queriesMedaMak.append('''{
                        "AoTest":12
                       }''')

_queriesMedaMak.append('''{
                        "AoTest":{},
                        "$attributes":{"id":1,"name":1},
                        "$orderby":{"name":1}
                       }''')

_queriesMedaMak.append('''{
                        "AoTest":{},
                        "$attributes":{"id":1,"name":1},
                        "$orderby":{"name":1}
                       }''')

_queriesMedaMak.append('''{
                        "AoTest":{},
                        "$attributes":{"id":1,"name":1}
                       }''')


_queriesMedaMak.append('''{"AoTest":{}}''')

_queriesMedaMak.append('''{
                        "AoTest":{},
                        "$attributes":{"name":1},
                        "$groupby":{"name":1}
                       }''')

_queriesMedaMak.append('''{
    "AoMeasurement": {
        "$or": [
            {
                "measurement_quantities.maximum": {
                    "$gte": 1,
                    "$lt": 2
                }
            },
            {
                "measurement_quantities.maximum": {
                    "$gte": 3,
                    "$lt": 4
                }
            },
            {
                "measurement_quantities.maximum": {
                    "$gte": 6,
                    "$lt": 7
                }
            }
        ]
    },
    "$options": {
        "$rowlimit": 1000,
        "$rowskip": 500,
        "$seqlimit": 1000,
        "$seqskip": 500
    },
    "$attributes": {
        "name": 1,
        "id": 1,
        "test": {
            "name": 1,
            "id": 1
        }
    },
    "$orderby": {
        "name": 1
    }
}''')

_queriesMedaMak.append('''{
                        "AoMeasurement":{"measurement_begin":"20091223111111001"}
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurement":{"measurement_begin":{"$between":["20091223000000", "20091224000000"]}}
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurement":{"measurement_begin":"2012-04-22T00:00:00.004Z"}
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurement":{"measurement_begin":{"$between":["2012-04-22T00:00:00.001Z", "2012-04-23T00:00:00.002Z"]}}
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurementQuantity":{"datatype":8}
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurementQuantity":{"datatype":"DT_LONGLONG"}
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurementQuantity":{"datatype":{"$in":[8, 11]}}
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurementQuantity":{"datatype":{"$in":["DT_LONGLONG", "DT_BYTESTR"]}}
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurementQuantity":{"maximum":{"$lt":-1245.8}}
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurementQuantity":{"maximum":{"$between":[1.2, 2.3]}}
                       }''')

_queriesMedaMak.append('''{
                        "AoPhysicalDimension":{ "length_exp":1 },
                        "$options": { "$rowlimit": 10 }
                       }''')

_queriesMedaMak.append('''{
                        "AoPhysicalDimension":{ "length_exp":{"$in":[1, 2]} },
                        "$options": { "$rowlimit": 10 }
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurement":{ "name":"abc" },
                        "$options": { "$rowlimit": 10 }
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurement":{ "name":{"$in":["abc", "def"]} },
                        "$options": { "$rowlimit": 10 }
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurementQuantity":{"maximum":{"$between":[1.2, 2.3]}},
                        "$attributes": { "name": 1, "id": 1, "unit.name":1 }
                       }''')

_queriesMedaMak.append('''{
                        "AoMeasurementQuantity":{"maximum":{"$between":[1.2, 2.3]}},
                        "$attributes": { "name": 1, "id": 1, "unit:OUTER.name":1 }
                       }''')

_queriesMedaMak.append('''{
                        "AoLocalColumn":{ "independent":1,"sequence_representation":"implicit_saw" },
                        "$options": { "$rowlimit": 10 }
                       }''')


_queriesEngine = []
_queriesEngine.append('''
{
    "AoTest": {}
}''')

_queriesEngine.append('''
{
    "Project": {}
}''')
_queriesEngine.append('''{
    "5": {}
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {},
    "$options": {
        "$rowlimit": 10
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {},
    "$attributes": {
        "name": 1,
        "id": 1
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {},
    "$attributes": {
        "name": 1,
        "id": 1,
        "measurement.name": 1
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": 1960
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {
        "id": 1960
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {
        "measurement": 4
    },
    "$attributes": {
        "name": 1,
        "id": 1
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {
        "measurement.test": 10
    },
    "$attributes": {
        "name": 1,
        "id": 1,
        "measurement.name": 1,
        "measurement.id": 1
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {
        "$and": [
            {
                "measurement.measurement_begin": {
                    "$gt": "20071101115000"
                }
            },
            {
                "$or": [
                    {
                        "name": "7 Time Point10:+Z"
                    },
                    {
                        "name": "1 Time Point4:+Z"
                    }
                ]
            }
        ]
    },
    "$attributes": {
        "name": 1,
        "id": 1,
        "unit.name": 1,
        "measurement.name": 1,
        "measurement.id": 1,
        "measurement.test.name": 1,
        "measurement.test.id": 1
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {},
    "$attributes": {
        "name": {
            "$distinct": 1
        }
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {},
    "$attributes": {
        "name": 1
    },
    "$orderby": {
        "name": 0
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {},
    "$attributes": {
        "name": 1
    },
    "$orderby": {
        "name": 1
    },
    "$groupby": {
        "name": 1
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {},
    "$attributes": {
        "name": 1,
        "unit.name": 1,
        "quantity.name": 1
    }
}''')
_queriesEngine.append('''
{
    "AoMeasurementQuantity": {},
    "$attributes": {
        "name": 1,
        "unit:OUTER.name": 1,
        "quantity:OUTER.name": 1
    }
}''')
_queriesEngine.append('''
{
    "AoLocalColumn": 2263,
    "$attributes": {
        "id": 1,
        "generation_parameters": 1,
        "values": 1,
        "flags": 1
    }
}''')
_queriesEngine.append('''
{
    "AoLocalColumn": {
        "submatrix": 24
    },
    "$attributes": {
        "id": 1,
        "generation_parameters": 1,
        "values": 1,
        "flags": 1
    },
    "$options": {
        "$seqlimit": 3
    }
}''')
_queriesEngine.append('''
{
    "AoLocalColumn": 2263,
    "$attributes": {
        "id": 1,
        "values": 1,
        "flags": 1
    },
    "$options": {
        "$seqlimit": 100,
        "$seqskip": 10
    }
}''')
_queriesEngine.append('''
{
    "AoLocalColumn": {
        "submatrix": 24,
        "name": {
            "$in": [
                "Phoenix_02",
                "FFemAIF1_14"
            ]
        }
    },
    "$attributes": {
        "id": 1,
        "generation_parameters": 1,
        "values": 1,
        "flags": 1
    }
}''')

_fileHandle = open('queryTestoutput.adoc', 'w')
_fileHandle.write(':toc: left\n:toclevels: 3\n\n')

_RunQueriesAndAddToFile('Medamak', {u'$URL': u'corbaname::10.89.2.24:900#MeDaMak1.ASAM-ODS', u'USER': 'test', u'PASSWORD': u'test'}, _fileHandle, _queriesMedaMak)
_RunQueriesAndAddToFile('Engine', {u'$URL': u'corbaname::10.89.2.24:900#ENGINE1.ASAM-ODS', u'USER': 'System', u'PASSWORD': u'puma'}, _fileHandle, _queriesEngine)

_fileHandle.close
