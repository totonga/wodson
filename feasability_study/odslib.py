#!/usr/bin/env python
"""
Access ASAM Ods server via python using omniorb.

Copyright (c) 2015, Andreas Krantz
License: Apache 2.0 (http://www.apache.org/licenses/LICENSE-2.0.html)

"""

__author__ = "Andreas Krantz"
__license__ = "Apache 2.0"
__version__ = "0.0.1"
__maintainer__ = "Andreas Krantz"
__email__ = "totonga@gmail.com"
__status__ = "Prototype"

from omniORB import CORBA
import org
import re
import logging

_orb_obj = None


def _orb():
    global _orb_obj

    if _orb_obj is None:
        # Initialise the ORB
        orbStartParameter = []
        orbStartParameter.append("-ORBnativeCharCodeSet")
        orbStartParameter.append("UTF-8")
        orbStartParameter.append("-ORBgiopMaxMsgSize")
        orbStartParameter.append("268435456")  # 256 MB
        _orb_obj = CORBA.ORB_init(orbStartParameter, CORBA.ORB_ID)

    return _orb_obj

_attribute_parser = re.compile(r'\s*((?P<aggregate>(NONE)|(COUNT)|(DCOUNT)|(MIN)|(MAX)|(AVG)|(STDDEV)|(SUM)|(DISTINCT)|(POINT))\()?\s*?(?P<attribute>.*)')
_orderByParser = re.compile(r'\s*((?P<order>(ASCENDING)|(DESCENDING))\()?\s*?(?P<attribute>.*)')


def ValidFlag(flagVal):
    return 9 == flagVal & 9


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


def _add_join_to_seq(relation, joinSeq,  joinType):
    for join in joinSeq:
        if LL_Equal(join.fromAID, relation.elem1) and LL_Equal(join.toAID, relation.elem2) and (join.refName == relation.arName):
            # already in sequence
            return

    joinDef = org.asam.ods.JoinDef(relation.elem1, relation.elem2, relation.arName, joinType)
    joinSeq.append(joinDef)


def GetRelationType(relationType):
    if relationType == org.asam.ods.FATHER_CHILD:
        return "FATHER_CHILD"
    elif relationType == org.asam.ods.INFO:
        return "INFO"
    elif relationType == org.asam.ods.INHERITANCE:
        return "INHERITANCE"
    return None


def GetAggrTypeStr(aggrType):
    if aggrType == org.asam.ods.NONE:
        return "NONE"
    if aggrType == org.asam.ods.COUNT:
        return "COUNT"
    elif aggrType == org.asam.ods.DCOUNT:
        return "DCOUNT"
    elif aggrType == org.asam.ods.MIN:
        return "MIN"
    elif aggrType == org.asam.ods.MAX:
        return "MAX"
    elif aggrType == org.asam.ods.AVG:
        return "AVG"
    elif aggrType == org.asam.ods.STDDEV:
        return "STDDEV"
    elif aggrType == org.asam.ods.SUM:
        return "SUM"
    elif aggrType == org.asam.ods.DISTINCT:
        return "DISTINCT"
    elif aggrType == org.asam.ods.POINT:
        return "POINT"

    return None

def get_scalar_type(columnType):

    if columnType == org.asam.ods.DS_BYTE:
        return org.asam.ods.DT_BYTE
    elif columnType == org.asam.ods.DS_BOOLEAN:
        return org.asam.ods.DT_BOOLEAN
    elif columnType == org.asam.ods.DS_SHORT:
        return org.asam.ods.DT_SHORT
    elif columnType == org.asam.ods.DS_LONG:
        return org.asam.ods.DT_LONG
    elif columnType == org.asam.ods.DS_LONGLONG:
        return org.asam.ods.DT_LONGLONG
    elif columnType == org.asam.ods.DS_FLOAT:
        return org.asam.ods.DT_FLOAT
    elif columnType == org.asam.ods.DS_DOUBLE:
        return org.asam.ods.DT_DOUBLE
    elif columnType == org.asam.ods.DS_DATE:
        return org.asam.ods.DT_DATE
    elif columnType == org.asam.ods.DS_STRING:
        return org.asam.ods.DT_STRING
    elif columnType == org.asam.ods.DS_ENUM:
        return org.asam.ods.DT_ENUM
    elif columnType == org.asam.ods.DS_COMPLEX:
        return org.asam.ods.DT_COMPLEX
    elif columnType == org.asam.ods.DS_DCOMPLEX:
        return org.asam.ods.DT_DCOMPLEX
    elif columnType == org.asam.ods.DS_EXTERNALREFERENCE:
        return org.asam.ods.DT_EXTERNALREFERENCE
    elif columnType == org.asam.ods.DS_ID:
        return org.asam.ods.DT_ID
    
    return columnType

