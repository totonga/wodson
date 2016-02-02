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

class CEnv:
    context_vars_ = {}
    session_obj_ = None

    def __init__(self, context_vars):
        self.context_vars_ = context_vars
    
_envs = {}

_envs['e1'] =  CEnv({u'URL':u'corbaname::10.89.2.24:900#ENGINE1.ASAM-ODS', u'USER':'System', u'PASSWORD':u'puma'})
_envs['e2'] =  CEnv({u'URL':u'corbaname::10.89.2.24:900#MeDaMak1.ASAM-ODS', u'USER':'test', u'PASSWORD':u'test'})
_envs['e3'] =  CEnv({u'URL':u'corbaname::130.164.139.4#AtfxNameMapTest.ASAM-ODS', u'USER':'', u'PASSWORD':u''})
_envs['e4'] =  CEnv({u'URL':u'corbaname::130.164.139.4#AtfxTest.ASAM-ODS', u'USER':'', u'PASSWORD':u''})

def _RequestWantsJson():
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json' and request.accept_mimetypes[best] > request.accept_mimetypes['text/html']

def _GetDiscriminatorArrayName(arrayType):
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


def _Session(envI):
    global session_obj__

    if _envs[envI].session_obj_ is None:
        sUrl = _envs[envI].context_vars_['URL']
        sUsr = _envs[envI].context_vars_['USER']
        sPwd = _envs[envI].context_vars_['PASSWORD']
        _envs[envI].session_obj_ = OdsLib.CSession(sUrl, sUsr, sPwd)

    return _envs[envI].session_obj_

def _SessionClose(envI):
    global session_obj__
    
    if not _envs[envI].session_obj_ is None:
        _envs[envI].session_obj_.Close()
        _envs[envI].session_obj_ = None

def data_post(envI, data_matrix):
    logging.info('create instances')

    return {}, 200

def data_modify_post(envI, data_matrix):
    return data_post(envI, data_matrix)

def data_put(envI, data_matrix):
    logging.info('update instances')

    return NoContent, 200

def data_modify_put(envI, data_matrix):
    return data_put(envI, data_matrix)

def data_delete(envI, data_matrix):
    logging.info('delete instances')

    return NoContent, 200

def data_modify_delete(envI, data_matrix):
    return data_delete(envI, data_matrix)

def data_get(envI,  query_struct):
    logging.info('retrieve data')

    entityStr = query_struct['entity']
    conditions = query_struct['conditions'] if 'conditions' in query_struct else []
    attributes = query_struct['attributes'] if 'attributes' in query_struct else []
    orderBy = query_struct['orderBy'] if 'orderBy' in query_struct else []
    groupBy = query_struct['groupBy'] if 'groupBy' in query_struct else []
    maxCount = query_struct['maxCount'] if 'maxCount' in query_struct else 10000
    skipCount = query_struct['skipCount'] if 'skipCount' in query_struct else 0
    vectorSkipCount = query_struct['vectorSkipCount'] if 'vectorSkipCount' in query_struct else 0
    vectorMaxCount = query_struct['vectorMaxCount'] if 'vectorMaxCount' in query_struct else sys.maxsize

    so = _Session(envI)
    model = so.Model()
    elem = model.GetElemEx(entityStr)
    result = so.GetInstancesEx_Ver2(elem.aeName, conditions, attributes, orderBy, groupBy, maxCount)
    
    rv = {}
    rv['tables']=[]

    for table in result:
        
        tableElem = model.GetElemByAid(table.aid)
    
        tableObj = {}
        tableObj['name'] = tableElem.aeName
        tableObj['baseName'] = tableElem.beName
        tableObj['skipCount'] = skipCount
        tableObj['vectorSkipCount'] = vectorSkipCount

        columnsObj = []

        for column in table.values:
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

            attr = model.GetAttribute(tableElem.aeName, aName)
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

                    valuesObj[_GetDiscriminatorArrayName(attr.dType)] = valArray
                else:
                    # column values
                    unknownSeqArray = []
                    for valIndex, columnValue in enumerate(columnValues):
                        valueValid = True
                        if valIndex < columnFlagLength:
                            valueValid = OdsLib.ValidFlag(columnFlags[valIndex])
                        TypedValueVectorObj = {}
                        TypedValueVectorObj['dataType'] = OdsLib.GetDataTypeStr(column.value.u._d)
                        TypedValueVectorObj[_GetDiscriminatorArrayName(column.value.u._d)] = columnValue
                        unknownSeqArray.append(TypedValueVectorObj if(True == valueValid) else None)
                    
                    valuesObj[_GetDiscriminatorArrayName(attr.dType)] = unknownSeqArray
            else:
                relAttr = model.GetRelation(tableElem.aeName, aName)
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
                valuesObj[_GetDiscriminatorArrayName(org.asam.ods.DT_LONGLONG)] = valArray

            columnObj['values'] = valuesObj
            columnsObj.append(columnObj)
        
        tableObj['columns'] = columnsObj
        rv['tables'].append(tableObj)

    if _RequestWantsJson():
        return jsonify(rv), 200
    
    return render_template('datamatrix.html', datamatrices=rv),  200
 
