import json
import os
import re
import subprocess
import zoneinfo
from typing import List

import oracledb

from dialects.BaseDialect import BaseDialect
from dialects.dialect_utils import get_db_name, build_attributes, normalize_executable_sql
from sql_gen.generator.ele_type.type_def import BaseType
from sql_gen.generator.ele_type.type_operation import load_col_type
from utils.tools import load_oracle_config, get_empty_db_name, get_proj_root_path, \
    scale_name_into_length


def output_type_handler(cursor, name, default_type, length, precision, scale):
    if default_type == oracledb.DB_TYPE_DATE:
        return cursor.var(
            oracledb.DB_TYPE_DATE,
            arraysize=cursor.arraysize,
            outconverter=lambda x: x.date() if x else None
        )
    elif default_type == oracledb.DB_TYPE_TIMESTAMP_TZ:
        return cursor.var(
            oracledb.DB_TYPE_TIMESTAMP_TZ,
            arraysize=cursor.arraysize,
            outconverter=lambda x: x.replace(tzinfo=zoneinfo.ZoneInfo(key="Asia/Shanghai"))  # x 已经是带时区的 datetime 对象
        )
    return None


class OracleDialect(BaseDialect):
    name = 'oracle'
    def __init__(self, config_file=None):
        self.conn_map = {}
        self.cursor_map = {}
        self.config = load_oracle_config(config_file)
        oracledb.init_oracle_client(lib_dir=self.config['oracle_instant_path'])
        self.types = None
        self.sql_plus_flag = False
        with open(os.path.join(get_proj_root_path(), 'src', 'utils', f'{self.name}_reserved_keyword.json'), 'r') as f:
            self.reserved_keywords = json.load(f)

    def execute(self, db_name: str, sql: str, db_param=None, emp_flag=False, restart_flag=False):
        sql = normalize_executable_sql(sql)
        if emp_flag:
            db_name = get_empty_db_name(db_name)
        db_name = get_db_name(self.name, db_name)
        if not self.sql_plus_flag:
            connection, cursor = self.connect(db_name, restart_flag)
            try:
                if db_param is not None:
                    for key, value in db_param.items():
                        cursor.execute(f"ALTER SESSION SET {key} = '{value}'")
                    connection.commit()
                cursor.execute(sql)
                if sql.startswith('INSERT') or sql.startswith('CREATE'):
                    connection.commit()
                    return True, []
                elif "SELECT" in sql.upper() and not 'EXPLAIN PLAN FOR' in sql:
                    result = cursor.fetchall()
                    return True, result
                else:
                    connection.commit()
                    return True, []
            except Exception as e:
                # Handle the exception, log the error, and optionally raise
                error_message = str(e)
                print(sql)
                print(f"Error executing SQL on database {db_name}: {error_message}")
                return False, error_message
        else:
            sqlplus_path = "sqlplus"
            user = self.config['oracle_user'],
            password = self.config['oracle_pwd'],
            server_ip = self.config['oracle_host'],
            server_port = self.config['oracle_port']
            db_string = db_name
            sqlplus_command = f"{sqlplus_path} -S {user}/{password}@{server_ip}:{server_port}/{db_string}"
            process = subprocess.run(sqlplus_command, shell=True,
                                     input='alter session set nls_language=american;\n ' + sql + ';',
                                     text=True, capture_output=True)
            return False, f"Error while executing Oracle query: {process.stdout}"


    def dependent_execute(self, db_name: str, sql: str, db_param=None):
            sql = normalize_executable_sql(sql)
            db_name = get_db_name(self.name, db_name)
            if db_name.startswith('tran') or db_name.startswith('emp_tran'):
                port = 36792
            else:
                port = self.config['oracle_port']
            connection = oracledb.connect(
                user=db_name,
                password=self.config['usr_default_pwd'],
                host=self.config['oracle_host'],
                port=port,
                service_name=self.config['oracle_sid']
            )
            connection.outputtypehandler = output_type_handler
            cursor = connection.cursor()
            try:
                if db_param is not None:
                    for key, value in db_param.items():
                        cursor.execute(f"ALTER SESSION SET {key} = '{value}'")
                    connection.commit()
                cursor.execute(sql)
                if sql.startswith('INSERT') or sql.startswith('CREATE'):
                    connection.commit()
                    return True, []
                elif "SELECT" in sql.upper() and not 'EXPLAIN PLAN FOR' in sql:
                    result = cursor.fetchall()
                    return True, result
                else:
                    connection.commit()
                    return True, []
            except Exception as e:
                # Handle the exception, log the error, and optionally raise
                error_message = str(e)
                print(sql)
                print(f"Error executing SQL on database {db_name}: {error_message}")
                return False, error_message

    def connect(self, db_name: str, restart_flag=False):
        if not restart_flag and db_name in self.conn_map:
            db_conn = self.conn_map[db_name]
            try:
                db_conn.ping()
                return db_conn, self.cursor_map[db_name]
            except Exception:
                pass
        if db_name.startswith('tran') or db_name.startswith('emp_tran'):
            port = 36792
        else:
            port = self.config['oracle_port']
        connection = oracledb.connect(
            user=self.config['oracle_sys_user'],
            password=self.config['oracle_sys_pwd'],
            host=self.config['oracle_host'],
            port=port,
            service_name=self.config['oracle_sid']
        )
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute(f"SELECT USERNAME FROM DBA_USERS")
        users = [user[0] for user in cursor.fetchall()]
        if db_name.upper() not in users:
            try:
                print(f'CREATE usr {db_name}')
                cursor.execute(f"CREATE USER {db_name} IDENTIFIED BY {self.config['usr_default_pwd']}")
                cursor.execute(f"GRANT CONNECT, RESOURCE TO {db_name}")
                cursor.execute(f"GRANT CREATE SESSION TO {db_name}")
                cursor.execute(f"GRANT ALTER SESSION TO {db_name}")
                cursor.execute(f"GRANT CREATE TABLE TO {db_name}")
                connection.commit()
            except Exception as e:
                print(f"Error creating user {db_name}: {e}")
                return False, f"Error creating user {db_name}: {e}"
        cursor.close()
        connection.close()

        connection = oracledb.connect(
            user=db_name,
            password=self.config['usr_default_pwd'],
            host=self.config['oracle_host'],
            port=port,
            service_name=self.config['oracle_sid']
        )
        cursor = connection.cursor()
        self.cursor_map[db_name] = cursor
        self.conn_map[db_name] = connection
        connection.outputtypehandler = output_type_handler
        return connection, cursor

    def close_connect(self, db_name: str):
        connection = self.conn_map[db_name]
        cursor = self.cursor_map[db_name]
        if connection:
            cursor.close()
            connection.close()
            self.conn_map.pop(db_name)
            self.cursor_map.pop(db_name)

    def drop_db(self, db_name: str):
        try:
            db_name = get_db_name(self.name, db_name)
            if db_name.startswith('tran') or db_name.startswith('emp_tran'):
                port = 36792
            else:
                port = self.config['oracle_port']
            connection = oracledb.connect(
                user=self.config['oracle_sys_user'],
                password=self.config['oracle_sys_pwd'],
                host=self.config['oracle_host'],
                port=port,
                service_name=self.config['oracle_sid']
            )
            if db_name in self.conn_map:
                self.close_connect(db_name)
            cursor = connection.cursor()
            cursor.execute(f"DROP USER {db_name} CASCADE")
            print(f"Drop {db_name} successfully!")
            connection.commit()
        except Exception as e:
            print(f"Error dropping user {db_name}: {e}")
            return False
        cursor.close()
        connection.close()
        return True

    def show_databases(self):
        try:
            connection = oracledb.connect(
                user=self.config['oracle_sys_user'],
                password=self.config['oracle_sys_pwd'],
                host=self.config['oracle_host'],
                port=self.config['oracle_port'],
                service_name=self.config['oracle_sid']
            )
            cursor = connection.cursor()
            cursor.execute(f"SELECT USERNAME FROM DBA_USERS")
            users = [user[0] for user in cursor.fetchall()]
            return users
        except Exception as e:
            print(f"Error while connecting to Oracle: {e}")
            return None

    def get_data_type(self, db_name: str, obj: str, is_table: bool, db_param: dict | None = None) -> tuple[bool, List]:
        if is_table:
            table_name = obj
            with open(os.path.join(get_proj_root_path(), 'data', db_name, 'schema.json'), 'r') as file:
                schema = json.loads(file.read())
            if table_name not in schema:
                raise ValueError(f"Table {table_name} not found in schema")
            else:
                res = []
                for col in schema[table_name]['cols']:
                    col_name = col['col']
                    col_type, _, _ = load_col_type(col['type'], col['col_name'], self.name, db_name, table_name)
                    res.append({
                        "col": col_name.lower(),
                        "type": col_type
                    })
                return True, res
        try:
            db_name = get_empty_db_name(db_name)
            db_name = get_db_name(self.name, db_name)
            connection, cursor = self.connect(db_name, False)
            if db_param is not None:
                for key, value in db_param.items():
                    cursor.execute(f"ALTER SESSION SET {key} = '{value}'")
                connection.commit()
            sql = obj
            cursor.execute(sql.strip().strip(';'))
            res = []
            for column in cursor.description:
                match = re.search(r'DB_TYPE_(\w+)', column[1].name)
                assert match
                type_name = match.group(1)
                res.append({
                    "col": column[0].lower(),
                    "type": type_name
                })
            cursor.fetchall()
            return True, res
        except Exception as e:
            error_message = str(e)
            print(obj)
            print(f"Error executing SQL on database {db_name}: {error_message}")
            return False, [error_message]


    def test_sql(self, ddls: list[str], sql: str):
        test_db_name = 'test'
        self.connect(test_db_name, True)
        for ddl in ddls:
            if ddl.strip() == '':
                continue
            self.execute(test_db_name, ddl)
        flag, res = self.execute(test_db_name, sql)
        self.drop_db(test_db_name)
        return flag, res


    def create_table(self, table_schema, constraints):
        table_name = table_schema['table']
        cols = table_schema['cols']
        primary_keys = ''
        if "primary_key" in table_schema:
            primary_key = table_schema['primary_key']
            for key in primary_key:
                if primary_keys != '':
                    primary_keys = primary_keys + ', '
                primary_keys = primary_keys + self.get_table_col_name(key)
        col_defs = ''
        for col in cols:
            col_name = col['col_name']
            assert isinstance(col['type'], BaseType)
            if col['type'].get_type_name(self.name) is None:
                continue
            attributes = build_attributes(col['type'], col.get('attribute', None), self.name)
            str_attribute = ''
            for attribute in attributes:
                assert attribute == 'NOT NULL' or attribute == 'UNIQUE'
                str_attribute = str_attribute + ' '
                str_attribute = str_attribute + attribute
            type_def = (f"\t{self.get_table_col_name(col_name)} "
                        f"{col['type'].get_type_name(self.name)} {str_attribute}")
            if col_defs != '':
                col_defs = col_defs + ',\n'
            col_defs = col_defs + type_def
        create_stmt = f"CREATE TABLE {self.get_table_col_name(table_name)} (\n{col_defs}"
        for constraint in constraints:
            create_stmt += ',\n\t' + constraint
        if primary_keys != '':
            create_stmt += ',\n\t' + (
                f"CONSTRAINT {self.get_table_col_name(scale_name_into_length(f'PK_{table_name}'))} "
                f"PRIMARY KEY ({primary_keys})")
        create_stmt += '\n);'
        return create_stmt


    def add_foreign_key(self, schema):
        table = schema['table']
        res = []
        if 'foreign_key' not in schema:
            return res
        table_idx_map = {}
        for fk in schema['foreign_key']:
            ori_column = fk['col']
            ref_table = fk['ref_table']
            ori_ref_column = fk['ref_col']
            if isinstance(ori_column, list):
                column_list = ''
                for column in ori_column:
                    if column_list != '':
                        column_list = column_list + ', '
                    column_list = column_list + self.get_table_col_name(column)
                assert isinstance(ori_ref_column, list)
                ref_column_list = ''
                for ref_column in ori_ref_column:
                    if ref_column_list != '':
                        ref_column_list = ref_column_list + ', '
                    ref_column_list = ref_column_list + self.get_table_col_name(ref_column)
            else:
                column_list = self.get_table_col_name(ori_column)
                ref_column_list = self.get_table_col_name(ori_ref_column)
            if table not in table_idx_map:
                table_idx_map[table] = 0
            table_idx_map[table] = table_idx_map[table] + 1
            idx = table_idx_map[table]
            res.append((
                f"ALTER TABLE {self.get_table_col_name(table)}\n"
                f"ADD CONSTRAINT {scale_name_into_length(f'FK_{table}_{idx}')} "
                f"FOREIGN KEY ({column_list})\n\t"
                f"REFERENCES {self.get_table_col_name(ref_table)} ({ref_column_list});"))
        return res


    def add_index(self, schema):
        table = schema['table']
        res = []
        table_idx_map = {}
        if 'index' not in schema:
            return res
        for index_cols in schema['index']:
            str_columns = ''
            for col in index_cols:
                if str_columns != '':
                    str_columns = str_columns + ', '
                str_columns = str_columns + self.get_table_col_name(col)
            if table not in table_idx_map:
                table_idx_map[table] = 0
            table_idx_map[table] = table_idx_map[table] + 1
            idx = table_idx_map[table]
            res.append(
                f"CREATE INDEX {scale_name_into_length(f'IDX_{table}_{idx}')} ON {self.get_table_col_name(table)} "
                f"({str_columns});")
        return res

    def get_table_col_name(self, name):
        if name.upper() in self.reserved_keywords:
            name = f"\"{name}\""
        elif ' ' in name or '-' in name:
            name = f"\"{name}\""
        return name