def GetDataTypeStr(dataType):
    columnType = dataType
    if columnType == org.asam.ods.DT_UNKNOWN:
        return "DT_UNKNOWN"
    if columnType == org.asam.ods.DT_BYTE:
        return "DT_BYTE"
    elif columnType == org.asam.ods.DT_BOOLEAN:
        return "DT_BOOLEAN"
    elif columnType == org.asam.ods.DT_SHORT:
        return "DT_SHORT"
    elif columnType == org.asam.ods.DT_LONG:
        return "DT_LONG"
    elif columnType == org.asam.ods.DT_LONGLONG:
        return "DT_LONGLONG"
    elif columnType == org.asam.ods.DT_FLOAT:
        return "DT_FLOAT"
    elif columnType == org.asam.ods.DT_DOUBLE:
        return "DT_DOUBLE"
    elif columnType == org.asam.ods.DT_DATE:
        return "DT_DATE"
    elif columnType == org.asam.ods.DT_STRING:
        return "DT_STRING"
    elif columnType == org.asam.ods.DT_ENUM:
        return "DT_ENUM"
    elif columnType == org.asam.ods.DT_COMPLEX:
        return "DT_COMPLEX"
    elif columnType == org.asam.ods.DT_DCOMPLEX:
        return "DT_DCOMPLEX"
    elif columnType == org.asam.ods.DT_EXTERNALREFERENCE:
        return "DT_EXTERNALREFERENCE"
    elif columnType == org.asam.ods.DS_BYTE:
        return "DS_BYTE"
    elif columnType == org.asam.ods.DS_BOOLEAN:
        return "DS_BOOLEAN"
    elif columnType == org.asam.ods.DS_SHORT:
        return "DS_SHORT"
    elif columnType == org.asam.ods.DS_LONG:
        return "DS_LONG"
    elif columnType == org.asam.ods.DS_LONGLONG:
        return "DS_LONGLONG"
    elif columnType == org.asam.ods.DS_FLOAT:
        return "DS_FLOAT"
    elif columnType == org.asam.ods.DS_DOUBLE:
        return "DS_DOUBLE"
    elif columnType == org.asam.ods.DS_DATE:
        return "DS_DATE"
    elif columnType == org.asam.ods.DS_STRING:
        return "DS_STRING"
    elif columnType == org.asam.ods.DS_ENUM:
        return "DS_ENUM"
    elif columnType == org.asam.ods.DS_COMPLEX:
        return "DS_COMPLEX"
    elif columnType == org.asam.ods.DS_DCOMPLEX:
        return "DS_DCOMPLEX"
    elif columnType == org.asam.ods.DS_EXTERNALREFERENCE:
        return "DS_EXTERNALREFERENCE"
    return None


def ExtractAttributeNameFromOrderByName(strVal):
    m = _orderByParser.search(strVal)
    aName = m.group("attribute")
    order = m.group("order")
    if not order is None:
        # cut closing bracket
        aName = aName.rstrip(" \t)")

    return aName, ("DESCENDING" != order)


