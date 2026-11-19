# -*- coding: utf-8 -*-
# @Project: SQL2SQL_Bench
# @Module: type_conversion$

# @Time: 2025/4/1 22:36
from sql_gen.generator.ele_type.type_def import *


# Translate execution type of each dialect into our intermediate Type representation

def type_mapping(dialect: str, op_type: str) -> BaseType:
    # return BaseType(type, dialect)
    # TODO: change the json file can also work
    t = (op_type or '').strip().lower()
    base = t.split('(')[0].strip()
    if dialect == 'mysql':
        if op_type in ['DECIMAL', 'NEWDECIMAL']:
            assert op_type == 'NEWDECIMAL'
            return FloatGeneralType()
        if op_type == 'DOUBLE':
            return DoubleType()
        elif op_type in ['SHORT', 'LONG', 'LONGLONG', 'INT24']:
            return IntType()
        elif op_type == 'TINY':
            return BoolType()
        elif op_type == 'GEOMETRY':
            return PointType()
        elif op_type in ["DATE", "NEWDATE"]:
            return DateType()
        elif op_type == 'TIME':
            return TimeType()
        elif op_type == 'DATETIME':
            return DatetimeType()
        elif op_type == 'TIMESTAMP':
            return TimestampType()
        elif op_type == 'YEAR':
            return YearType()
        elif op_type in ['VARCHAR', 'VAR_STRING', 'STRING']:
            return VarcharType()
        elif op_type in ['BLOB', 'MEDIUM_BLOB', 'TINY_BLOB', 'LONG_BLOB']:
            return BlobType()
        elif op_type == 'JSON':
            return JsonType()
        elif op_type == 'NULL':
            return NullType()
        else:
            raise ValueError(f"MySQL Type {op_type} is not supported yet")
    elif dialect == 'pg':
        if op_type.startswith('_'):
            ele_type = type_mapping(dialect, op_type[1:])
            return ArrayType(ele_type)
        if op_type == 'uuid':
            return UuidType()
        elif op_type == 'bytea':
            return BlobType()
        elif op_type == 'jsonb':
            return JsonbType()
        elif op_type == 'varchar':
            return VarcharType()
        elif op_type == 'float8':
            return DoubleType()
        elif op_type == 'numeric' or op_type == 'float4':
            return FloatGeneralType()
        elif op_type == 'point':
            return PointType()
        elif op_type == 'bool':
            return BoolType()
        elif op_type == 'text':
            return TextType()
        elif op_type == 'char':
            return StringGeneralType()
        elif op_type in ["int8", "int2", "int4"]:
            return IntType()
        elif op_type == 'timestamp':
            return TimestampType()
        elif op_type == 'time':
            return TimeType()
        elif op_type == 'date':
            return DateType()
        elif op_type == 'json':
            return JsonType()
        elif op_type == 'xml':
            return XmlType()
        elif op_type == 'bpchar':
            return StringGeneralType()
        else:
            return NoneType()
            # raise ValueError(f"PG Type {op_type} is not supported yet")
    elif dialect == 'oracle':
        if op_type == 'NUMBER':
            return NumberType()
        if op_type == 'CHAR' or op_type == 'VARCHAR':
            return StringGeneralType()
        if op_type == 'DATE':
            return DateType()
        if op_type == 'TIMESTAMP':
            return TimestampType()
        if op_type == 'BINARY_DOUBLE':
            return DoubleType()
        if op_type == 'XMLTYPE':
            return XmlType()
        raise ValueError(f"Oracle Type {op_type} is not supported yet")
    elif dialect == 'sqlite':
        # SQLite query-time typeof() mainly returns: null, integer, real, text, blob.
        sqlite_base = base
        if sqlite_base in ['null', 'unknown', '']:
            return NullType()

        if sqlite_base in ['integer', 'int', 'tinyint', 'smallint', 'mediumint',
                           'bigint', 'int2', 'int8', 'unsigned big int', 'bool', 'boolean']:
            return IntType()

        if sqlite_base in ['real', 'double', 'double precision', 'float',
                           'numeric', 'decimal', 'number']:
            return NumberType()

        if sqlite_base in ['text', 'char', 'character', 'varchar', 'nvarchar',
                           'nchar', 'clob', 'string']:
            return StringGeneralType()

        if 'blob' in sqlite_base:
            return BlobType()

        # Keep temporal aliases after scalar families.
        if sqlite_base == 'date':
            return DateType()
        if sqlite_base == 'time':
            return TimeType()
        if sqlite_base in ['datetime', 'timestamp']:
            return TimestampType()

        if sqlite_base == 'json':
            return JsonType()

        raise ValueError(f"sqlite Type {op_type} is not supported yet")
    if dialect == 'snowflake':
        snowflake_base = (op_type or '').strip().split('(')[0].strip().upper()
        snowflake_code_map = {
            "0": NumberType,
            "1": DoubleType,
            "2": StringGeneralType,
            "3": DateType,
            "5": JsonType,
            "6": TimestampType,
            "7": TimestampType,
            "8": TimestampType,
            "9": JsonType,
            "10": ArrayType,
            "11": BlobType,
            "12": TimeType,
            "13": BoolType,
            "14": PointType,
            "15": PointType,
        }
        if snowflake_base in snowflake_code_map:
            if snowflake_base == "10":
                return ArrayType(None)
            return snowflake_code_map[snowflake_base]()

        if snowflake_base in ["NUMBER", "DECIMAL", "NUMERIC", "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT",
                              "BYTEINT", "DECFLOAT"]:
            return NumberType()
        if snowflake_base in ["FLOAT", "DOUBLE", "DOUBLE PRECISION", "REAL"]:
            return DoubleType()
        if snowflake_base in ["TEXT", "VARCHAR", "STRING", "CHAR", "CHARACTER"]:
            return StringGeneralType()
        if snowflake_base == "UUID":
            return UuidType()
        if snowflake_base == "DATE":
            return DateType()
        if snowflake_base in ["TIME"]:
            return TimeType()
        if snowflake_base in ["TIMESTAMP", "TIMESTAMP_NTZ"]:
            return TimestampType()
        if snowflake_base in ["TIMESTAMP_TZ", "TIMESTAMP_LTZ"]:
            return TimestampTZType()
        if snowflake_base in ["VARIANT", "OBJECT"]:
            return JsonType()
        if snowflake_base in ["ARRAY", "ARRAY<STRUCTURED>", "ARRAY(<STRUCTURED>)"]:
            return ArrayType(None)
        if snowflake_base == "BINARY":
            return BlobType()
        if snowflake_base == "BOOLEAN":
            return BoolType()
        if snowflake_base in ["GEOGRAPHY", "GEOMETRY"]:
            return PointType()
        if snowflake_base in ["NULL", ""]:
            return NullType()
        raise ValueError(f"snowflake Type {op_type} is not supported yet")
    elif dialect == 'sqlserver':
        if base in ['bit']:
            return BoolType()
        if base in ['tinyint', 'smallint', 'int', 'bigint']:
            return IntType()
        if base in ['decimal', 'numeric', 'money', 'smallmoney']:
            return NumberType()
        if base in ['real', 'float']:
            return DoubleType()
        if base in ['char', 'varchar', 'nchar', 'nvarchar', 'text', 'ntext']:
            return StringGeneralType()
        if base in ['binary', 'varbinary', 'image']:
            return BlobType()
        if base == 'uniqueidentifier':
            return UuidType()
        if base == 'xml':
            return XmlType()
        if base == 'date':
            return DateType()
        if base == 'time':
            return TimeType()
        if base in ['datetime', 'datetime2', 'smalldatetime']:
            return DatetimeType()
        if base == 'datetimeoffset':
            return TimestampTZType()
        if base == 'sql_variant':
            return NoneType()
        if base in ['', 'null']:
            return NullType()
        raise ValueError(f"SQLServer Type {op_type} is not supported yet")
    else:
        raise ValueError(f"dialect {dialect} is not supported")
