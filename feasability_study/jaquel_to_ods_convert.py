import json

import datetime
import time
import logging
import org
import odslib

from sys import maxsize, maxint

_jo_aggregates = { '$none': org.asam.ods.NONE, '$count': org.asam.ods.COUNT, '$dcount': org.asam.ods.DCOUNT, '$min': org.asam.ods.MIN, '$max': org.asam.ods.MAX, '$avg': org.asam.ods.AVG, '$sum': org.asam.ods.SUM, '$distinct': org.asam.ods.DISTINCT, '$point': org.asam.ods.POINT}
_jo_operators = { '$eq': org.asam.ods.EQ, '$neq': org.asam.ods.NEQ, '$lt': org.asam.ods.LT, '$gt': org.asam.ods.GT, '$lte': org.asam.ods.LTE, '$gte': org.asam.ods.GTE, '$inset': org.asam.ods.INSET, '$notinset': org.asam.ods.NOTINSET, '$like': org.asam.ods.LIKE, '$null': org.asam.ods.IS_NULL, '$notnull': org.asam.ods.IS_NOT_NULL, '$notlike': org.asam.ods.NOTLIKE, '$between': org.asam.ods.BETWEEN }
_jo_operators_ci_map = { org.asam.ods.EQ: org.asam.ods.CI_EQ, org.asam.ods.NEQ: org.asam.ods.CI_NEQ, org.asam.ods.LT: org.asam.ods.CI_LT, org.asam.ods.GT: org.asam.ods.CI_GT, org.asam.ods.LTE: org.asam.ods.CI_LTE, org.asam.ods.GTE: org.asam.ods.CI_GTE, org.asam.ods.INSET: org.asam.ods.CI_INSET, org.asam.ods.NOTINSET: org.asam.ods.CI_NOTINSET, org.asam.ods.LIKE: org.asam.ods.CI_LIKE, org.asam.ods.NOTLIKE: org.asam.ods.CI_NOTLIKE }

def _jo_enum(model, aaApplElem, aaName, nameOrIndex):
    if isinstance(nameOrIndex, basestring):
        return long(model.GetEnumIndex(aaApplElem, aaName, nameOrIndex))

    return long(nameOrIndex)


def _jo_date(dateVal):
    if dateVal.endswith('Z'):
        tv = datetime.datetime.strptime(dateVal, '%Y-%m-%dT%H:%M:%S.%fZ')
        return tv.strftime("%Y%I%d%H%M%S%f").rstrip('0')

    return dateVal.encode('utf-8')


def _parse_path_and_add_joins(model, applElem, attribPath, joinSeq):
    aaType = org.asam.ods.DT_UNKNOWN
    aaName = ""
    aaApplElem = applElem
    pathParts = attribPath.split(".")
    nrOfPathParts = len(pathParts)
    for i in range(nrOfPathParts):
        pathPart = pathParts[i]
        joinType = org.asam.ods.JTDEFAULT
        if pathPart.endswith(':OUTER'):
            pathPart = pathPart[:-6]
            joinType = org.asam.ods.JTOUTER

        if(i != nrOfPathParts - 1):
            # Must be a relation
            relation = model.GetRelationEx(aaApplElem.aeName, pathPart)
            aaName = relation.arName
            aaApplElem = model.GetElemByAid(relation.elem2)

            # add join
            if (-1 == relation.arRelationRange.max) and (1 == relation.invRelationRange.max):
                realRelation = model.FindInverseRelation(relation)
                odslib._add_join_to_seq(realRelation, joinSeq,  joinType)
            else:
                odslib._add_join_to_seq(relation, joinSeq,  joinType)
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


def _parse_global_options(elemDict, target):
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


def _parse_attributes(model, applElem, target, elemDict, attrib):

    for elem in elemDict:

        elemAttrib = attrib.copy()

        if elem.startswith('$'):
            if elem in _jo_aggregates:
                elemAttrib['aggr'] = _jo_aggregates[elem]
            elif '$unit' == elem:
                elemAttrib['unit'] = elemDict[elem]
                continue
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
            _parse_attributes(model, applElem, target, elemDict[elem], elemAttrib)
        elif isinstance(elemDict[elem], list):
            raise SyntaxError('attributes is not allowed to contain arrays')
        else:
            aaType, aaName, aaApplElem = _parse_path_and_add_joins(model, applElem, elemAttrib['path'], target.joinSeq)
            target.anuSeq.append(org.asam.ods.SelAIDNameUnitId(org.asam.ods.AIDName(aaApplElem.aid, aaName), odslib.Int2LL(elemAttrib['unit']), elemAttrib['aggr']))


