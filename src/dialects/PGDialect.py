import json
import os
import traceback
from typing import List

import psycopg

from dialects.BaseDialect import BaseDialect
from dialects.dialect_utils import convert_decimal_to_float, get_db_name, build_attributes, normalize_executable_sql
from sql_gen.generator.ele_type.type_operation import load_col_type
from utils.tools import load_pg_config, get_empty_db_name, get_proj_root_path, \
    scale_name_into_length


class PGDialect(BaseDialect):
    def __init__(self, config_file=None):
        self.name = 'pg'
        self.conn_map = {}
        self.cursor_map = {}
        self.config = load_pg_config(config_file)
        self.types = None
        with open(os.path.join(get_proj_root_path(), 'src', 'utils', f'{self.name}_reserved_keyword.json'), 'r') as f:
            self.reserved_keywords = json.load(f)

    def execute(self, db_name: str, sql: str, db_param=None, emp_flag=False, restart_flag=False):
        sql = normalize_executable_sql(sql)
        if emp_flag:
            db_name = get_empty_db_name(db_name)
        db_name = get_db_name('pg', db_name)
        connection, cursor = self.connect(db_name, restart_flag)
        try:
            if db_param is not None:
                for key, value in db_param.items():
                    cursor.execute(f"SET {key} = '{value}';")
                connection.commit()
            cursor.execute(sql)
            if cursor.description:
                rows = cursor.fetchall()
            else:
                rows = None
            connection.commit()
            rows = convert_decimal_to_float(rows)
            return True, rows
        except (Exception, psycopg.Error) as error:
            print(sql)
            connection.rollback()
            traceback.print_exc()
            return False, f"Error while executing PostgreSQL query: {error}"

    def dependent_execute(self, db_name: str, sql: str, db_param=None):
        sql = normalize_executable_sql(sql)
        try:
            connection = psycopg.connect(
                host=self.config['pg_host'],
                port=self.config['pg_port'],
                user=self.config['pg_user'],
                password=self.config['pg_pwd'],
                dbname=db_name
            )
            cursor = connection.cursor()
            self.conn_map[db_name] = connection
            self.cursor_map[db_name] = cursor
            cursor.execute("SET lc_messages TO 'en_US.UTF-8';")
            if db_param is not None:
                for key, value in db_param.items():
                    cursor.execute(f"SET {key} = '{value}';")
                connection.commit()
            cursor.execute(sql)
            if cursor.description:
                rows = cursor.fetchall()
            else:
                rows = None
            connection.commit()
            return True, rows
        except (Exception, psycopg.Error) as error:
            print(sql)
            traceback.print_exc()
            return False, f"Error while executing PostgreSQL query: {error}"

    def connect(self, db_name: str, restart_flag=False):
        if not restart_flag and db_name in self.conn_map:
            conn = self.conn_map[db_name]
            if conn:
                return self.conn_map[db_name], self.cursor_map[db_name]
        flag = False
        try:
            connection = psycopg.connect(
                host=self.config['pg_host'],
                port=self.config['pg_port'],
                user=self.config['pg_user'],
                password=self.config['pg_pwd'],
                dbname='postgres'
            )
            connection.autocommit = True

            cursor = connection.cursor()

            cursor.execute("SELECT datname FROM pg_database;")
            databases = [db[0] for db in cursor.fetchall()]

            if db_name not in databases:
                print(f"Database '{db_name}' does not exist, creating...")
                cursor.execute(f"CREATE DATABASE \"{db_name}\";")
                print(f"Database '{db_name}' created successfully!")
                connection.commit()
                flag = True
        except (Exception, psycopg.Error) as error:
            print(f"Error while connecting to PostgreSQL: {error}")

        try:
            connection = psycopg.connect(
                host=self.config['pg_host'],
                port=self.config['pg_port'],
                user=self.config['pg_user'],
                password=self.config['pg_pwd'],
                dbname=db_name
            )

            cursor = connection.cursor()

            self.conn_map[db_name] = connection
            self.cursor_map[db_name] = cursor
            cursor.execute("SET lc_messages TO 'en_US.UTF-8';")
            if flag:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            connection.commit()
            if connection:
                return connection, cursor

        except (Exception, psycopg.Error) as error:
            print(f"Error while connecting to PostgreSQL: {error}")

    def close_connect(self, db_name: str):
        connection = self.conn_map[db_name]
        cursor = self.cursor_map[db_name]
        if connection:
            cursor.close()
            connection.close()
            self.conn_map.pop(db_name)
            self.cursor_map.pop(db_name)
            print("PostgreSQL connection is closed")

    def _get_type_name_by_oid(self, oid):
        if self.types is None:
            with open(os.path.join(get_proj_root_path(), 'src', 'sql_gen', 'generator', 'ele_type', 'pg_types.json'),
                      'r') as file:
                self.types = json.loads(file.read())
        if str(oid) in self.types:
            return self.types[str(oid)]
        else:
            return "UNKNOWN"


    def drop_db(self, db_name: str):
        try:
            db_name = get_db_name('pg', db_name)
            connection = psycopg.connect(
                host=self.config['pg_host'],
                port=self.config['pg_port'],
                user=self.config['pg_user'],
                password=self.config['pg_pwd'],
                dbname='postgres'
            )
            connection.autocommit = True
            cursor = connection.cursor()
            if db_name in self.conn_map:
                self.close_connect(db_name)
            cursor.execute(f"DROP DATABASE \"{db_name}\";")
            connection.commit()
            cursor.close()
            connection.close()
            print(f"Database '{db_name}' dropped successfully!")
        except (Exception, psycopg.Error) as error:
            print(f"Error while connecting to PostgreSQL: {error}")

    def show_databases(self):
        try:
            connection = psycopg.connect(
                host=self.config['pg_host'],
                port=self.config['pg_port'],
                user=self.config['pg_user'],
                password=self.config['pg_pwd'],
                dbname='postgres'
            )
            cursor = connection.cursor()
            cursor.execute("SELECT datname FROM pg_database;")
            databases = [db[0] for db in cursor.fetchall()]
            return databases
        except (Exception, psycopg.Error) as error:
            print(f"Error while connecting to PostgreSQL: {error}")
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
                    col_type, _, _ = load_col_type(col['type'], col['col_name'], 'pg', db_name, table_name)
                    res.append({
                        "col": col_name.lower(),
                        "type": col_type
                    })
                return True, res
        try:
            db_name = get_empty_db_name(db_name)
            db_name = get_db_name('pg', db_name)
            connection, cursor = self.connect(db_name)
            if db_param is not None:
                for key, value in db_param.items():
                    cursor.execute(f"SET {key} = '{value}';")
                connection.commit()
            sql = obj
            cursor.execute(sql)
            res = []
            if cursor.description:
                for column in cursor.description:
                    res.append({
                        "col": column.name.lower(),
                        "type": self._get_type_name_by_oid(column.type_code)
                    })
            connection.commit()
            return True, res
        except (Exception, psycopg.Error) as error:
            print(obj)
            print(f"Error while executing PostgreSQL query: {error}")
            connection.rollback()
            return False, [f"Error while executing PostgreSQL query: {error}"]

    def test_sql(self, ddls: list[str], sql: str):
        test_db_name = 'test'
        self.drop_db(test_db_name)
        self.connect(test_db_name)
        for ddl in ddls:
            if ddl.strip() == '':
                continue
            flag, res = self.execute(test_db_name, ddl)
            if not flag:
                print(res)
                exit()
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
            if col['type'].get_type_name('pg') is None:
                continue
            attributes = build_attributes(col['type'], col.get('attribute', None), 'pg')
            str_attribute = ''
            for attribute in attributes:
                str_attribute = str_attribute + ' '
                str_attribute = str_attribute + attribute
            type_def = f"\t{self.get_table_col_name(col_name)} {col['type'].get_type_name('pg')}{str_attribute}"
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
                ref_column = ''
                for column in ori_ref_column:
                    if ref_column != '':
                        ref_column = ref_column + ', '
                    ref_column = ref_column + self.get_table_col_name(column)
            else:
                column_list = self.get_table_col_name(ori_column)
                ref_column = self.get_table_col_name(ori_ref_column)
            if table not in table_idx_map:
                table_idx_map[table] = 0
            table_idx_map[table] = table_idx_map[table] + 1
            idx = table_idx_map[table]
            res.append((
                f"ALTER TABLE {self.get_table_col_name(table)}\n"
                f"ADD CONSTRAINT {scale_name_into_length(f'FK_{table}_{idx}')} "
                f"FOREIGN KEY ({column_list})\n\t"
                f"REFERENCES {self.get_table_col_name(ref_table)} ({ref_column}) "
                f"ON DELETE CASCADE ON UPDATE NO ACTION;"))
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
                table_idx_map[table] = 1
            else:
                table_idx_map[table] += 1
            idx = table_idx_map[table]
            res.append(
                f"CREATE INDEX {scale_name_into_length(f'IDX_{table}_{idx}')} "
                f"ON {self.get_table_col_name(table)} ({str_columns});")
        return res


    def get_table_col_name(self, name):
        if name.upper() in self.reserved_keywords:
            name = f"\"{name}\""
        elif ' ' in name or '-' in name:
            name = f"\"{name}\""
        return name

