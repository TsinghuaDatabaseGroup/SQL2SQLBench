from dialects.MySQLDialect import MySQLDialect
from dialects.OracleDialect import OracleDialect
from dialects.PGDialect import PGDialect
from dialects.SnowflakeDialect import SnowflakeDialect
from dialects.SQLiteDialect import SQLiteDialect
from dialects.SQLServerDialect import SQLServerDialect

Dialects = {
    'mysql': MySQLDialect(),
    'pg': PGDialect(),
    'oracle': OracleDialect(),
    'snowflake': SnowflakeDialect(),
    'sqlserver': SQLServerDialect(),
    'sqlite': SQLiteDialect(),
}

def get_all_dialect_instances():
    return Dialects


def sql_execute(dialect: str, db_name: str, sql: str, db_parameter: dict | None = None, emp_flag=False,
                restart_flag=False):
    if dialect not in Dialects:
        raise ValueError(f"{dialect} is not supported")
    return Dialects[dialect].execute(db_name, sql, db_parameter, emp_flag, restart_flag)


def sql_dependent_execute(dialect: str, dbname: str, sql: str, db_param: dict | None = None):
    if dialect not in Dialects:
        raise ValueError(f"{dialect} is not supported")
    return Dialects[dialect].dependent_execute(dbname, sql, db_param)


def get_type(dialect: str, db_name: str, obj: str, is_table: bool, db_param: dict | None = None):
    if dialect not in Dialects:
        raise ValueError(f"{dialect} is not supported")
    return Dialects[dialect].get_data_type(db_name, obj, is_table, db_param)


def drop_db(dialect: str, db_name: str):
    if dialect not in Dialects:
        raise ValueError(f"{dialect} is not supported")
    return Dialects[dialect].drop_db(db_name)
