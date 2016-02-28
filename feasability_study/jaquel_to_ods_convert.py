import json

import logging
import org
import odslib

from sys import maxsize


jaquelQueryString = '''{
                        "AoTest":{"name":{"$like":"abc","$options":"i"}},
                        "$options":{"$seqskip":5}
                       }'''

jaquelQueryString7 = '''{
                        "AoTest":{"name":{"$eq":"abc","$options":"i"}}
                       }'''


jaquelQueryString6 = '''{
                        "AoTest":12
                       }'''

jaquelQueryString5 = '''{
                        "AoTest":{},
                        "$attributes":{"id":1,"name":1},
                        "$orderby":{"name":1},
                        "$groupby":{"id":1}
                       }'''

jaquelQueryString4 = '''{
                        "AoTest":{},
                        "$attributes":{"id":1,"name":1},
                        "$orderby":{"name":1}
                       }'''

jaquelQueryString3 = '''{
                        "AoTest":{},
                        "$attributes":{"id":1,"name":1}
                       }'''

jaquelQueryString2 = '''{"AoTest":{}}'''

jaquelQueryString1 = '''{
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
}'''


_jo_aggregates = { '$none': org.asam.ods.NONE, '$count': org.asam.ods.COUNT, '$dcount': org.asam.ods.DCOUNT, '$min': org.asam.ods.MIN, '$max': org.asam.ods.MAX, '$avg': org.asam.ods.AVG, '$sum': org.asam.ods.SUM, '$distinct': org.asam.ods.DISTINCT, '$point': org.asam.ods.POINT}
_jo_operators = { '$eq': org.asam.ods.EQ, '$neq': org.asam.ods.NEQ, '$lt': org.asam.ods.LT, '$gt': org.asam.ods.GT, '$lte': org.asam.ods.LTE, '$gte': org.asam.ods.GTE, '$inset': org.asam.ods.INSET, '$notinset': org.asam.ods.NOTINSET, '$like': org.asam.ods.LIKE, '$null': org.asam.ods.IS_NULL, '$notnull': org.asam.ods.IS_NOT_NULL, '$notlike': org.asam.ods.NOTLIKE, '$between': org.asam.ods.BETWEEN }
_jo_operators_ci_map = { org.asam.ods.EQ: org.asam.ods.CI_EQ, org.asam.ods.NEQ: org.asam.ods.CI_NEQ, org.asam.ods.LT: org.asam.ods.CI_LT, org.asam.ods.GT: org.asam.ods.CI_GT, org.asam.ods.LTE: org.asam.ods.CI_LTE, org.asam.ods.GTE: org.asam.ods.CI_GTE, org.asam.ods.INSET: org.asam.ods.CI_INSET, org.asam.ods.NOTINSET: org.asam.ods.CI_NOTINSET, org.asam.ods.LIKE: org.asam.ods.CI_LIKE, org.asam.ods.NOTLIKE: org.asam.ods.CI_NOTLIKE }



def _parse_path_and_add_joins(model, applElem, attribPath, joinSeq):
    aaType = org.asam.ods.DT_UNKNOWN
    aaName = ""
    aaApplElem = applElem
    pathParts = attribPath.split(".")
    nrOfPathParts = len(pathParts)
    for i in range(nrOfPathParts):
        pathPart = pathParts[i]
        joinType = org.asam.ods.JTDEFAULT
        if ( pathPart.startswith('OUTER(') and pathPart.endswith(')') ):
            pathPart = pathPart[6:-1]
            joinType = org.asam.ods.JTOUTER

        if(i != nrOfPathParts - 1):
            # Must be a relation
            relation = model.GetRelationEx(aaApplElem.aeName, pathPart)
            aaName = relation.arName
            aaApplElem = model.GetElemByAid(relation.elem2)

            # add join
            if (-1 == relation.arRelationRange.max) and (1 == relation.invRelationRange.max):
                realRelation = model.FindInverseRelation(relation)
                _add_join_to_seq(realRelation, joinSeq,  joinType)
            else:
                _add_join_to_seq(relation, joinSeq,  joinType)
        else:
            # maybe relation or attribute
            attribute = model.GetAttributeEx(aaApplElem.aeName, pathPart)
            if not attribute is None:
                aaName = attribute.aaName
                aaType = attribute.dType
            else:
                relation = model.GetRelationEx(aaApplElem.aeName, pathPart)
                aaName = relation.arName
                aaType = org.asam.ods.DT_LONGLONG  # its an id
    return aaType, aaName, aaApplElem

