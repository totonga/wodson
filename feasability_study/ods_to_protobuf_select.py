import ods_protobuf_convert
import odslib
import json
import wodson_pb2
import org
from google.protobuf import json_format
from google.protobuf import timestamp_pb2

_op_aggregates = { org.asam.ods.NONE: wodson_pb2.DataMatrix.Column.NONE , org.asam.ods.COUNT: wodson_pb2.DataMatrix.Column.COUNT , org.asam.ods.DCOUNT: wodson_pb2.DataMatrix.Column.DCOUNT , org.asam.ods.MIN: wodson_pb2.DataMatrix.Column.MIN , org.asam.ods.MAX: wodson_pb2.DataMatrix.Column.MAX , org.asam.ods.AVG: wodson_pb2.DataMatrix.Column.AVG , org.asam.ods.SUM: wodson_pb2.DataMatrix.Column.SUM , org.asam.ods.DISTINCT: wodson_pb2.DataMatrix.Column.DISTINCT , org.asam.ods.POINT: wodson_pb2.DataMatrix.Column.POINT}
_op_seloperator = { org.asam.ods.AND: wodson_pb2.SelectStruct.ConditionArrayItem.AND , org.asam.ods.OR: wodson_pb2.SelectStruct.ConditionArrayItem.OR , org.asam.ods.NOT: wodson_pb2.SelectStruct.ConditionArrayItem.NOT , org.asam.ods.OPEN: wodson_pb2.SelectStruct.ConditionArrayItem.OPEN , org.asam.ods.CLOSE: wodson_pb2.SelectStruct.ConditionArrayItem.CLOSE}

_op_selopcode = {   org.asam.ods.EQ                  :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.EQ            ,
                    org.asam.ods.NEQ                 :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.NEQ           ,
                    org.asam.ods.LT                  :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.LT            ,
                    org.asam.ods.GT                  :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.GT            ,
                    org.asam.ods.LTE                 :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.LTE           ,
                    org.asam.ods.GTE                 :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.GTE           ,
                    org.asam.ods.INSET               :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.INSET         ,
                    org.asam.ods.NOTINSET            :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.NOTINSET      ,
                    org.asam.ods.LIKE                :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.LIKE          ,
                    org.asam.ods.CI_EQ               :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.CI_EQ         ,
                    org.asam.ods.CI_NEQ              :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.CI_NEQ        ,
                    org.asam.ods.CI_LT               :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.CI_LT         ,
                    org.asam.ods.CI_GT               :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.CI_GT         ,
                    org.asam.ods.CI_LTE              :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.CI_LTE        ,
                    org.asam.ods.CI_GTE              :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.CI_GTE        ,
                    org.asam.ods.CI_INSET            :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.CI_INSET      ,
                    org.asam.ods.CI_NOTINSET         :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.CI_NOTINSET   ,
                    org.asam.ods.CI_LIKE             :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.CI_LIKE       ,
                    org.asam.ods.IS_NULL             :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.IS_NULL       ,
                    org.asam.ods.IS_NOT_NULL         :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.IS_NOT_NULL   ,
                    org.asam.ods.NOTLIKE             :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.NOTLIKE       ,
                    org.asam.ods.CI_NOTLIKE          :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.CI_NOTLIKE    ,
                    org.asam.ods.BETWEEN             :  wodson_pb2.SelectStruct.ConditionArrayItem.Condition.BETWEEN }

def _aidToWrite(aid, default):
    rv = odslib.LL2Int(aid)
    return rv if default != rv else 0

