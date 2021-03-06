#!/usr/bin/env python
"""
Access ASAM Ods python using omniorb and wrap it using swagger.

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
import odslib
import connexion
from flask import render_template, redirect, jsonify, url_for, request, make_response, session
from flask.sessions import SessionInterface
from connexion import NoContent
from beaker.middleware import SessionMiddleware

import org
import ods_protobuf_convert
import jaquel_to_ods_convert
import con_utils

app = connexion.App(__name__)

_active_aosession = {}

session_opts = {
    'session.type': 'file',
    'session.cookie_expires': False, # can be set to secconds instead
    'session.data_dir': './data',
    'session.auto': True,
    'session.secret': 'VerySecretAndRandomString!PotentiallyAutomaticGenerated'
}


class BeakerSessionInterface(SessionInterface):
    def open_session(self, app, request):
        session = request.environ['beaker.session']
        return session

    def save_session(self, app, session, response):
        session.save()


def _Session(config, conI):
    global _active_aosession

    if not _active_aosession.has_key(conI):
        params = con_utils.get_params(config, conI)
        _active_aosession[conI] = odslib.CSessionAutoReconnect(params)

    return _active_aosession[conI]


def _SessionClose(conI):
    global _active_aosession

    if _active_aosession.has_key(conI):
        del _active_aosession[conI]


def _request_wants_protobuf():
    best = request.accept_mimetypes.best_match([ods_protobuf_convert.content_type_binary(), ods_protobuf_convert.content_type_json(), 'application/json', 'text/html'])
    return best == ods_protobuf_convert.content_type_binary() or best == ods_protobuf_convert.content_type_json(), best == ods_protobuf_convert.content_type_json()


def _request_wants_json():
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


def data_post(conI, data_matrix):
    logging.info('create instances')
    return jsonify({}), 200


def data_modify_post(conI, data_matrix):
    return data_post(conI, data_matrix)


def data_put(conI, data_matrix):
    logging.info('update instances')
    return NoContent, 200


def data_modify_put(conI, data_matrix):
    return data_put(conI, data_matrix)


def data_delete(conI, data_matrix):
    logging.info('delete instances')

    return NoContent, 200


def data_delete_post(conI, data_matrix):
    return data_delete(conI, data_matrix)


def data_access_post(conI,  query_struct):
    logging.info('retrieve data')

    if 'entity' in query_struct:
        # assume element list
        entityStr = query_struct['entity']
        conditions = query_struct['conditions'] if 'conditions' in query_struct else []
        attributes = query_struct['attributes'] if 'attributes' in query_struct else []
        orderBy = query_struct['orderBy'] if 'orderBy' in query_struct else []
        groupBy = query_struct['groupBy'] if 'groupBy' in query_struct else []
        rowMaxCount = query_struct['rowMaxCount'] if 'rowMaxCount' in query_struct else 10000
        rowSkipCount = query_struct['rowSkipCount'] if 'rowSkipCount' in query_struct else 0
        seqSkipCount = query_struct['seqSkipCount'] if 'seqSkipCount' in query_struct else 0
        seqMaxCount = query_struct['seqMaxCount'] if 'seqMaxCount' in query_struct else 50

        so = _Session(session, conI)
        model = so.Model()
        elem = model.GetElemEx(entityStr)
        result = so.GetElementValues(elem.aeName, conditions, attributes, orderBy, groupBy, rowMaxCount)
    else:
        # assume jaquel
        so = _Session(session, conI)
        model = so.Model()

        elem, qse, options = jaquel_to_ods_convert.JaquelToQueryStructureExt(model, query_struct)
        result = so.GetInstancesEx(qse, options['rowlimit'])
        rowMaxCount  = options['rowlimit']
        rowSkipCount = options['rowskip']
        seqMaxCount  = options['seqlimit']
        seqSkipCount = options['seqskip']

    wantsProto, wantsProtoJson = _request_wants_protobuf()
    if wantsProto:
        response = make_response(ods_protobuf_convert.o2p_datamatrices(model, elem, result, rowSkipCount, seqSkipCount, seqMaxCount, wantsProtoJson))
        response.headers['content-type'] = ods_protobuf_convert.content_type_binary() if not wantsProtoJson else ods_protobuf_convert.content_type_json()
        return response, 200

    rv = {}
    rv['matrices'] = []

    for table in result:

        tableElem = model.GetElemByAid(table.aid)

        tableObj = {}
        tableObj['name'] = tableElem.aeName
        tableObj['baseName'] = tableElem.beName
        tableObj['rowSkipCount'] = rowSkipCount
        tableObj['seqSkipCount'] = seqSkipCount

        columnsObj = []

        for column in table.values:
            columnObj = {}
            columnValues = odslib.ColumnGetSeq(column)
            for rowIndex, row in enumerate(columnValues):
                if isinstance(row, list):
                    # we should do this using value matrix but actually we are emulating it
                    rowNumAvailable = len(row)
                    if(rowNumAvailable > 0 and (seqSkipCount > 0 or seqMaxCount < rowNumAvailable)):
                        if(seqSkipCount >= rowNumAvailable):
                            columnValues = []
                        else:
                            numtakeable = rowNumAvailable - seqSkipCount
                            if(numtakeable > seqMaxCount):
                                numtakeable = seqMaxCount
                            columnValues[rowIndex] = row[seqSkipCount:(seqSkipCount + numtakeable)]

            columnFlags = column.value.flag
            columnFlagLength = len(columnFlags)
            aName, aAggrType = odslib.ExtractAttributeNameFromColumnName(column.valName)
            columnObj['aggregate'] = odslib.GetAggrTypeStr(aAggrType)

            attr = model.GetAttribute(tableElem.aeName, aName)
            valuesObj = {}
            if not attr is None:
                valuesObj['dataType'] = odslib.GetDataTypeStr(attr.dType)
                columnObj['name'] = attr.aaName
                columnObj['baseName'] = attr.baName

                if(org.asam.ods.DT_UNKNOWN != attr.dType):
                    valArray = []
                    for valIndex, columnValue in enumerate(columnValues):
                        valueValid = True
                        if valIndex < columnFlagLength:
                            valueValid = odslib.ValidFlag(columnFlags[valIndex])
                        valArray.append(columnValue if(True == valueValid) else (None if not odslib.IsSequence(attr.dType) else []))

                    valuesObj[_GetDiscriminatorArrayName(attr.dType)] = valArray
                else:
                    # column values
                    unknownSeqArray = []
                    for valIndex, columnValue in enumerate(columnValues):
                        valueValid = True
                        if valIndex < columnFlagLength:
                            valueValid = odslib.ValidFlag(columnFlags[valIndex])
                        TypedValueVectorObj = {}
                        TypedValueVectorObj['dataType'] = odslib.GetDataTypeStr(column.value.u._d)
                        TypedValueVectorObj[_GetDiscriminatorArrayName(column.value.u._d)] = columnValue
                        unknownSeqArray.append(TypedValueVectorObj if(True == valueValid) else None)

                    valuesObj[_GetDiscriminatorArrayName(attr.dType)] = unknownSeqArray
            else:
                relAttr = model.GetRelation(tableElem.aeName, aName)
                valuesObj['dataType'] = odslib.GetDataTypeStr(org.asam.ods.DT_LONGLONG)
                columnObj['name'] = relAttr.arName
                columnObj['baseName'] = relAttr.brName

                valArray = []
                for valIndex, columnValue in enumerate(columnValues):
                    valueValid = True
                    if valIndex < columnFlagLength:
                        valueValid = odslib.ValidFlag(columnFlags[valIndex])
                    if 0 == columnValue:
                        valueValid = False
                    valArray.append(columnValue if(True == valueValid) else None)
                valuesObj[_GetDiscriminatorArrayName(org.asam.ods.DT_LONGLONG)] = valArray

            columnObj['values'] = valuesObj
            columnsObj.append(columnObj)

        tableObj['columns'] = columnsObj
        rv['matrices'].append(tableObj)

    if _request_wants_json():
        return jsonify(rv), 200

    return render_template('datamatrix.html', datamatrices=rv),  200


def data_get(conI, query_struct):
    return data_access_post(conI, query_struct)


def data_iteratorguid_get(conI,  iteratorGuid):
    logging.info('get additional results for ' + iteratorGuid)
    return jsonify({}), 200


def transaction_post(conI):
    logging.info('start transaction')
    return NoContent, 200


def transaction_put(conI):
    logging.info('commit transaction')
    return NoContent, 200


def transaction_delete(conI):
    logging.info('abort transaction')
    return NoContent, 200


def model_modify_put(conI, model):
    logging.info('create or overwrite entity/attribute/enum in model')
    for entity in model['entities']:
        logging.info('create ' + entity['name'])
        for attribute in entity['attributes']:
            logging.info('  create attribute ' + attribute['name'])
        for relation in entity['relations']:
            logging.info('  create relation ' + relation['name'])

    return NoContent, 200


def model_delete_post(conI, model):
    logging.info('delete entity/attribute/enum in model')
    for entity in model['entities']:
        logging.info('delete ' + entity['name'])

    return NoContent, 200


def model_access_get(conI):
    logging.info('get the server model')
    rv = {}
    model = _Session(session, conI).Model()
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
        entityObj['objecttype'] = odslib.LL2Int(elem.aid)
        # add attributes
        attributes = []
        for attr in elem.attributes:
            attrObj = {}
            attrObj['name'] = attr.aaName
            attrObj['baseName'] = attr.baName
            attrObj['dataType'] = odslib.GetDataTypeStr(attr.dType)
            attrObj['length'] = attr.length
            attrObj['obligatory'] = attr.isObligatory
            attrObj['unique'] = attr.isUnique
            attrObj['unitId'] = odslib.LL2Int(attr.unitId)
            if(org.asam.ods.DT_ENUM == attr.dType or org.asam.ods.DS_ENUM == attr.dType):
                attrObj['enumeration'] = model.GetEnumName(elem.aid, attr.aaName)
            attributes.append(attrObj)
        entityObj['attributes'] = attributes
        # add relations
        relations = []
        for applRel in model.model_.applRels:
            if odslib.LL_Equal(applRel.elem1, elem.aid):
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
                relObj["kind"] = odslib.GetRelationType(applRel.arRelationType)
                relObj["relEntityName"] = relEntity.aeName
                relObj["relEntityBaseName"] = relEntity.beName
                relations.append(relObj)
        entityObj['relations'] = relations
        entities.append(entityObj)
    rv['entities'] = entities
    return rv


def context_get(conI,  pattern):
    logging.info('get context variables')
    so = _Session(session, conI)
    nvi = so.GetContext(pattern)
    rv = []
    nviCount = nvi.getCount()
    nvs = nvi.nextN(nviCount)
    for nv in nvs:
        pObj = {}
        pObj['name'] = nv.valName
        pObj['value'] = str(odslib.GetTsValue(nv.value))
        rv.append(pObj)

    return rv, 200


def context_put(conI, parameters):
    logging.info('set context variables')
    so = _Session(session, conI)
    for param in parameters:
        varName = param['name']
        varValue = param['value']
        so.setContextString(varName,  varValue)
    return NoContent, 200


def con_get():
    logging.info('get info from existing Con entries')
    cons = con_utils.list(session)
    rv = {}
    rv['cons'] = []
    for conI in cons:
        conObj = {}
        conObj['name'] = conI
        rv['cons'].append(conObj)
    return jsonify(rv), 200;


def con_put(cons):
    logging.info('get info from existing Con entries')
    for conI in cons:
        if con_utils.exists(session, conI):
            con_utils.update(session, conI, cons[conI])
        else:
            con_utils.add(session, conI, cons[conI])
    return NoContent, 200

def con_coni_get(conI):
    logging.info('get con parameters')
    rv = []
    params = con_utils.get_params(session, conI)
    for param in params:
        if 'PASSWORD' != param:
            pObj = {}
            pObj['name'] = param
            pObj['value'] = params[param]
            rv.append(pObj)
    return rv


def con_coni_post(conI, parameters):
    logging.info('Create a new con')
    if con_utils.exists(session, conI):
        # already exist
        return NoContent, 405

    params = {}
    for param in parameters:
        pName = param['name']
        pValue = param['value']
        params[pName] = pValue

    con_utils.add(session, conI, params)

    return NoContent, 200


def con_coni_delete(conI):
    logging.info('delete con and close session')
    con_utils.delete(session, conI)
    _SessionClose(conI)
    return NoContent, 200


def con_coni_put(conI, parameters):
    logging.info('set con parameters')
    params = {}
    for param in parameters:
        pName = param['name']
        pValue = param['value']
        params[pName] = pValue

    # make sure we can change configuration of session
    _SessionClose(conI)
    con_utils.update(session, conI, params)

    return NoContent, 200


def utils_asampath_create_get(conI, params):
    logging.info('create an asam path')

    entityStr = params['entity']
    iid = params['id']

    so = _Session(session, conI)
    model = so.Model()
    elem = model.GetElemEx(entityStr)
    rv = {}
    rv['path'] = so.AsamPathCreate(elem.aid,  iid)
    return rv


def utils_asampath_create_post(conI, params):
    return utils_asampath_create_get(conI, params)


def utils_asampath_resolve_get(conI, params):
    logging.info('resolve an asam path')

    path = params['path']

    so = _Session(session, conI)
    entity,  iid = so.AsamPathResolve(path)
    rv = {}
    rv['entity'] = entity
    rv['id'] = iid
    return rv


def utils_asampath_resolve_post(conI, params):
    return utils_asampath_resolve_get(conI, params)


def utils_binary_access_post(conI,  binary_identifier):
    logging.info('read binary chunk')
    return jsonify({}),  200


def utils_binary_download_post(conI,  binary_identifier):
    logging.info('download file')

    response = make_response("abc")
    response.headers['content-type'] = 'application/octet-stream'
    return response


def utils_binary_getuploadurl_post(conI,  binary_identifier):
    logging.info('determnine upload url')

    return u"http://kjdfslakjdlkdjaslfj", 200


def utils_basemodel_get(conI):
    logging.info('retrieve basemodel')
    return app.app.send_static_file('basemodel_asamxx.xml')


@app.route('/')
def index():
    return redirect('ui/')


@app.route('/testdataget/')
def testdataget():
    return app.app.send_static_file('testdataget.html')


logging.basicConfig(level=logging.INFO)
app.add_api('swagger.yaml')
application = app.app
application.wsgi_app = SessionMiddleware(application.wsgi_app, session_opts)
application.session_interface = BeakerSessionInterface()
# set the WSGI application callable to allow using uWSGI:
# uwsgi --http :8081 -w app
# Make the WSGI interface available at the top level so wfastcgi can get it.
wsgi_app = application.wsgi_app

if __name__ == '__main__':
    application.run('localhost', 8081)
