#!/usr/bin/env python
"""
Access ASAM Ods python using omniorb and wrap it using swagger

Copyright (c) 2015, Andreas Krantz
License: Apache 2.0 (http://www.apache.org/licenses/LICENSE-2.0.html)
"""
__author__ = "Andreas Krantz"
__license__ = "Apache 2.0"
__version__ = "0.0.1"
__maintainer__ = "Andreas Krantz"
__email__ = "totonga@gmail.com"
__status__ = "Prototype"

import logging
import sys
import org
import OdsLib
import connexion

# from flask import Flask
from flask import render_template,  redirect,  jsonify
from flask import request
from connexion import NoContent

app = connexion.App(__name__)


context_vars__ = {}
session_obj__ = None

# initialize to do single call without init
context_vars__['URL'] = 'corbaname::10.89.2.24:900#MeDaMak1.ASAM-ODS'
context_vars__['USER'] = 'test'
context_vars__['PASSWORD'] = 'test'

def request_wants_json():
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json' and request.accept_mimetypes[best] > request.accept_mimetypes['text/html']

def GetDiscriminatorArrayName__(arrayType):
    if arrayType == org.asam.ods.DT_UNKNOWN:
        return "unknownSeq"
    if arrayType == org.asam.ods.DT_BYTE:
        return "numVal"
    elif arrayType == org.asam.ods.DT_BOOLEAN:
        return "numVal"
    elif arrayType == org.asam.ods.DT_SHORT:
        return "numVal"
    elif arrayType == org.asam.ods.DT_LONG:
        return "numVal"
    elif arrayType == org.asam.ods.DT_LONGLONG:
        return "numVal"
    elif arrayType == org.asam.ods.DT_FLOAT:
        return "numVal"
    elif arrayType == org.asam.ods.DT_DOUBLE:
        return "numVal"
    elif arrayType == org.asam.ods.DT_DATE:
        return "dateVal"
    elif arrayType == org.asam.ods.DT_STRING:
        return "strVal"
    elif arrayType == org.asam.ods.DT_ENUM:
        return "numVal"
    elif arrayType == org.asam.ods.DT_COMPLEX:
        return "numVal"
    elif arrayType == org.asam.ods.DT_DCOMPLEX:
        return "numVal"
    elif arrayType == org.asam.ods.DT_EXTERNALREFERENCE:
        return "strVal"
    elif arrayType == org.asam.ods.DS_BYTE:
        return "numSeq"
    elif arrayType == org.asam.ods.DS_BOOLEAN:
        return "numSeq"
    elif arrayType == org.asam.ods.DS_SHORT:
        return "numSeq"
    elif arrayType == org.asam.ods.DS_LONG:
        return "numSeq"
    elif arrayType == org.asam.ods.DS_LONGLONG:
        return "numSeq"
    elif arrayType == org.asam.ods.DS_FLOAT:
        return "numSeq"
    elif arrayType == org.asam.ods.DS_DOUBLE:
        return "numSeq"
    elif arrayType == org.asam.ods.DS_DATE:
        return "dateSeq"
    elif arrayType == org.asam.ods.DS_STRING:
        return "strSeq"
    elif arrayType == org.asam.ods.DS_ENUM:
        return "numSeq"
    elif arrayType == org.asam.ods.DS_COMPLEX:
        return "numVal"
    elif arrayType == org.asam.ods.DS_DCOMPLEX:
        return "numVal"
    elif arrayType == org.asam.ods.DS_EXTERNALREFERENCE:
        return "strSeq"
    return None


def Session__():
    global session_obj__

    if session_obj__ is None:
        sUrl = context_vars__['URL']
        sUsr = context_vars__['USER']
        sPwd = context_vars__['PASSWORD']
        session_obj__ = OdsLib.CSession(sUrl, sUsr, sPwd)

    return session_obj__

def SessionClose__():
    global session_obj__
    
    if not session_obj__ is None:
        session_obj__.Close()
        session_obj__ = None

def post_data(data_matrix):
    logging.info('create instances')

    return {}, 200

def put_data(data_matrix):
    logging.info('update instances')

    return NoContent, 200

