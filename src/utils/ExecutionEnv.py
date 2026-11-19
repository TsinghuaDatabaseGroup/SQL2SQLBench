# -*- coding: utf-8 -*-
# @Project: SQL2SQL_Bench
# @Module: ExecutionEnv$

# @Time: 2025/6/15 12:29
from utils.db_connector import sql_execute, get_type


class ExecutionEnv:
    def __init__(self, dialect: str, db_name: str):
        self.dialect = dialect
        self.db_name = db_name
        self.db_param = {}

    def add_param(self, dialect: str, param_values: dict):
        if dialect != self.dialect:
            return True
        for db_param, param_value in param_values.items():
            if db_param in self.db_param:
                if self.db_param[db_param] != param_value:
                    return False
        self.db_param.update(param_values)
        return True

    def execute_sql(self, sql: str):
        if self.dialect == 'snowflake':
            restart_flag = False
        else:
            restart_flag = True
        flag, res = sql_execute(self.dialect, self.db_name, sql, self.db_param, restart_flag=restart_flag)
        return flag, res

    def fetch_type(self, object, is_table=False):
        return get_type(self.dialect, self.db_name, object, is_table, self.db_param)

    def explain_execute_sql(self, sql: str):
        if self.dialect == 'mysql':
            return self.execute_sql('EXPLAIN ' + sql)
        elif self.dialect == 'oracle':
            return self.execute_sql('EXPLAIN PLAN FOR ' + sql)
        elif self.dialect == 'pg':
            return self.execute_sql('EXPLAIN ' + sql)
        elif self.dialect == 'snowflake':
            return self.execute_sql('EXPLAIN USING TEXT ' + sql)
        elif self.dialect == 'sqlite':
            return self.execute_sql('EXPLAIN QUERY PLAN ' + sql)
        elif self.dialect == 'sqlserver':
            self.execute_sql('SET SHOWPLAN_ALL ON')
            try:
                return self.execute_sql(sql)
            finally:
                self.execute_sql('SET SHOWPLAN_ALL OFF')
        else:
            raise NotImplementedError(f'Unsupported dialect: {self.dialect}')