def ExtractAttributeNameFromColumnName(columnName):
    m = _attribute_parser.search(columnName)
    aName = m.group("attribute")
    aAggrTypeStr = m.group("aggregate")
    aAggrType = org.asam.ods.NONE
    if not aAggrTypeStr is None:
        # cut closing bracket and determine aggregate type
        aName = aName.rstrip(" \t)")
        if 'NONE' == aAggrTypeStr: aAggrType = org.asam.ods.NONE
        elif 'COUNT' == aAggrTypeStr: aAggrType = org.asam.ods.COUNT
        elif 'DCOUNT' == aAggrTypeStr: aAggrType = org.asam.ods.DCOUNT
        elif 'MIN' == aAggrTypeStr: aAggrType = org.asam.ods.MIN
        elif 'MAX' == aAggrTypeStr: aAggrType = org.asam.ods.MAX
        elif 'AVG' == aAggrTypeStr: aAggrType = org.asam.ods.AVG
        elif 'STDDEV' == aAggrTypeStr: aAggrType = org.asam.ods.STDDEV
        elif 'SUM' == aAggrTypeStr: aAggrType = org.asam.ods.SUM
        elif 'DISTINCT' == aAggrTypeStr: aAggrType = org.asam.ods.DISTINCT
        elif 'POINT' == aAggrTypeStr: aAggrType = org.asam.ods.POINT
        else:
            raise Exception("Unknown aggregate type in '" + columnName + "'")

    return aName.strip(), aAggrType


def ColumnType(column):
    return column.value.u._d


def ColumnGetSeq(column):
    if org.asam.ods.DT_LONGLONG == column.value.u._d:
        rv = _column_get_seq(column)
        iSeq = []
        for val in rv:
            iSeq.append(LL2Int(val))
        return iSeq
    if org.asam.ods.DT_STRING == column.value.u._d:
        rv = _column_get_seq(column)
        iSeq = []
        for val in rv:
            iSeq.append(val.decode('utf-8'))
        return iSeq
    if org.asam.ods.DT_DATE == column.value.u._d:
        rv = _column_get_seq(column)
        iSeq = []
        for val in rv:
            iSeq.append(val.decode('utf-8'))
        return iSeq
    if org.asam.ods.DT_EXTERNALREFERENCE == column.value.u._d:
        rv = _column_get_seq(column)
        iSeq = []
        for val in rv:
            iSeq.append(val.description.decode('utf-8'))
            iSeq.append(val.mimeType.decode('utf-8'))
            iSeq.append(val.location.decode('utf-8'))
        return iSeq
    return _column_get_seq(column)


def _column_get_seq(column):
    columnType = column.value.u._d
    if columnType == org.asam.ods.DT_BYTE:
        return column.value.u.byteVal
    elif columnType == org.asam.ods.DT_BOOLEAN:
        return column.value.u.booleanVal
    elif columnType == org.asam.ods.DT_SHORT:
        return column.value.u.shortVal
    elif columnType == org.asam.ods.DT_LONG:
        return column.value.u.longVal
    elif columnType == org.asam.ods.DT_LONGLONG:
        return column.value.u.longlongVal
    elif columnType == org.asam.ods.DT_FLOAT:
        return column.value.u.floatVal
    elif columnType == org.asam.ods.DT_DOUBLE:
        return column.value.u.doubleVal
    elif columnType == org.asam.ods.DT_DATE:
        return column.value.u.dateVal
    elif columnType == org.asam.ods.DT_STRING:
        return column.value.u.stringVal
    elif columnType == org.asam.ods.DT_ENUM:
        return column.value.u.enumVal
    elif columnType == org.asam.ods.DT_COMPLEX:
        return column.value.u.complexVal
    elif columnType == org.asam.ods.DT_DCOMPLEX:
        return column.value.u.dcomplexVal
    elif columnType == org.asam.ods.DT_EXTERNALREFERENCE:
        return column.value.u.extRefVal
    elif columnType == org.asam.ods.DS_BYTE:
        return column.value.u.byteSeq
    elif columnType == org.asam.ods.DS_BOOLEAN:
        return column.value.u.booleanSeq
    elif columnType == org.asam.ods.DS_SHORT:
        return column.value.u.shortSeq
    elif columnType == org.asam.ods.DS_LONG:
        return column.value.u.longSeq
    elif columnType == org.asam.ods.DS_LONGLONG:
        return column.value.u.longlongSeq
    elif columnType == org.asam.ods.DS_FLOAT:
        return column.value.u.floatSeq
    elif columnType == org.asam.ods.DS_DOUBLE:
        return column.value.u.doubleSeq
    elif columnType == org.asam.ods.DS_DATE:
        return column.value.u.dateSeq
    elif columnType == org.asam.ods.DS_STRING:
        return column.value.u.dstringSeq
    elif columnType == org.asam.ods.DS_ENUM:
        return column.value.u.enumSeq
    elif columnType == org.asam.ods.DS_COMPLEX:
        return column.value.u.complexSeq
    elif columnType == org.asam.ods.DS_DCOMPLEX:
        return column.value.u.dcomplexSeq
    elif columnType == org.asam.ods.DS_EXTERNALREFERENCE:
        return column.value.u.extRefSeq

    logging.error("_column_get_seq: Unknown column type " + str(columnType))

    return None


