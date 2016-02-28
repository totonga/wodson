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


_session = odslib.CSessionAutoReconnect({u'$URL': u'corbaname::10.89.2.24:900#MeDaMak1.ASAM-ODS', u'USER': 'test', u'PASSWORD': u'test'})
_model = _session.Model()

for testQuery in testQueries:
    applElem, qse, options = jaquel_to_ods_convert.JaquelToQueryStructureExt(_model, testQuery)
    print str(qse)
    print str(options)
    print '-----------------------------------------------------'
    result = _session.GetInstancesEx(qse, options['rowlimit'])
    print '+++++++++++++++++++++++++++++++++++++++++++++++++++++'
