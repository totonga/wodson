import json
import wodson_pb2
from google.protobuf import json_format
from google.protobuf import timestamp_pb2

query = json.loads('''{
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
        "minimum": {
            "$min": 1,
            "$max": 1
        },
        "maximum": {
            "$min": 1,
            "$max": 1
        },
        "val": {
            "$none": { "$unit": 4711 }
        },
        "val2": {
            "$unit": 4711
        }
    },
    "$orderby": {
        "test.name": 0,
        "name": 1,
        "unit_under_test": {
            "name":1
        } 
    },
    "$groupby": {
        "test": {
            "id": 1
        }
    }
}''')


_jp_aggregates = { '$none': wodson_pb2.DataMatrix.Column.NONE, '$count': wodson_pb2.DataMatrix.Column.COUNT, '$dcount': wodson_pb2.DataMatrix.Column.DCOUNT, '$min': wodson_pb2.DataMatrix.Column.MIN, '$max': wodson_pb2.DataMatrix.Column.MAX, '$avg': wodson_pb2.DataMatrix.Column.AVG, '$sum': wodson_pb2.DataMatrix.Column.SUM, '$distinct': wodson_pb2.DataMatrix.Column.DISTINCT, '$point': wodson_pb2.DataMatrix.Column.POINT}
_jp_operands = { '$eq': wodson_pb2.Request.ConditionArrayItem.Condition.EQ, '$neq': wodson_pb2.Request.ConditionArrayItem.Condition.NEQ, '$lt': wodson_pb2.Request.ConditionArrayItem.Condition.LT, '$gt': wodson_pb2.Request.ConditionArrayItem.Condition.GT, '$lte': wodson_pb2.Request.ConditionArrayItem.Condition.LTE, '$gte': wodson_pb2.Request.ConditionArrayItem.Condition.GTE, '$inset': wodson_pb2.Request.ConditionArrayItem.Condition.INSET, '$notinset': wodson_pb2.Request.ConditionArrayItem.Condition.NOTINSET, '$like': wodson_pb2.Request.ConditionArrayItem.Condition.LIKE, '$null': wodson_pb2.Request.ConditionArrayItem.Condition.ISNULL, '$notnull': wodson_pb2.Request.ConditionArrayItem.Condition.ISNOTNULL, '$notlike': wodson_pb2.Request.ConditionArrayItem.Condition.NOTLIKE, '$between': wodson_pb2.Request.ConditionArrayItem.Condition.BETWEEN }

def ParseOptions(target, elemDict):
    for elem in elemDict:
        if elem.startswith('$'):
            if "$rowlimit" == elem:
                target.rowlimit = long(elemDict[elem])
            elif "$rowskip" == elem:
                target.rowskip = long(elemDict[elem])
            elif "$seqlimit" == elem:
                target.seqlimit = long(elemDict[elem])
            elif "$seqskip" == elem:
                target.seqskip = long(elemDict[elem])
            else:
                raise SyntaxError('Undefined options "' + elem + '"')
        else:
            raise SyntaxError('No undefined options allowed "' + elem + '"')

def ParseAttributes(target, elemDict, attrib):

    for elem in elemDict:

        elemAttrib = attrib.copy()

        if elem.startswith('$'):
            if elem in _jp_aggregates:
                elemAttrib['aggr'] = _jp_aggregates[elem]
            elif '$unit' == elem:
                elemAttrib['unit'] = elemDict[elem]
            elif '$calculated' == elem:
                raise SyntaxError('currently not supported "' + elem + '"')
            elif '$options' == elem:
                raise SyntaxError('Actually no $options defined for attributes')
            else:
                raise SyntaxError('Unknown aggregate "' + elem + '"')
        else:
            elemAttrib['path']
            if elemAttrib['path']:
                elemAttrib['path'] += '.'
            elemAttrib['path'] += elem

        if isinstance(elemDict[elem], dict):
            ParseAttributes(target, elemDict[elem], elemAttrib)
        elif isinstance(elemDict[elem], list):
            raise SyntaxError('attributes is not allowed to contain arrays')
        else:
            pAttrib = target.attributes.add()
            pAttrib.path = elemAttrib['path']
            pAttrib.aggregate = elemAttrib['aggr']
            if 0 != elemAttrib['unit']:
                pAttrib.unit = elemAttrib['unit']

def ParseOrderBy(target, elemDict, attrib):
    
    for elem in elemDict:

        elemAttrib = attrib.copy()

        if elem.startswith('$'):
            raise SyntaxError('no predefinded element "' + elem + '" defined in orderby')

        elemAttrib['path']
        if elemAttrib['path']:
            elemAttrib['path'] += '.'
        elemAttrib['path'] += elem

        if isinstance(elemDict[elem], dict):
            ParseOrderBy(target, elemDict[elem], elemAttrib)
        elif isinstance(elemDict[elem], list):
            raise SyntaxError('attributes is not allowed to contain arrays')
        else:
            pAttrib = target.orderby.add()
            pAttrib.path = elemAttrib['path']
            if 0 == elemDict[elem]:
                pAttrib.order = wodson_pb2.Request.OrderbyItem.DESCENDING
            elif 1 == elemDict[elem]:
                pAttrib.order = wodson_pb2.Request.OrderbyItem.ASCENDING
            else:
                raise SyntaxError(str(elemDict[elem]) + ' not supported for orderby')