def _parse_orderby(model, applElem, target, elemDict, attrib):
    
    for elem in elemDict:

        elemAttrib = attrib.copy()

        if elem.startswith('$'):
            raise SyntaxError('no predefinded element "' + elem + '" defined in orderby')

        elemAttrib['path']
        if elemAttrib['path']:
            elemAttrib['path'] += '.'
        elemAttrib['path'] += elem

        if isinstance(elemDict[elem], dict):
            _parse_orderby(model, applElem, target, elemDict[elem], elemAttrib)
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


def _parse_groupby(model, applElem, target, elemDict, attrib):
    
    for elem in elemDict:

        elemAttrib = attrib.copy()

        if elem.startswith('$'):
            raise SyntaxError('no predefinded element "' + elem + '" defined in orderby')

        elemAttrib['path']
        if elemAttrib['path']:
            elemAttrib['path'] += '.'
        elemAttrib['path'] += elem

        if isinstance(elemDict[elem], dict):
            _parse_groupby(model, applElem, target, elemDict[elem], elemAttrib)
        elif isinstance(elemDict[elem], list):
            raise SyntaxError('attributes is not allowed to contain arrays')
        else:
            if 1 != elemDict[elem]:
                raise SyntaxError(str(elemDict[elem]) + ' only 1 supported in groupby')
            aaType, aaName, aaApplElem = _parse_path_and_add_joins(model, applElem, elemAttrib['path'], target.joinSeq)
            target.groupBy.append(org.asam.ods.AIDName(aaApplElem.aid, aaName))


def _parse_conditions_conjuction(model, applElem, conjunction, target, elemDict, attrib):
    if not isinstance(elemDict, list):
        raise SyntaxError('$and and $or must always contain array')

    if attrib['conjuctionCount'] > 0:
        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, attrib['conjuction']))

    if len(elemDict) > 1:
        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.OPEN))

    firstTime = True
    for elem in elemDict:
        if not isinstance(elemDict, object):
            raise SyntaxError('$and and $or array always contains objects')
        
        if not firstTime:
            target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, conjunction))

        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.OPEN))
        elemAttrib = attrib.copy()
        elemAttrib['conjuctionCount'] = 0
        elemAttrib['conjuction'] =  org.asam.ods.AND
        elemAttrib['options'] = ''
        _parse_conditions(model, applElem, target, elem, elemAttrib)
        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.CLOSE))
        firstTime = False
    
    if len(elemDict) > 1:
        target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.CLOSE))


def _parse_conditions_not(model, applElem, target, elemDict, attrib):
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
    _parse_conditions(model, applElem, target, elemDict, attrib)
    target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.CLOSE))