def IsSequence(arrayType):
    if arrayType == org.asam.ods.DS_BYTE:
        return True
    elif arrayType == org.asam.ods.DS_BOOLEAN:
        return True
    elif arrayType == org.asam.ods.DS_SHORT:
        return True
    elif arrayType == org.asam.ods.DS_LONG:
        return True
    elif arrayType == org.asam.ods.DS_LONGLONG:
        return True
    elif arrayType == org.asam.ods.DS_FLOAT:
        return True
    elif arrayType == org.asam.ods.DS_DOUBLE:
        return True
    elif arrayType == org.asam.ods.DS_DATE:
        return True
    elif arrayType == org.asam.ods.DS_STRING:
        return True
    elif arrayType == org.asam.ods.DS_ENUM:
        return True
    elif arrayType == org.asam.ods.DS_COMPLEX:
        return True
    elif arrayType == org.asam.ods.DS_DCOMPLEX:
        return True
    elif arrayType == org.asam.ods.DS_EXTERNALREFERENCE:
        return True

    return False

def ColumnCountRows(column):
    seq = _column_get_seq(column)
    if seq is None:
        return 0
    return len(seq)


def LL0():
    return org.asam.ods.T_LONGLONG(0, 0)


def LL2Int(val):
    if 0 != val.high:
        rv = val.high << 32
        rv = rv | val.low
        return rv
    else:
        return val.low


def Int2LL(val):
    return org.asam.ods.T_LONGLONG(int((val >> 32) & 0xFFFFFFFF), int(val & 0xFFFFFFFF))


def LL_Equal(val1, val2):
    if val1.high != val2.high:
        return False
    if val1.low != val2.low:
        return False
    return True


def LL_Is0(val):
    if 0 != val.high:
        return False
    if 0 != val.low:
        return False
    return True


def GetTsValue(tsVal):

    if tsVal.u._d == org.asam.ods.DT_BYTE: return tsVal.u.byteVal
    elif tsVal.u._d == org.asam.ods.DT_BOOLEAN: return tsVal.u.booleanVal
    elif tsVal.u._d == org.asam.ods.DT_SHORT: return tsVal.u.shortVal
    elif tsVal.u._d == org.asam.ods.DT_LONG: return tsVal.u.longVal
    elif tsVal.u._d == org.asam.ods.DT_LONGLONG: return LL2Int(tsVal.u.longlongVal)
    elif tsVal.u._d == org.asam.ods.DT_FLOAT: return tsVal.u.floatVal
    elif tsVal.u._d == org.asam.ods.DT_DOUBLE: return tsVal.u.doubleVal
    elif tsVal.u._d == org.asam.ods.DT_DATE: return tsVal.u.dateVal
    elif tsVal.u._d == org.asam.ods.DT_STRING: return tsVal.u.stringVal
    elif tsVal.u._d == org.asam.ods.DT_ENUM: return tsVal.u.enumVal
    #elif aaType == org.asam.ods.DT_COMPLEX:
    #elif aaType == org.asam.ods.DT_DCOMPLEX:
    #elif aaType == org.asam.ods.DT_EXTERNALREFERENCE:
    else:
        raise Exception("Unable to read TS_Value.")