def _ParseOptions(elemDict, target):
    for elem in elemDict:
        if elem.startswith('$'):
            if "$rowlimit" == elem:
                target['rowlimit'] = long(elemDict[elem])
            elif "$rowskip" == elem:
                target['rowskip'] = long(elemDict[elem])
            elif "$seqlimit" == elem:
                target['seqlimit'] = long(elemDict[elem])
            elif "$seqskip" == elem:
                target['seqskip'] = long(elemDict[elem])
            else:
                raise SyntaxError('Undefined options "' + elem + '"')
        else:
            raise SyntaxError('No undefined options allowed "' + elem + '"')

def _ParseAttributes(model, applElem, target, elemDict, attrib):

    for elem in elemDict:

        elemAttrib = attrib.copy()

        if elem.startswith('$'):
            if elem in _jo_aggregates:
                elemAttrib['aggr'] = _jo_aggregates[elem]
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
            _ParseAttributes(model, applElem, target, elemDict[elem], elemAttrib)
        elif isinstance(elemDict[elem], list):
            raise SyntaxError('attributes is not allowed to contain arrays')
        else:
            aaType, aaName, aaApplElem = _parse_path_and_add_joins(model, applElem, elemAttrib['path'], target.joinSeq)
            target.anuSeq.append(org.asam.ods.SelAIDNameUnitId(org.asam.ods.AIDName(aaApplElem.aid, aaName), odslib.Int2LL(elemAttrib['unit']), elemAttrib['aggr']))

def _ParseOrderBy(model, applElem, target, elemDict, attrib):
    
    for elem in elemDict:

        elemAttrib = attrib.copy()

        if elem.startswith('$'):
            raise SyntaxError('no predefinded element "' + elem + '" defined in orderby')

        elemAttrib['path']
        if elemAttrib['path']:
            elemAttrib['path'] += '.'
        elemAttrib['path'] += elem

        if isinstance(elemDict[elem], dict):
            _ParseOrderBy(model, applElem, target, elemDict[elem], elemAttrib)
        elif isinstance(elemDict[elem], list):
            raise SyntaxError('attributes is not allowed to contain arrays')
        else:
            aaType, aaName, aaApplElem = _parse_path_and_add_joins(model, applElem, elemAttrib['path'], target.joinSeq)
            ascending = True
            if 0 == elemDict[elem]:
                ascending = False
            elif 1 == elemDict[elem]:
                ascending = True
            else:
                raise SyntaxError(str(elemDict[elem]) + ' not supported for orderby')
            target.orderBy.append(org.asam.ods.SelOrder(org.asam.ods.AIDName(aaApplElem.aid, aaName), ascending))


def _ParseGroupBy(model, applElem, target, elemDict, attrib):
    
    for elem in elemDict:

        elemAttrib = attrib.copy()

        if elem.startswith('$'):
            raise SyntaxError('no predefinded element "' + elem + '" defined in orderby')

        elemAttrib['path']
        if elemAttrib['path']:
            elemAttrib['path'] += '.'
        elemAttrib['path'] += elem

        if isinstance(elemDict[elem], dict):
            _ParseGroupBy(model, applElem, target, elemDict[elem], elemAttrib)
        elif isinstance(elemDict[elem], list):
            raise SyntaxError('attributes is not allowed to contain arrays')
        else:
            if 1 != elemDict[elem]:
                raise SyntaxError(str(elemDict[elem]) + ' only 1 supported in groupby')
            aaType, aaName, aaApplElem = _parse_path_and_add_joins(model, applElem, elemAttrib['path'], target.joinSeq)
            target.groupBy.append(org.asam.ods.AIDName(aaApplElem.aid, aaName))