def data_access_post(envI, query_struct):
    return data_get(envI, query_struct)

def transaction_put(envI):
    logging.info('commit transaction')
    
    return NoContent, 200

def transaction_delete(envI):
    logging.info('abort transaction')
    
    return NoContent, 200

def model_put(envI, model):
    logging.info('create or overwrite entity/attribute/enum in model')
    for entity in model['entities']:
        logging.info('create ' + entity['name'])
        for attribute in entity['attributes']:
            logging.info('  create attribute ' + attribute['name'])
        for relation in entity['relations']:
            logging.info('  create relation ' + relation['name'])

    return NoContent, 200

def model_delete(envI, model):
    logging.info('delete entity/attribute/enum in model')
    for entity in model['entities']:
        logging.info('delete ' + entity['name'])

    return NoContent, 200

def model_get(envI):
    logging.info('get the server model')
    rv = {}
    model = _Session(envI).Model()
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

def context_get(envI):
    logging.info('get context variables')
    rv = []
    for param in _envs[envI].context_vars_:
        if 'PASSWORD' != param:
            pObj = {}
            pObj['name'] = param
            pObj['value'] = _envs[envI].context_vars_[param]
            rv.append(pObj)
    return rv

def context_put(envI, parameters):
    logging.info('set context variables')
    # make sure we can use different context
    _SessionClose(envI)
    
    for param in parameters:
        pName = param['name']
        pValue = param['value']
        _envs[envI].context_vars_[pName] = pValue

    return NoContent, 200

def utils_asampath_create_get(envI, params):
    logging.info('create an asam path')
    
    entityStr = params['entity']
    iid = params['id']

    so = _Session(envI)
    model = so.Model()
    elem = model.GetElemEx(entityStr)
    rv = {}
    rv['path'] = so.AsamPathCreate(elem.aid,  iid)
    return rv

def utils_asampath_create_post(envI, params):
    return utils_asampath_create_get(envI, params)

def utils_asampath_resolve_get(envI, params):
    logging.info('resolve an asam path')
    
    path = params['path']
 
    so = _Session(envI)
    entity,  iid = so.AsamPathResolve(path)
    rv = {}
    rv['entity'] = entity
    rv['id'] = iid
    return rv

def utils_asampath_resolve_post(envI, params):
    return utils_asampath_resolve_get(envI, params)

@app.route('/')
def index():
    return redirect('ui/')

@app.route('/testdataget/')
def testdataget():
    return app.app.send_static_file('testdataget.html')


logging.basicConfig(level=logging.INFO)

app.add_api('swagger.yaml')
# set the WSGI application callable to allow using uWSGI:
# uwsgi --http :8081 -w app
# Make the WSGI interface available at the top level so wfastcgi can get it.
wsgi_app = app.app.wsgi_app
application = app.app

if __name__ == '__main__':
    application.run('localhost', 8081)