def CreateTsValue(aaType, strVal):

    if aaType == org.asam.ods.DT_BYTE: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_BYTE(int(strVal))), 15)
    elif aaType == org.asam.ods.DT_BOOLEAN: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_BOOLEAN(int(strVal))), 15)
    elif aaType == org.asam.ods.DT_SHORT: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_SHORT(int(strVal))), 15)
    elif aaType == org.asam.ods.DT_LONG: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_LONG(long(strVal))), 15)
    elif aaType == org.asam.ods.DT_LONGLONG: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, Int2LL(long(strVal))), 15)
    elif aaType == org.asam.ods.DT_FLOAT: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, float(strVal)), 15)
    elif aaType == org.asam.ods.DT_DOUBLE: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, float(strVal)), 15)
    elif aaType == org.asam.ods.DT_DATE: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, strVal.encode('utf-8')), 15)
    elif aaType == org.asam.ods.DT_STRING: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, strVal.encode('utf-8')), 15)
    elif aaType == org.asam.ods.DT_ENUM: return org.asam.ods.TS_Value(org.asam.ods.TS_Union(aaType, org.asam.ods.T_LONG(long(strVal))), 15)
    #elif aaType == org.asam.ods.DT_COMPLEX:
    #elif aaType == org.asam.ods.DT_DCOMPLEX:
    #elif aaType == org.asam.ods.DT_EXTERNALREFERENCE:
    else:
        raise Exception("Unknown how to attach '" + strVal + "' does not exist as " + str(aaType) + " union.")


def _get_session(params):

    objString = params['$URL']

    logging.info("ORB: resolve objecturl")
    obj = _orb().string_to_object(objString)
    if obj is None:
        return None
    logging.info("ORB: object retrieved")
    factory = obj._narrow(org.asam.ods.AoFactory)
    if (factory is None):
        return None

    logging.info("ORB: Got factory")

    nvs = []
    for paramName,  paramValue in params.iteritems():
        if not paramName.startswith('$'):
            nvs.append(org.asam.ods.NameValue(paramName.encode('utf-8'), org.asam.ods.TS_Value(org.asam.ods.TS_Union(org.asam.ods.DT_STRING, paramValue.encode('utf-8')), 15)))

    logging.info("AoFactory: Establish new session")
    session = factory.newSessionNameValue(nvs)
    if session is None:
        return None
    logging.info("AoFactory: Session retrieved")
    return session