def _create_tsvalue(model, aaApplElem, aaName, aaType, srcValues):

    if isinstance(srcValues, list):
        if aaType == org.asam.ods.DT_COMPLEX and 2 == len(srcValues):
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_COMPLEX(float(srcValues[0]),float(srcValues[1]))), 15)
        elif aaType == org.asam.ods.DT_DCOMPLEX and 2 == len(srcValues):
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_DCOMPLEX(float(srcValues[0]),float(srcValues[1]))), 15)
        elif aaType == org.asam.ods.DT_EXTERNALREFERENCE and 3 == len(srcValues):
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_ExternalReference(srcValues[0].encode('utf-8'),srcValues[1].encode('utf-8'),srcValues[2].encode('utf-8'))), 15)
        #go on with seq target
        elif aaType == org.asam.ods.DT_BYTE or aaType == org.asam.ods.DS_BYTE:
            destVals = []
            for srcVal in srcValues:
                destVals.append(int(srcVal))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_BYTE, destVals), 15)
        elif aaType == org.asam.ods.DT_BOOLEAN or aaType == org.asam.ods.DS_BOOLEAN:
            destVals = []
            for srcVal in srcValues:
                destVals.append(org.asam.ods.T_BOOLEAN(int(srcVal)))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_BOOLEAN, destVals), 15)
        elif aaType == org.asam.ods.DT_SHORT or aaType == org.asam.ods.DS_SHORT:
            destVals = []
            for srcVal in srcValues:
                destVals.append(int(srcVal))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_SHORT, destVals), 15)
        elif aaType == org.asam.ods.DT_LONG or aaType == org.asam.ods.DS_LONG:
            destVals = []
            for srcVal in srcValues:
                destVals.append(long(srcVal))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_LONG, destVals), 15)
        elif aaType == org.asam.ods.DT_LONGLONG or aaType == org.asam.ods.DS_LONGLONG:
            destVals = []
            for srcVal in srcValues:
                destVals.append(odslib.Int2LL(long(srcVal)))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_LONGLONG, destVals), 15)
        elif aaType == org.asam.ods.DT_FLOAT or aaType == org.asam.ods.DS_FLOAT:
            destVals = []
            for srcVal in srcValues:
                destVals.append(float(srcVal))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_FLOAT, destVals), 15)
        elif aaType == org.asam.ods.DT_DOUBLE or aaType == org.asam.ods.DS_DOUBLE:
            destVals = []
            for srcVal in srcValues:
                destVals.append(float(srcVal))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_DOUBLE, destVals), 15)
        elif aaType == org.asam.ods.DT_DATE or aaType == org.asam.ods.DS_DATE:
            destVals = []
            for srcVal in srcValues:
                destVals.append(_jo_date(srcVal))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_DATE, destVals), 15)
        elif aaType == org.asam.ods.DT_STRING or aaType == org.asam.ods.DS_STRING:
            destVals = []
            for srcVal in srcValues:
                destVals.append(str(srcVal).encode('utf-8'))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_STRING, destVals), 15)
        elif aaType == org.asam.ods.DT_ENUM or aaType == org.asam.ods.DS_ENUM:
            destVals = []
            for srcVal in srcValues:
                destVals.append(_jo_enum(model, aaApplElem, aaName, srcVal))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_ENUM, destVals), 15)
        elif aaType == org.asam.ods.DT_COMPLEX or aaType == org.asam.ods.DS_COMPLEX:
            destVals = []
            for srcIndex in range(0, len(srcValues), 2):
                destVals.append(org.asam.ods.T_COMPLEX(float(srcValues[srcIndex * 2 + 0]),float(srcValues[srcIndex * 2 + 1])))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_COMPLEX, destVals), 15)
        elif aaType == org.asam.ods.DT_DCOMPLEX or aaType == org.asam.ods.DS_DCOMPLEX:
            destVals = []
            for srcIndex in range(0, len(srcValues), 2):
                destVals.append(org.asam.ods.T_DCOMPLEX(float(srcValues[srcIndex * 2 + 0]),float(srcValues[srcIndex * 2 + 1])))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_DCOMPLEX, destVals), 15)
        elif aaType == org.asam.ods.DT_EXTERNALREFERENCE or aaType == org.asam.ods.DS_EXTERNALREFERENCE:
            destVals = []
            for srcIndex in range(0, len(srcValues), 3):
                destVals.append(org.asam.ods.T_ExternalReference(srcValues[0].encode('utf-8'),srcValues[1].encode('utf-8'),srcValues[1].encode('utf-8')))
            return org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DS_DCOMPLEX, destVals), 15)
        else:
            raise Exception("Unknown how to attach array, does not exist as " + str(aaType) + " union.")

    if aaType == org.asam.ods.DT_BYTE:
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_BYTE(int(srcValues))), 15)
    elif aaType == org.asam.ods.DT_BOOLEAN:
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_BOOLEAN(int(srcValues))), 15)
    elif aaType == org.asam.ods.DT_SHORT:
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, int(srcValues)), 15)
    elif aaType == org.asam.ods.DT_LONG:
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, long(srcValues)), 15)
    elif aaType == org.asam.ods.DT_LONGLONG:
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, odslib.Int2LL(long(srcValues))), 15)
    elif aaType == org.asam.ods.DT_FLOAT:
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, float(srcValues)), 15)
    elif aaType == org.asam.ods.DT_DOUBLE:
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, float(srcValues)), 15)
    elif aaType == org.asam.ods.DT_DATE:
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, _jo_date(srcValues)), 15)
    elif aaType == org.asam.ods.DT_STRING:
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, srcValues.encode('utf-8')), 15)
    elif aaType == org.asam.ods.DT_ENUM:
        return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, _jo_enum(model, aaApplElem, aaName, srcValues)), 15)
    else:
        raise Exception("Unknown how to attach '" + srcValues + "' does not exist as " + str(aaType) + " union.")


def _get_ods_operator(aaType, conditionOperator, conditionOptions):
    if org.asam.ods.DT_STRING == aaType or org.asam.ods.DS_STRING == aaType:
        if -1 != conditionOptions.find('i'):
            # check if there is an CI operator
            if conditionOperator in _jo_operators_ci_map:
                return _jo_operators_ci_map[conditionOperator]

    return conditionOperator