def _ParseConditionsConjuction(model, applElem, conjunction, target, elemDict, attrib):
    if not isinstance(elemDict, list):
        raise SyntaxError('$and and $or must always contain array')

    if attrib['conjuctionCount'] > 0:
        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, attrib['conjuction']))

    elemAttrib = attrib.copy()
    elemAttrib['conjuctionCount'] = 0
    elemAttrib['conjuction'] =  org.asam.ods.AND
    elemAttrib['options'] = ''

    if len(elemDict) > 1:
        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.OPEN))

    firstTime = True
    for elem in elemDict:
        if not isinstance(elemDict, object):
            raise SyntaxError('$and and $or array always contains objects')
        
        if not firstTime:
            target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, conjunction))

        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.OPEN))
        _ParseConditions(model, applElem, target, elem, attrib)
        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.CLOSE))
        firstTime = False
    
    if len(elemDict) > 1:
        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.CLOSE))

def _ParseConditionsNot(model, applElem, target, elemDict, attrib):
    if not isinstance(elemDict, object):
        raise SyntaxError('$not must always contain object')

    if elemAttrib['conjuctionCount'] > 0:
        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, elemAttrib['conjuction']))

    elemAttrib = attrib.copy()
    elemAttrib['conjuctionCount'] = 0
    elemAttrib['conjuction'] =  org.asam.ods.AND
    elemAttrib['options'] = ''

    org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.OPEN)
    target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.NOT))
    target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.OPEN))
    _ParseConditions(model, applElem, target, elemDict, attrib)
    target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.CLOSE))

def _CreateTsValue(aaType, srcValue):

    if isinstance(srcValue, list):
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, str(srcValue).encode('utf-8')), 15)

    if aaType == org.asam.ods.DT_BYTE: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_BYTE(int(srcValue))), 15)
    elif aaType == org.asam.ods.DT_BOOLEAN: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_BOOLEAN(int(srcValue))), 15)
    elif aaType == org.asam.ods.DT_SHORT: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_SHORT(int(srcValue))), 15)
    elif aaType == org.asam.ods.DT_LONG: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_LONG(long(srcValue))), 15)
    elif aaType == org.asam.ods.DT_LONGLONG: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, odslib.Int2LL(long(srcValue))), 15)
    elif aaType == org.asam.ods.DT_FLOAT: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, float(srcValue)), 15)
    elif aaType == org.asam.ods.DT_DOUBLE: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, float(srcValue)), 15)
    elif aaType == org.asam.ods.DT_DATE: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, srcValue.encode('utf-8')), 15)
    elif aaType == org.asam.ods.DT_STRING: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, srcValue.encode('utf-8')), 15)
    elif aaType == org.asam.ods.DT_ENUM: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_LONG(long(srcValue))), 15)
    #elif aaType == org.asam.ods.DT_COMPLEX:
    #elif aaType == org.asam.ods.DT_DCOMPLEX:
    #elif aaType == org.asam.ods.DT_EXTERNALREFERENCE:
    else:
        raise Exception("Unknown how to attach '" + srcValue + "' does not exist as " + str(aaType) + " union.")

def _GetOdsOperator(aaType, conditionOperator, conditionOptions):
    if org.asam.ods.DT_STRING == aaType or org.asam.ods.DS_STRING == aaType:
        if -1 != conditionOptions.find('i'):
            # check if there is an CI operator
            if conditionOperator in _jo_operators_ci_map:
                return _jo_operators_ci_map[conditionOperator]

    return conditionOperator

def _AddCondition(model, applElem, target, conditionPath, conditionOperator, conditionOperandValue, conditionUnitId, conditionOptions):
    aaType, aaName, aaApplElem = _parse_path_and_add_joins(model, applElem, conditionPath, target.joinSeq)
    oper = _GetOdsOperator(aaType, conditionOperator, conditionOptions)
    tsValue = _CreateTsValue(aaType, conditionOperandValue)
    selValExt = org.asam.ods.SelValueExt(org.asam.ods.AIDNameUnitId(org.asam.ods.AIDName(aaApplElem.aid, aaName), odslib.Int2LL(conditionUnitId)), oper, tsValue)
    selItem = org.asam.ods.SelItem(org.asam.ods.SEL_VALUE_TYPE, selValExt)
    target.condSeq.append(selItem)


