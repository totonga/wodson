import jaquel_to_ods_convert
import ods_to_protobuf_select

import odslib

import json


testQueries = []

testQueries.append('''{
                        "AoTest":{"name":"a","id":1}
                       }''')

testQueries.append('''{
                        "AoTest":{"name":{"$inset":["a","b","c"]},"id":{"$inset":[1,2,3]}}
                       }''')

testQueries.append('''{
                        "AoTest":{"name":{"$inset":["a","b","c"]},"id":{"$inset":["1","2","3"]}}
                       }''')

testQueries.append('''{
                        "AoTest":{"name":{"$like":"abc","$options":"i"}},
                        "$options":{"$seqskip":5}
                       }''')

testQueries.append('''{
                        "AoTest":{"name":{"$eq":"abc","$options":"i"}}
                       }''')


testQueries.append('''{
                        "AoTest":12
                       }''')

testQueries.append('''{
                        "AoTest":{},
                        "$attributes":{"id":1,"name":1},
                        "$orderby":{"name":1}
                       }''')

testQueries.append('''{
                        "AoTest":{},
                        "$attributes":{"id":1,"name":1},
                        "$orderby":{"name":1}
                       }''')

testQueries.append('''{
                        "AoTest":{},
                        "$attributes":{"id":1,"name":1}
                       }''')


testQueries.append('''{"AoTest":{}}''')

testQueries.append('''{
                        "AoTest":{},
                        "$attributes":{"name":1},
                        "$groupby":{"name":1}
                       }''')

testQueries.append('''{
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

testQueries.append('''{
                        "AoMeasurement":{"measurement_begin":"20091223111111001"}
                       }''')

testQueries.append('''{
                        "AoMeasurement":{"measurement_begin":{"$between":["20091223000000", "20091224000000"]}}
                       }''')

testQueries.append('''{
                        "AoMeasurement":{"measurement_begin":"2012-04-22T00:00:00.004Z"}
                       }''')

testQueries.append('''{
                        "AoMeasurement":{"measurement_begin":{"$between":["2012-04-22T00:00:00.001Z", "2012-04-23T00:00:00.002Z"]}}
                       }''')

testQueries.append('''{
                        "AoMeasurementQuantity":{"datatype":8}
                       }''')

testQueries.append('''{
                        "AoMeasurementQuantity":{"datatype":"DT_LONGLONG"}
                       }''')

testQueries.append('''{
                        "AoMeasurementQuantity":{"datatype":{"$inset":[8, 11]}}
                       }''')

testQueries.append('''{
                        "AoMeasurementQuantity":{"datatype":{"$inset":["DT_LONGLONG", "DT_BYTESTR"]}}
                       }''')

testQueries.append('''{
                        "AoMeasurementQuantity":{"maximum":{"$lt":-1245.8}}
                       }''')

testQueries.append('''{
                        "AoMeasurementQuantity":{"maximum":{"$between":[1.2, 2.3]}}
                       }''')

testQueries.append('''{
                        "AoPhysicalDimension":{ "length_exp":1 },
                        "$options": { "$rowlimit": 10 }
                       }''')

testQueries.append('''{
                        "AoPhysicalDimension":{ "length_exp":{"$inset":[1, 2]} },
                        "$options": { "$rowlimit": 10 }
                       }''')

testQueries.append('''{
                        "AoMeasurement":{ "name":"abc" },
                        "$options": { "$rowlimit": 10 }
                       }''')

testQueries.append('''{
                        "AoMeasurement":{ "name":{"$inset":["abc", "def"]} },
                        "$options": { "$rowlimit": 10 }
                       }''')

testQueries.append('''{
                        "AoMeasurementQuantity":{"maximum":{"$between":[1.2, 2.3]}},
                        "$attributes": { "name": 1, "id": 1, "unit.name":1 }
                       }''')

testQueries.append('''{
                        "AoMeasurementQuantity":{"maximum":{"$between":[1.2, 2.3]}},
                        "$attributes": { "name": 1, "id": 1, "unit:OUTER.name":1 }
                       }''')

testQueries.append('''{
                        "AoLocalColumn":{ "independent":1,"sequence_representation":"implicit_saw" },
                        "$options": { "$rowlimit": 10 }
                       }''')


def _writeLine(f, line):
    print line
    f.write(line + "\n")


_session = odslib.CSessionAutoReconnect({u'$URL': u'corbaname::10.89.2.24:900#MeDaMak1.ASAM-ODS', u'USER': 'test', u'PASSWORD': u'test'})
_model = _session.Model()

f = open('queryTestoutput.adoc', 'w')

for index, testQuery in enumerate(testQueries):
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

f.close
