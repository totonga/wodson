import jaquel_to_ods_convert

import odslib

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
                        "$orderby":{"name":1},
                        "$groupby":{"id":1}
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
    "AoMeasurement": {
        "name": { "$inset":["a","b","c"] },
        "$or": [
            {
                "measurement_begin": {
                    "$gte": "2012-04-23T00:00:00.000Z",
                    "$lt": "2012-04-24T00:00:00.000Z"
                }
            },
            {
                "measurement_begin": {
                    "$gte": "2012-05-23T00:00:00.000Z",
                    "$lt": "2012-05-24T00:00:00.000Z"
                }
            },
            {
                "measurement_begin": {
                    "$gte": "2012-06-23T00:00:00.000Z",
                    "$lt": "2012-06-24T00:00:00.000Z"
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
        },
        "measurement_quantities.minimum": {
            "$min": 1,
            "$max": 1
        },
        "measurement_quantities.maximum": {
            "$min": 1,
            "$max": 1
        }
    },
    "$orderby": {
        "test.name": 0,
        "name": 1,
        "units_under_test": {
            "name":1
        } 
    },
    "$groupby": {
        "test": {
            "id": 1
        }
    }
}''')


_session = odslib.CSessionAutoReconnect({u'$URL': u'corbaname::10.89.2.24:900#MeDaMak1.ASAM-ODS', u'USER': 'test', u'PASSWORD': u'test'})
_model = _session.Model()

for testQuery in testQueries:
    target, options = jaquel_to_ods_convert.JaquelToQueryStructureExt(_model, testQuery)
    print str(target)
    print str(options)
    print '-----------------------------------------------------'