def _ParseConditions(model, applElem, target, elemDict, attrib):

    for elem in elemDict:

        elemAttrib = attrib.copy()
        if '$options' in elemDict:
            elemAttrib['options'] = elemDict['$options']

        if elem.startswith('$'):
            if elem in _jo_operators:
                elemAttrib['operator'] = _jo_operators[elem]
            elif '$and' == elem:
                _ParseConditionsConjuction(model, applElem, org.asam.ods.AND, target, elemDict[elem], attrib)
                attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1
                continue
            elif '$or' == elem:
                _ParseConditionsConjuction(model, applElem, org.asam.ods.OR, target, elemDict[elem], attrib)
                attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1
                continue
            elif '$not' == elem:
                _ParseConditionsNot(model, applElem, target, elemDict[elem], attrib)
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
            _ParseConditions(model, applElem, target, elemDict[elem], elemAttrib)
        else:
            if 0 != attrib['conjuctionCount']:
                target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, elemAttrib['conjuction']))

            conditionPath = elemAttrib['path']
            conditionOperator = elemAttrib['operator']
            conditionOperandValue = elemDict[elem]
            conditionOptions = elemAttrib['options']
            conditionUnitId = 0

            _AddCondition(model, applElem, target, conditionPath, conditionOperator, conditionOperandValue, conditionUnitId, conditionOptions)
            attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1


def JaquelToQueryStructureExt(model, jaquelQueryStr):
    
    query = json.loads(jaquelQueryStr)

    applElem = None
    aid = None

    qse = org.asam.ods.QueryStructureExt([],[],[],[],[])
    globalOptions = {'rowlimit': maxsize, 'rowskip': 0, 'seqlimit': maxsize, 'seqskip': 0 }

    # first parse conditions to get entity
    for elem in query:
        if not elem.startswith('$'):
            if not applElem is None:
                raise SyntaxError('Only one start point allowed "' + elem + '"')

            applElem = model.GetElemEx(elem)
            aid = applElem.aid
            if isinstance(query[elem], dict):
                _ParseConditions(model, applElem, qse, query[elem], {'conjuction': org.asam.ods.AND, 'conjuctionCount': 0, 'path':'', 'operator': org.asam.ods.EQ, 'options': ''})
            else:
                # id given
                _AddCondition(model, applElem, qse, 'id', org.asam.ods.EQ, long(query[elem]), 0, '')

    # parse the others
    for elem in query:
        if elem.startswith('$'):
            if '$attributes' == elem:
                _ParseAttributes(model, applElem, qse, query[elem], {'path': '', 'aggr': org.asam.ods.NONE, 'unit': 0})
            elif '$orderby' == elem:
                _ParseOrderBy(model, applElem, qse, query[elem],{'path': ''})
            elif '$groupby' == elem:
                _ParseGroupBy(model, applElem, qse, query[elem],{'path': ''})
            elif '$options' == elem:
                _ParseOptions(query[elem], globalOptions)
            else:
                raise SyntaxError('unkonw first level define "' + elem + '"')

    if 0 == len(qse.anuSeq):
        qse.anuSeq.append(org.asam.ods.SelAIDNameUnitId(org.asam.ods.AIDName(aid, "*".encode('utf-8')), org.asam.ods.T_LONGLONG(0, 0), org.asam.ods.NONE))

    return qse, globalOptions


_session = odslib.CSessionAutoReconnect({u'$URL': u'corbaname::10.89.2.24:900#MeDaMak1.ASAM-ODS', u'USER': 'test', u'PASSWORD': u'test'})
_model = _session.Model()

target, options = JaquelToQueryStructureExt(_model, jaquelQueryString)
print str(target)
print str(options)