def ParseGroupBy(target, elemDict, attrib):
    
    for elem in elemDict:

        elemAttrib = attrib.copy()

        if elem.startswith('$'):
            raise SyntaxError('no predefinded element "' + elem + '" defined in orderby')

        elemAttrib['path']
        if elemAttrib['path']:
            elemAttrib['path'] += '.'
        elemAttrib['path'] += elem

        if isinstance(elemDict[elem], dict):
            ParseGroupBy(target, elemDict[elem], elemAttrib)
        elif isinstance(elemDict[elem], list):
            raise SyntaxError('attributes is not allowed to contain arrays')
        else:
            pAttrib = target.groupby.add()
            pAttrib.path = elemAttrib['path']
            if 1 != elemDict[elem]:
                raise SyntaxError(str(elemDict[elem]) + ' only 1 supported in groupby')

def ParseConditionsConjuction(conjunction, target, elemDict, attrib):
    if not isinstance(elemDict, list):
        raise SyntaxError('$and and $or must always contain array')

    if attrib['conjuctionCount'] > 0:
        target.conditions.add().conjunction = attrib['conjuction']

    elemAttrib = attrib.copy()
    elemAttrib['conjuctionCount'] = 0
    elemAttrib['conjuction'] =  wodson_pb2.Request.ConditionArrayItem.AND

    if len(elemDict) > 1:
        target.conditions.add().conjunction = wodson_pb2.Request.ConditionArrayItem.OPEN

    firstTime = True
    for elem in elemDict:
        if not isinstance(elemDict, object):
            raise SyntaxError('$and and $or array always contains objects')
        
        if not firstTime:
            target.conditions.add().conjunction = conjunction

        target.conditions.add().conjunction = wodson_pb2.Request.ConditionArrayItem.OPEN
        ParseConditions(target, elem, attrib)
        target.conditions.add().conjunction = wodson_pb2.Request.ConditionArrayItem.CLOSE
        firstTime = False
    
    if len(elemDict) > 1:
        target.conditions.add().conjunction = wodson_pb2.Request.ConditionArrayItem.CLOSE

def ParseConditionsNot(target, elemDict, attrib):
    if not isinstance(elemDict, object):
        raise SyntaxError('$not must always contain object')

    if elemAttrib['conjuctionCount'] > 0:
        target.conditions.add().conjunction = elemAttrib['conjuction']

    elemAttrib = attrib.copy()
    elemAttrib['conjuctionCount'] = 0
    elemAttrib['conjuction'] =  wodson_pb2.Request.ConditionArrayItem.AND

    target.conditions.add().conjunction = wodson_pb2.Request.ConditionArrayItem.NOT
    target.conditions.add().conjunction = wodson_pb2.Request.ConditionArrayItem.OPEN
    ParseConditions(target, elemDict, attrib)
    target.conditions.add().conjunction = wodson_pb2.Request.ConditionArrayItem.CLOSE

def ParseConditions(target, elemDict, attrib):
    for elem in elemDict:

        elemAttrib = attrib.copy()

        if elem.startswith('$'):
            if elem in _jp_operands:
                elemAttrib['operator'] = _jp_operands[elem]
            elif '$and' == elem:
                ParseConditionsConjuction(wodson_pb2.Request.ConditionArrayItem.AND, target, elemDict[elem], attrib)
                attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1
                continue
            elif '$or' == elem:
                ParseConditionsConjuction(wodson_pb2.Request.ConditionArrayItem.OR, target, elemDict[elem], attrib)
                attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1
                continue
            elif '$not' == elem:
                ParseConditionsNot(target, elemDict[elem], attrib)
                attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1
                continue
            elif '$options' == elem:
                continue
            else:
                raise SyntaxError('Unknown aggregate "' + elem + '"')
        else:
            elemAttrib['path']
            if elemAttrib['path']:
                elemAttrib['path'] += '.'
            elemAttrib['path'] += elem

        if isinstance(elemDict[elem], dict):
            ParseConditions(target, elemDict[elem], elemAttrib)
        else:
            if 0 != attrib['conjuctionCount']:
                pConjunction = target.conditions.add().conjunction = elemAttrib['conjuction']

            pCondition = target.conditions.add().condition
            attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1
            pCondition.path = elemAttrib['path']
            pCondition.operator = elemAttrib['operator']
            operandValue = elemDict[elem]
            # !!! we need to determine the model attribute type to figure out where to store the Json Values in pCondition.value. in this code we write them all to string
            if isinstance(operandValue, list):
                for currVal in operandValue:
                    pCondition.value_string.values.append(str(currVal)) 
            else:
                pCondition.value_string.values.append(str(operandValue))


target = wodson_pb2.Request()

for elem in query:
    if '$options' == elem:
        ParseOptions(target, query[elem])
    elif '$attributes' == elem:
        ParseAttributes(target, query[elem], {'path': '', 'aggr': wodson_pb2.DataMatrix.Column.NONE, 'unit': 0})
    elif '$orderby' == elem:
        ParseOrderBy(target, query[elem],{'path': '', 'order': wodson_pb2.Request.OrderbyItem.ASCENDING})
    elif '$groupby' == elem:
        ParseGroupBy(target, query[elem],{'path': ''})
    else:
        target.entity = elem
        ParseConditions(target, query[elem], {'conjuction': wodson_pb2.Request.ConditionArrayItem.AND, 'conjuctionCount': 0, 'path':'', 'operator': wodson_pb2.Request.ConditionArrayItem.Condition.EQ})

print json_format.MessageToJson(target, False)