def _add_condition(model, applElem, target, conditionPath, conditionOperator, conditionOperandValue, conditionUnitId, conditionOptions):
    aaType, aaName, aaApplElem = _parse_path_and_add_joins(model, applElem, conditionPath, target.joinSeq)
    oper = _get_ods_operator(aaType, conditionOperator, conditionOptions)
    tsValue = _create_tsvalue(model, aaApplElem, aaName, aaType, conditionOperandValue)
    selValExt = org.asam.ods.SelValueExt(org.asam.ods.AIDNameUnitId(org.asam.ods.AIDName(aaApplElem.aid, aaName), odslib.Int2LL(conditionUnitId)), oper, tsValue)
    selItem = org.asam.ods.SelItem(org.asam.ods.SEL_VALUE_TYPE, selValExt)
    target.condSeq.append(selItem)


def _parse_conditions(model, applElem, target, elemDict, attrib):

    for elem in elemDict:

        elemAttrib = attrib.copy()
        if '$options' in elemDict:
            elemAttrib['options'] = elemDict['$options']

        if elem.startswith('$'):
            if elem in _jo_operators:
                elemAttrib['operator'] = _jo_operators[elem]
            elif '$unit' == elem:
                elemAttrib['unit'] = elemDict[elem]
            elif '$and' == elem:
                _parse_conditions_conjuction(model, applElem, org.asam.ods.AND, target, elemDict[elem], attrib)
                attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1
                continue
            elif '$or' == elem:
                _parse_conditions_conjuction(model, applElem, org.asam.ods.OR, target, elemDict[elem], attrib)
                attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1
                continue
            elif '$not' == elem:
                _parse_conditions_not(model, applElem, target, elemDict[elem], attrib)
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
            oldConjuctionCount = elemAttrib['conjuctionCount']
            _parse_conditions(model, applElem, target, elemDict[elem], elemAttrib)
            if(oldConjuctionCount != elemAttrib['conjuctionCount']):
                attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1
        else:
            if 0 != attrib['conjuctionCount']:
                target.condSeq.append(org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, elemAttrib['conjuction']))

            conditionPath = elemAttrib['path']
            conditionOperator = elemAttrib['operator']
            conditionOperandValue = elemDict[elem]
            conditionOptions = elemAttrib['options']
            conditionUnitId = elemAttrib['unit']

            _add_condition(model, applElem, target, conditionPath, conditionOperator, conditionOperandValue, conditionUnitId, conditionOptions)
            attrib['conjuctionCount'] = attrib['conjuctionCount'] + 1


def JaquelToQueryStructureExt(model, jaquelQuery):
    
    if isinstance(jaquelQuery, dict):
        query = jaquelQuery
    else:
        query = json.loads(jaquelQuery)

    applElem = None
    aid = None

    qse = org.asam.ods.QueryStructureExt([],[],[],[],[])
    globalOptions = {'rowlimit': maxint, 'rowskip': 0, 'seqlimit': maxint, 'seqskip': 0 }

    # first parse conditions to get entity
    for elem in query:
        if not elem.startswith('$'):
            if not applElem is None:
                raise SyntaxError('Only one start point allowed "' + elem + '"')

            applElem = model.GetElemEx(elem)
            aid = applElem.aid
            if isinstance(query[elem], dict):
                _parse_conditions(model, applElem, qse, query[elem], {'conjuction': org.asam.ods.AND, 'conjuctionCount': 0, 'path':'', 'operator': org.asam.ods.EQ, 'options': '', 'unit': 0})
            else:
                # id given
                _add_condition(model, applElem, qse, 'id', org.asam.ods.EQ, long(query[elem]), 0, '')

    # parse the others
    for elem in query:
        if elem.startswith('$'):
            if '$attributes' == elem:
                _parse_attributes(model, applElem, qse, query[elem], {'path': '', 'aggr': org.asam.ods.NONE, 'unit': 0})
            elif '$orderby' == elem:
                _parse_orderby(model, applElem, qse, query[elem],{'path': ''})
            elif '$groupby' == elem:
                _parse_groupby(model, applElem, qse, query[elem],{'path': ''})
            elif '$options' == elem:
                _parse_global_options(query[elem], globalOptions)
            else:
                raise SyntaxError('unkonw first level define "' + elem + '"')

    if 0 == len(qse.anuSeq):
        qse.anuSeq.append(org.asam.ods.SelAIDNameUnitId(org.asam.ods.AIDName(aid, "*".encode('utf-8')), org.asam.ods.T_LONGLONG(0, 0), org.asam.ods.NONE))

    return applElem, qse, globalOptions
