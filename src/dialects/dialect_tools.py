from utils.db_connector import get_all_dialect_instances

dialects = get_all_dialect_instances()


def get_table_col_name(name: str, dialect: str):
    if dialect not in dialects:
        raise Exception(f"Unknown dialect {dialect}")
    return dialects[dialect].get_table_col_name(name)


def get_all_dialects():
    return [dialects[dialect].name for dialect in dialects]


def get_reserved_keyword_list(dialect: str):
    return dialects[dialect].reserved_keywords


def is_any_reserved_keyword(col):
    for dialect, dialect_instance in dialects.items():
        if col.upper() in dialect_instance.reserved_keywords:
            return True
    return False
