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
                        "AoLocalColumn":{ "independent":1,"sequence_representation":"implicit_saw" },
                        "$options": { "$rowlimit": 10 }
                       }''')


_session = odslib.CSessionAutoReconnect({u'$URL': u'corbaname::10.89.2.24:900#MeDaMak1.ASAM-ODS', u'USER': 'test', u'PASSWORD': u'test'})
_model = _session.Model()

for testQuery in testQueries:
    print json.dumps(json.loads(testQuery), indent=4)
    print '-----------------------------------------------------'
    applElem, qse, options = jaquel_to_ods_convert.JaquelToQueryStructureExt(_model, testQuery)
    print str(qse).replace('org.asam.ods.', '')
    print str(options)
    print '-----------------------------------------------------'
    protoSelect = ods_to_protobuf_select.ods_to_protobuf_select_json(_model, qse, options)
    print str(protoSelect)
    print '-----------------------------------------------------'
    result = _session.GetInstancesEx(qse, options['rowlimit'])
    print '+++++++++++++++++++++++++++++++++++++++++++++++++++++'