def get_data(simple_query):
    logging.info('retrieve data')

    entityStr = simple_query['entity']
    conditions = simple_query['conditions'] if 'conditions' in simple_query else []
    attributes = simple_query['attributes'] if 'attributes' in simple_query else []
    orderBy = simple_query['orderBy'] if 'orderBy' in simple_query else []
    groupBy = simple_query['groupBy'] if 'groupBy' in simple_query else []
    maxCount = simple_query['maxCount'] if 'maxCount' in simple_query else 10000
    skipCount = simple_query['skipCount'] if 'skipCount' in simple_query else 0
    vectorSkipCount = simple_query['vectorSkipCount'] if 'vectorSkipCount' in simple_query else 0
    vectorMaxCount = simple_query['vectorMaxCount'] if 'vectorMaxCount' in simple_query else sys.maxsize

    so = Session__()
    model = so.Model()
    elem = model.GetElemEx(entityStr)
    result = so.GetInstancesExSimple(elem.aeName, conditions, attributes, orderBy, groupBy, maxCount)

    rv = {}
    rv['name'] = elem.aeName
    rv['baseName'] = elem.beName
    rv['skipCount'] = skipCount
    rv['vectorSkipCount'] = vectorSkipCount

    columnsObj = []

    for column in result.values:
        columnObj = {}
        columnValues = OdsLib.ColumnGetSeqEx(column)
        for rowIndex, row in enumerate(columnValues):
            if isinstance(row, list):
                # we should do this using value matrix but actually we are emulating it
                rowNumAvailable = len(row)
                if(rowNumAvailable > 0 and (vectorSkipCount > 0 or vectorMaxCount < rowNumAvailable)):
                    if(vectorSkipCount >= rowNumAvailable):
                        columnValues = []
                    else:
                        numtakeable = rowNumAvailable - vectorSkipCount
                        if(numtakeable > vectorMaxCount): 
                            numtakeable = vectorMaxCount
                        columnValues[rowIndex] = row[vectorSkipCount:(vectorSkipCount + numtakeable)]

        columnFlags = column.value.flag
        columnFlagLength = len(columnFlags)
        aName, aAggrType = OdsLib.ExtractAttributeNameFromColumnName(column.valName)
        columnObj['aggregate'] = OdsLib.GetAggrTypeStr(aAggrType)

        attr = model.GetAttribute(elem.aeName, aName)
        valuesObj = {}
        if not attr is None:
            valuesObj['dataType'] = OdsLib.GetDataTypeStr(attr.dType)
            columnObj['name'] = attr.aaName
            columnObj['baseName'] = attr.baName

            if(org.asam.ods.DT_UNKNOWN != attr.dType):
                valArray = []
                for valIndex, columnValue in enumerate(columnValues):
                    valueValid = True
                    if valIndex < columnFlagLength:
                        valueValid = OdsLib.ValidFlag(columnFlags[valIndex])
                    valArray.append(columnValue if(True == valueValid) else None)

                valuesObj[GetDiscriminatorArrayName__(attr.dType)] = valArray
            else:
                # column values
                unknownSeqArray = []
                for valIndex, columnValue in enumerate(columnValues):
                    valueValid = True
                    if valIndex < columnFlagLength:
                        valueValid = OdsLib.ValidFlag(columnFlags[valIndex])
                    TypedValueVectorObj = {}
                    TypedValueVectorObj['dataType'] = OdsLib.GetDataTypeStr(column.value.u._d)
                    TypedValueVectorObj[GetDiscriminatorArrayName__(column.value.u._d)] = columnValue
                    unknownSeqArray.append(TypedValueVectorObj if(True == valueValid) else None)
                
                valuesObj[GetDiscriminatorArrayName__(attr.dType)] = unknownSeqArray
        else:
            relAttr = model.GetRelation(elem.aeName, aName)
            valuesObj['dataType'] = OdsLib.GetDataTypeStr(org.asam.ods.DT_LONGLONG)
            columnObj['name'] = relAttr.arName
            columnObj['baseName'] = relAttr.brName

            valArray = []
            for valIndex, columnValue in enumerate(columnValues):
                valueValid = True
                if valIndex < columnFlagLength:
                    valueValid = OdsLib.ValidFlag(columnFlags[valIndex])
                if 0 == columnValue:
                    valueValid = False
                valArray.append(columnValue if(True == valueValid) else None)
            valuesObj[GetDiscriminatorArrayName__(org.asam.ods.DT_LONGLONG)] = valArray

        columnObj['values'] = valuesObj
        columnsObj.append(columnObj)
    
    rv['columns'] = columnsObj

    if request_wants_json():
        return jsonify(rv), 200
    
    return render_template('datamatrix.html', datamatrix=rv),  200
 
def post_dataGP(simple_query):
    return get_data(simple_query)

def put_transaction():
    logging.info('commit transaction')
    
    return NoContent, 200

def delete_transaction():
    logging.info('abort transaction')
    
    return NoContent, 200

def put_schema(schema):
    logging.info('create or overwrite entity/attribute/enum in schema')
    for entity in schema['entities']:
        logging.info('create ' + entity['name'])
        for attribute in entity['attributes']:
            logging.info('  create attribute ' + attribute['name'])
        for relation in entity['relations']:
            logging.info('  create relation ' + relation['name'])

    return NoContent, 200