class CModel:
    model_ = None
    enums_ = None
    enumAttribs_ = None

    def __init__(self, session):
        self.model_ = session.getApplicationStructureValue()

        try:
            self.enums_ = session.getEnumerationStructure()
        except org.asam.ods.AoException, ex:
            logging.error('Unable to retrieve enum struct:' + ex)
        except CORBA.BAD_OPERATION, ex:
            logging.error('Unable to retrieve enum struct:' + ex)

        try:
            self.enumAttribs_ = session.getEnumerationAttributes()
        except org.asam.ods.AoException, ex:
            logging.error('Unable to retrieve enum attributes:' + ex)
        except CORBA.BAD_OPERATION, ex:
            logging.error('Unable to retrieve enum attributes:' + ex)

    def GetEnumIndex(self, elem, aaName, name):
        enumName = self.GetEnumName(elem.aid, aaName)
        for enum in self.enums_:
            if enumName == enum.enumName:
                for enumItem in enum.items:
                    if name == enumItem.itemName:
                        return enumItem.index
                raise Exception("Enum '" + enumName + "' does not contain item named '" + name + "'")
        raise Exception("Enum not resolvable")


    def GetEnumName(self, aid, aaName):
        for enumAttrib in self.enumAttribs_:
            if aaName == enumAttrib.aaName and LL_Equal(aid, enumAttrib.aid):
                return enumAttrib.enumName
        return None

    def Aid(self, aeName):
        elem = self.GetElem(aeName)
        return elem.aid

    def GetElemEx(self, strVal):
        rv = self.GetElem(strVal)
        if rv is None:
            rv = self.GetElemB(strVal)
        if rv is None and strVal.isdigit():
            rv = self.GetElemByAid(Int2LL(int(strVal)))
        return rv

    def GetElem(self, aeName):
        for elem in self.model_.applElems:
            if aeName == elem.aeName:
                return elem
        return None

    def GetElemB(self, beName):
        for elem in self.model_.applElems:
            if beName == elem.beName:
                return elem
        return None

    def GetElemByAid(self, aid):
        for elem in self.model_.applElems:
            if LL_Equal(elem.aid, aid):
                return elem
        return None

    def MapAttrNameToAaName(self, aeName, attribName):
        attr = self.GetAttributeEx(aeName, attribName)
        if not attr is None:
            return attr.aaName
        rel = self.GetRelationEx(aeName, attribName)
        if not rel is None:
            return rel.arName

        raise Exception("Attribute '" + aeName + "." + attribName + "' does not exist")

    def GetAttribute(self, aeName, aaName):
        elem = self.GetElem(aeName)
        for attr in elem.attributes:
            if attr.aaName == aaName:
                return attr
        return None

    def GetAttributeB(self, aeName, baName):
        elem = self.GetElem(aeName)
        for attr in elem.attributes:
            if attr.baName == baName:
                return attr
        return None

    def GetAttributeEx(self, aeName, attributeName):
        rv = self.GetAttribute(aeName, attributeName)
        if rv is None:
            rv = self.GetAttributeB(aeName, attributeName)
        if not rv is None:
            return rv

        return None

    def GetRelationByAid(self, aid, arName):
        for rel in self.model_.applRels:
            if LL_Equal(rel.elem1, aid) and rel.arName == arName:
                return rel
        return None

    def GetRelation(self, aeName, arName):
        aid = self.Aid(aeName)
        return self.GetRelationByAid(aid,  arName)

    def GetRelationEx(self, aeName, relationName):
        rv = self.GetRelation(aeName, relationName)
        if rv is None:
            rv = self.GetRelationB(aeName, relationName)
        if not rv is None:
            return rv

        return None

    def FindInverseRelation(self,  relation):
        return self.GetRelationByAid(relation.elem2,  relation.invName)

    def GetRelationB(self, aeName, brName):
        aid = self.Aid(aeName)
        for rel in self.model_.applRels:
            if LL_Equal(rel.elem1, aid) and rel.brName == brName:
                return rel
        return None

    def GetNRelationNames(self, aeName):
        rv = []
        aid = self.Aid(aeName)
        for rel in self.model_.applRels:
            if LL_Equal(rel.elem1, aid) and 1 != rel.arRelationRange.max:
                rv.append(rel.arName)
        return rv


