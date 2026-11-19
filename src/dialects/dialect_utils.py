import re
from decimal import Decimal

from utils.tools import get_db_ids, get_all_db_name, get_tran_db_name, get_empty_db_name

database_mapping = {
    "customer_order": "cus_order",
    "test": "test"
}


_CONTINUATION_KEYWORDS = (
    r"UNION(?:\s+ALL)?",
    r"INTERSECT",
    r"EXCEPT",
    r"(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN",
    r"ON",
    r"WHERE",
    r"GROUP\s+BY",
    r"ORDER\s+BY",
    r"HAVING",
    r"LIMIT",
    r"OFFSET",
    r"FETCH",
)


def normalize_executable_sql(sql: str) -> str:
    return sql.strip().strip(';')

def convert_decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, list):
        return [convert_decimal_to_float(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_decimal_to_float(item) for item in obj)
    elif isinstance(obj, dict):
        return {key: convert_decimal_to_float(value) for key, value in obj.items()}
    else:
        return obj


def get_db_name(dialect, db_name):
    db_ids = get_db_ids() + [get_all_db_name(dialect), get_tran_db_name(get_all_db_name(dialect))]
    if db_name not in database_mapping:
        for db_id in db_ids:
            if db_id == db_name:
                return db_name
            elif db_name == get_empty_db_name(db_id):
                return db_name
        return db_name
    else:
        return database_mapping[db_name]


def build_attributes(col_type, attributes, dialect):
    res = []
    if attributes is None:
        return res
    for attribute in attributes:
        if attribute is None:
            continue
        elif isinstance(attribute, str):
            # different in null handling
            if dialect == 'sqlserver' and attribute == 'UNIQUE':
                continue
            res.append(str(attribute))
        else:
            assert isinstance(attribute, dict)
            attr_type = attribute['type']
            if attr_type == 'default':
                from sql_gen.generator.ele_type.type_operation import build_value
                res.append(f"DEFAULT {build_value(col_type, attribute['value'], dialect)}")
    return res