def delete_schema(schema):
    logging.info('delete entity/attribute/enum in schema')
    for entity in schema['entities']:
        logging.info('delete ' + entity['name'])

    return NoContent, 200

def get_schema():
    logging.info('get the server schema')
    rv = {}
    model = Session__().Model()
    # add enumerations
    enumsArray = []
    for enum in model.enums_:
        enumObj = {}
        enumObj['name'] = enum.enumName
        enumItems = []
        for enumItem in enum.items:
            enumItemObj = {}
            enumItemObj['name'] = enumItem.itemName
            enumItemObj['index'] = enumItem.index
            enumItems.append(enumItemObj)
        enumObj['entries'] = enumItems
        enumsArray.append(enumObj)
    rv['enumerations'] = enumsArray
    # add entities
    entities = []
    for elem in model.model_.applElems:
        entityObj = {}
        entityObj['name'] = elem.aeName
        entityObj['baseName'] = elem.beName
        entityObj['objecttype'] = OdsLib.LL2Int(elem.aid)
        # add attributes
        attributes = []
        for attr in elem.attributes:
            attrObj = {}
            attrObj['name'] = attr.aaName
            attrObj['baseName'] = attr.baName
            attrObj['dataType'] = OdsLib.GetDataTypeStr(attr.dType)
            attrObj['length'] = attr.length
            attrObj['obligatory'] = attr.isObligatory
            attrObj['unique'] = attr.isUnique
            attrObj['unitId'] = OdsLib.LL2Int(attr.unitId)
            if(org.asam.ods.DT_ENUM == attr.dType or org.asam.ods.DS_ENUM == attr.dType):
                attrObj['enumeration'] = model.GetEnumName(elem.aid, attr.aaName)
            attributes.append(attrObj)
        entityObj['attributes'] = attributes
        # add relations
        relations = []
        for applRel in model.model_.applRels:
            if OdsLib.LL_Equal(applRel.elem1, elem.aid):
                relType = "n-m" 
                if (1 == applRel.arRelationRange.max and -1 == applRel.invRelationRange.max):
                    relType = "1-n" 
                elif (-1 == applRel.arRelationRange.max and 1 == applRel.invRelationRange.max):
                    relType = "n-1" 
                relEntity = model.GetElemByAid(applRel.elem2)
                relObj = {}
                relObj["name"] = applRel.arName
                relObj["baseName"] = applRel.brName
                relObj["inverseName"] = applRel.invName
                relObj["inverseBaseName"] = applRel.invBrName
                relObj["obligatory"] = (True if (0 != applRel.arRelationRange.min and -1 != applRel.arRelationRange.max) else False)
                relObj["type"] = relType
                relObj["kind"] = OdsLib.GetRelationType(applRel.arRelationType)
                relObj["relEntityName"] = relEntity.aeName
                relObj["relEntityBaseName"] = relEntity.beName
                relations.append(relObj)
        entityObj['relations'] = relations
        entities.append(entityObj)
    rv['entities'] = entities
    return rv

def get_context():
    logging.info('get context variables')
    rv = []
    for param in context_vars__:
        if 'PASSWORD' != param:
            pObj = {}
            pObj['name'] = param
            pObj['value'] = context_vars__[param]
            rv.append(pObj)
    return rv

def put_context(parameters):
    logging.info('set context variables')
    # make sure we can use different context
    SessionClose__()
    
    for param in parameters:
        pName = param['name']
        pValue = param['value']
        context_vars__[pName] = pValue

    return NoContent, 200

def get_utils_asampath_create(params):
    logging.info('create an asam path')
    
    entityStr = params['entity']
    iid = params['id']

    so = Session__()
    model = so.Model()
    elem = model.GetElemEx(entityStr)
    rv = {}
    rv['path'] = so.AsamPathCreate(elem.aid,  iid)
    return rv

def post_utils_asampath_create(params):
    return get_utils_asampath_create(params)

def get_utils_asampath_resolve(params):
    logging.info('resolve an asam path')
    
    path = params['path']
 
    so = Session__()
    entity,  iid = so.AsamPathResolve(path)
    rv = {}
    rv['entity'] = entity
    rv['id'] = iid
    return rv

def post_utils_asampath_resolve(params):
    return get_utils_asampath_resolve(params)

@app.route('/')
def index():
    return redirect('ui/')

logging.basicConfig(level=logging.INFO)

app.add_api('swagger.yaml')
# set the WSGI application callable to allow using uWSGI:
# uwsgi --http :8081 -w app
# Make the WSGI interface available at the top level so wfastcgi can get it.
wsgi_app = app.app.wsgi_app
application = app.app

if __name__ == '__main__':
    application.run('localhost', 8081)