class CSession:
    _aoSession = None
    # Model members
    _cModel = None
    # access data
    _applElemAccess = None

    def __init__(self, params):

        self._aoSession = _get_session(params)
        if self._aoSession is None:
            raise Exception("Retrieving session failed!")

        self._cModel = CModel(self._aoSession)
        self._applElemAccess = self._aoSession.getApplElemAccess()

    def __del__(self):
        try:
            self.Close()
        except:
            logging.info("Exception occured when closing session")

    def Model(self):
        return self._cModel

    def Close(self):
        if not self._aoSession is None:
            self._aoSession.close()
            self._aoSession = None

    def AsamPathCreate(self,  aid,  iid):
        applStruct = self._aoSession.getApplicationStructure()
        ae = applStruct.getElementById(aid)
        ie = ae.getInstanceById(Int2LL(iid))
        return ie.getAsamPath()

    def AsamPathResolve(self,  path):
        applStruct = self._aoSession.getApplicationStructure()
        ie = applStruct.getInstanceByAsamPath(path.encode('utf-8'))
        iid = ie.getId()
        entity = ie.getApplicationElement().getName()
        return entity,  LL2Int(iid)

    def GetContext(self, pattern):
       return self._aoSession.getContext(pattern.encode('utf-8'))

    def SetContextString(self, varName, varValue):
        self._aoSession.setContextString(varName.encode('utf-8'),  varValue.encode('utf-8'))

    def GetElementValues(self, aeName, conditionArray, attributeArray, orderByArray, groupByArray, how_many):

        if conditionArray is None: conditionArray = []
        if attributeArray is None: attributeArray = []
        if orderByArray is None: orderByArray = []
        if how_many is None: how_many = 0

        applElem = self.Model().GetElem(aeName)
        aid = applElem.aid

        anuSeq = []
        condSeq = []
        joinSeq = []
        orderBySeq = []
        groupBySeq = []

        if(0 == len(attributeArray)):
            anuSeq.append(org.asam.ods.SelAIDNameUnitId(org.asam.ods.AIDName(aid, "*"), org.asam.ods.T_LONGLONG(0, 0), org.asam.ods.NONE))
        else:
            for attributeItem in attributeArray:
                if("*" == attributeItem):
                    anuSeq.append(org.asam.ods.SelAIDNameUnitId(org.asam.ods.AIDName(aid, "*"), org.asam.ods.T_LONGLONG(0, 0), org.asam.ods.NONE))
                else:
                    attribPath, aAggrType = ExtractAttributeNameFromColumnName(attributeItem)
                    aaType, aaName, aaApplElem = _parse_path_and_add_joins(self.Model(), applElem, attribPath, joinSeq)
                    anuSeq.append(org.asam.ods.SelAIDNameUnitId(org.asam.ods.AIDName(aaApplElem.aid, aaName), org.asam.ods.T_LONGLONG(0, 0), aAggrType))

        for orderByItem in orderByArray:
            attribPath, ascending = ExtractAttributeNameFromOrderByName(orderByItem)
            aaType, aaName, aaApplElem = _parse_path_and_add_joins(self.Model(), applElem, attribPath, joinSeq)
            orderBySeq.append(org.asam.ods.SelOrder(org.asam.ods.AIDName(aaApplElem.aid, aaName), ascending))

        for attribPath in groupByArray:
            aaType, aaName, aaApplElem = _parse_path_and_add_joins(self.Model(), applElem, attribPath, joinSeq)
            groupBySeq.append(org.asam.ods.AIDName(aaApplElem.aid, aaName))

        if(len(conditionArray) > 0):
            expressionParser = re.compile(r'\s*(?P<attribute>.*?)\s*?(?P<operator>([!<>=][=]|[<>=]))\s*(?P<operand>.*)')
            caseSensitive = 1
            for part in conditionArray:
                if '$cs' == part:
                    caseSensitive = 1
                elif '$ci' == part:
                    caseSensitive = 0
                elif '$open' == part:
                    selItem = org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.OPEN)
                    condSeq.append(selItem)
                elif '$close' == part:
                    selItem = org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.CLOSE)
                    condSeq.append(selItem)
                elif '$or' == part:
                    selItem = org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.OR)
                    condSeq.append(selItem)
                elif '$and' == part:
                    selItem = org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.AND)
                    condSeq.append(selItem)
                elif '$not' == part:
                    selItem = org.asam.ods.SelItem(org.asam.ods.SEL_OPERATOR_TYPE, org.asam.ods.NOT)
                    condSeq.append(selItem)
                else:
                    #split condition
                    m = expressionParser.search(part)
                    attribPath = m.group("attribute")
                    operatorStr = m.group("operator")
                    operandStr = m.group("operand")

                    aaType, aaName, aaApplElem = _parse_path_and_add_joins(self.Model(), applElem, attribPath, joinSeq)

                    operator = None
                    if '=' == operatorStr:
                        if (org.asam.ods.DT_STRING == aaType or org.asam.ods.DS_STRING == aaType):
                            operator = org.asam.ods.LIKE if 1 == caseSensitive else org.asam.ods.CI_LIKE
                        else:
                            operator = org.asam.ods.EQ
                    elif '<>' == operatorStr:
                        if (org.asam.ods.DT_STRING == aaType or org.asam.ods.DS_STRING == aaType):
                            operator = org.asam.ods.NLIKE if 1 == caseSensitive else org.asam.ods.CI_NLIKE
                        else:
                            operator = org.asam.ods.NEQ
                    elif '==' == operatorStr: operator = org.asam.ods.EQ if ((org.asam.ods.DT_STRING == aaType or org.asam.ods.DS_STRING == aaType)) and 1 == caseSensitive else org.asam.ods.CI_EQ
                    elif '!=' == operatorStr: operator = org.asam.ods.NEQ if ((org.asam.ods.DT_STRING == aaType or org.asam.ods.DS_STRING == aaType)) and 1 == caseSensitive else org.asam.ods.CI_NEQ
                    elif '<' == operatorStr: operator = org.asam.ods.LT
                    elif '>' == operatorStr: operator = org.asam.ods.GT
                    elif '<=' == operatorStr: operator = org.asam.ods.LTE
                    elif '>=' == operatorStr: operator = org.asam.ods.GTE
                    else:
                        raise Exception("Query contains unknown operator '" + operatorStr + "'")

                    tsValue = CreateTsValue(aaType, operandStr)
                    selValExt = org.asam.ods.SelValueExt(org.asam.ods.AIDNameUnitId(org.asam.ods.AIDName(aaApplElem.aid, aaName), LL0()), operator, tsValue)
                    selItem = org.asam.ods.SelItem(org.asam.ods.SEL_VALUE_TYPE, selValExt)
                    condSeq.append(selItem)

        return self.GetInstancesEx(org.asam.ods.QueryStructureExt(anuSeq, condSeq, joinSeq, orderBySeq, groupBySeq), how_many)

    def GetInstancesEx(self, qse, how_many):

        logging.info('Call ApplElemAccess.getInstancesExt(aoq="' + str(qse).replace('org.asam.ods.','') + '", how_many=' + str(how_many) + '")')
        rs = self._applElemAccess.getInstancesExt(qse, how_many)
        for r in rs:
            return r.firstElems

        return None