def _AssignConditionValues(u, target):
    columnType = u._d
    if columnType == org.asam.ods.DT_BYTE:
        target.value_byte.values.join(u._v)
    elif columnType == org.asam.ods.DT_BOOLEAN:
        target.value_boolean.values.append(u._v)
    elif columnType == org.asam.ods.DT_SHORT:
        target.value_long.values.append(u._v)
    elif columnType == org.asam.ods.DT_LONG:
        target.value_long.values.append(u._v)
    elif columnType == org.asam.ods.DT_LONGLONG:
        target.value_longlong.values.append(odslib.LL2Int(u._v))
    elif columnType == org.asam.ods.DT_FLOAT:
        target.value_double.values.append(u._v)
    elif columnType == org.asam.ods.DT_DOUBLE:
        target.value_double.values.append(u._v)
    elif columnType == org.asam.ods.DT_DATE:
        target.value_date.values.extend([ods_protobuf_convert.o2p_date(u._v)])
    elif columnType == org.asam.ods.DT_STRING:
        target.value_string.values.append(u._v.decode('utf-8'))
    elif columnType == org.asam.ods.DT_ENUM:
        target.value_long.values.append(u._v)
    elif columnType == org.asam.ods.DT_COMPLEX:
        target.value_double.values.append(u._v.r)
        target.value_double.values.append(u._v.i)
    elif columnType == org.asam.ods.DT_DCOMPLEX:
        target.value_double.values.append(u._v.r)
        target.value_double.values.append(u._v.i)
    elif columnType == org.asam.ods.DT_EXTERNALREFERENCE:
        target.value_string.values.append(u._v.description.decode('utf-8'))
        target.value_string.values.append(u._v.mimeType.decode('utf-8'))
        target.value_string.values.append(u._v.location.decode('utf-8'))
    elif columnType == org.asam.ods.DS_BYTE:
        for columnValue in columnValues:
            target.value_byte.values.join(columnValue)
    elif columnType == org.asam.ods.DS_BOOLEAN:
        for columnValue in u._v:
            target.value_boolean.values.append(columnValue)
    elif columnType == org.asam.ods.DS_SHORT:
        for columnValue in u._v:
            target.value_long.values.append(columnValue)
    elif columnType == org.asam.ods.DS_LONG:
        for columnValue in u._v:
            target.value_long.values.append(columnValue)
    elif columnType == org.asam.ods.DS_LONGLONG:
        for columnValue in u._v:
            target.value_longlong.values.append(odslib.LL2Int(columnValue))
    elif columnType == org.asam.ods.DS_FLOAT:
        for columnValue in u._v:
            target.value_double.values.append(columnValue)
    elif columnType == org.asam.ods.DS_DOUBLE:
        for columnValue in u._v:
            target.value_double.values.append(columnValue)
    elif columnType == org.asam.ods.DS_DATE:
        target.value_date.values.extend(ods_protobuf_convert.o2p_dateseq(u._v))
    elif columnType == org.asam.ods.DS_STRING:
        for columnValue in u._v:
            target.value_string.values.append(columnValue.decode('utf-8'))
    elif columnType == org.asam.ods.DS_ENUM:
        for columnValue in u._v:
            target.value_long.values.append(columnValue)
    elif columnType == org.asam.ods.DS_COMPLEX:
        for columnValue in u._v:
            target.value_double.values.append(columnValue.r)
            target.value_double.values.append(columnValue.i)
    elif columnType == org.asam.ods.DS_DCOMPLEX:
        for columnValue in u._v:
            target.value_double.values.append(columnValue.r)
            target.value_double.values.append(columnValue.i)
    elif columnType == org.asam.ods.DS_EXTERNALREFERENCE:
        for columnValue in u._v:
            target.value_string.values.append(columnValue.description.decode('utf-8'))
            target.value_string.values.append(columnValue.mimeType.decode('utf-8'))
            target.value_string.values.append(columnValue.location.decode('utf-8'))


def ods_to_protobuf_select_json(model, qse, options):

    default_objecttype = odslib.LL2Int(qse.anuSeq[0].attr.aid)

    rv = wodson_pb2.SelectStruct()
    rv.default_objecttype = default_objecttype
    for anu in qse.anuSeq:
        targetAnu = rv.attributes.add()
        targetAnu.objecttype = _aidToWrite(anu.attr.aid, default_objecttype)
        targetAnu.atribute = anu.attr.aaName
        targetAnu.aggregate = _op_aggregates[anu.aggregate]
        targetAnu.unit = odslib.LL2Int(anu.unitId)

    for cond in qse.condSeq:
        if org.asam.ods.SEL_VALUE_TYPE == cond._d:
            targetCond = rv.where.add().condition
            targetCond.objecttype = _aidToWrite(cond._v.attr.attr.aid, default_objecttype)
            targetCond.atribute = cond._v.attr.attr.aaName
            targetCond.unit = odslib.LL2Int(cond._v.attr.unitId)
            targetCond.operator = _op_selopcode[cond._v.oper]
            _AssignConditionValues(cond._v.value.u, targetCond)

        elif org.asam.ods.SEL_OPERATOR_TYPE == cond._d:
            rv.where.add().conjunction = _op_seloperator[cond._v]

    for orderBy in qse.orderBy:
        targetOrderby = rv.orderby.add()
        targetOrderby.objecttype = _aidToWrite(orderBy.attr.aid, default_objecttype)
        targetOrderby.atribute = orderBy.attr.aaName 
        targetOrderby.order = wodson_pb2.SelectStruct.OrderbyItem.ASCENDING if orderBy.ascending else wodson_pb2.SelectStruct.OrderbyItem.DESCENDING

    for groupBy in qse.groupBy:
        targetOrderby = rv.groupby.add()
        targetOrderby.objecttype = _aidToWrite(groupBy.aid, default_objecttype)
        targetOrderby.atribute = groupBy.aaName 

    return json_format.MessageToJson(rv)