class CSessionAutoReconnect:
    _cSession = None
    _params = {}

    def __init__(self, params):
        self._cSession = CSession(params)
        self._params = params

    def __del__(self):
        self._cSession = None

    def Close(self):
        # no need to reconnect
        self._cSession.Close()
        self._cSession = None

    def Model(self):
        # no need to reconnect
        return self._CSession().Model()

    def AsamPathCreate(self,  aid,  iid):
        try:
            return self._CSession().AsamPathCreate(aid, iid)
        except (CORBA.OBJECT_NOT_EXIST, CORBA.COMM_FAILURE, CORBA.TRANSIENT, CORBA.INV_OBJREF):
            return self._CSessionReconnect().AsamPathCreate(aid, iid)

    def AsamPathResolve(self,  path):
        try:
            return self._CSession().AsamPathResolve(path)
        except (CORBA.OBJECT_NOT_EXIST, CORBA.COMM_FAILURE, CORBA.TRANSIENT, CORBA.INV_OBJREF):
            return self._CSessionReconnect().AsamPathResolve(path)

    def GetContext(self, pattern):
        try:
            return self._CSession().GetContext(pattern)
        except (CORBA.OBJECT_NOT_EXIST, CORBA.COMM_FAILURE, CORBA.TRANSIENT, CORBA.INV_OBJREF):
            return self._CSessionReconnect().GetContext(pattern)

    def SetContextString(self, varName, varValue):
        try:
            self._CSession().SetContextString(varName,  varValue)
        except (CORBA.OBJECT_NOT_EXIST, CORBA.COMM_FAILURE, CORBA.TRANSIENT, CORBA.INV_OBJREF):
            self._CSessionReconnect().SetContextString(varName,  varValue)

    def GetElementValues(self, aeName, conditionArray, attributeArray, orderByArray, groupByArray, how_many):
        try:
            return self._CSession().GetElementValues(aeName, conditionArray, attributeArray, orderByArray, groupByArray, how_many)
        except (CORBA.OBJECT_NOT_EXIST, CORBA.COMM_FAILURE, CORBA.TRANSIENT, CORBA.INV_OBJREF):
            return self._CSessionReconnect().GetElementValues(aeName, conditionArray, attributeArray, orderByArray, groupByArray, how_many)
    
    def GetInstancesEx(self, qse, how_many):
        try:
            return self._CSession().GetInstancesEx(qse, how_many)
        except (CORBA.OBJECT_NOT_EXIST, CORBA.COMM_FAILURE, CORBA.TRANSIENT, CORBA.INV_OBJREF):
            return self._CSessionReconnect().GetInstancesEx(qse, how_many)

    def _CSessionReconnect(self):
        self._cSession = None
        return self._CSession()

    def _CSession(self):
        if self._cSession is None:
            self._cSession = CSession(self._params)
        return self._cSession
