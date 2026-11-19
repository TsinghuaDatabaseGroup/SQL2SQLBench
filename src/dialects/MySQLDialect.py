import json
import os
from typing import List

from dialects.BaseDialect import BaseDialect
import mysql.connector

from dialects.dialect_utils import convert_decimal_to_float, get_db_name, build_attributes, normalize_executable_sql
from sql_gen.generator.ele_type.type_operation import load_col_type
from utils.tools import load_mysql_config, get_empty_db_name, get_proj_root_path, \
    scale_name_into_length


class MySQLDialect(BaseDialect):
    name = 'mysql'
    def __init__(self, config_file=None):
        self.conn_map = {}
        self.cursor_map = {}
        self.config = load_mysql_config(config_file)
        self.types = None
        with open(os.path.join(get_proj_root_path(), 'src', 'utils', f'{self.name}_reserved_keyword.json'), 'r') as f:
            self.reserved_keywords = json.load(f)

    def connect(self, db_name: str, restart_flag=False):
        if not restart_flag and db_name in self.conn_map:
            conn = self.conn_map[db_name]
            if conn.is_connected():
                return self.conn_map[db_name], self.cursor_map[db_name]
        try:
            connection = mysql.connector.connect(
                host=self.config['mysql_host'],
                port=self.config['mysql_port'],
                user=self.config['mysql_user'],
                password=self.config['mysql_pwd'],
            )
            cursor = connection.cursor()
            cursor.execute("SHOW DATABASES")
            databases = [db[0] for db in cursor.fetchall()]

            if db_name not in databases:
                print(f"Database '{db_name}' don't exist, start creating")
                cursor.execute(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
                print(f"Database '{db_name}' create successfully!")
                connection.commit()
            cursor.close()
            connection.close()
        except mysql.connector.Error as err:
            print(f"error raised: {err}")

        try:
            connection = mysql.connector.connect(
                host=self.config['mysql_host'],
                port=self.config['mysql_port'],
                user=self.config['mysql_user'],
                password=self.config['mysql_pwd'],
                database=db_name
            )
            cursor = connection.cursor()
            self.conn_map[db_name] = connection
            self.cursor_map[db_name] = cursor
            if connection.is_connected():
                return connection, cursor
        except mysql.connector.Error as e:
            print(f"Error while connecting to MySQL: {e}")

    def execute(self, db_name: str, sql: str, db_param=None, emp_flag=False, restart_flag=False):
        sql = normalize_executable_sql(sql)
        if emp_flag:
            db_name = get_empty_db_name(db_name)
        db_name = get_db_name(self.name, db_name)
        connection, cursor = self.connect(db_name, restart_flag)
        try:
            cursor.execute('SET NAMES utf8mb4 COLLATE utf8mb4_bin')
            cursor.execute('SET sql_mode = \'PAD_CHAR_TO_FULL_LENGTH\';')
            if db_param is not None:
                for key, value in db_param.items():
                    cursor.execute(f"SET SESSION {key} = '{value}'")
                connection.commit()
            cursor.execute(sql)
            rows = cursor.fetchall()
            connection.commit()
            rows = convert_decimal_to_float(rows)
            return True, rows
        except mysql.connector.Error as e:
            connection.rollback()
            return False, e.args[1]

    def dependent_execute(self, db_name: str, sql: str, db_param=None, emp_flag=False):
        sql = normalize_executable_sql(sql)
        try:
            connection = mysql.connector.connect(
                host=self.config['mysql_host'],
                port=self.config['mysql_port'],
                user=self.config['mysql_user'],
                password=self.config['mysql_pwd'],
                database=db_name
            )
            cursor = connection.cursor()
            cursor.execute('SET NAMES utf8mb4 COLLATE utf8mb4_bin')
            if db_param is not None:
                for key, value in db_param.items():
                    cursor.execute(f"SET SESSION {key} = '{value}'")
                connection.commit()
            cursor.execute(sql)
            rows = cursor.fetchall()
            connection.commit()
            return True, rows
        except mysql.connector.Error as e:
            print(sql)
            print(f"Error while executing MySQL SQL: {e}")
            return False, f"Error while executing MySQL SQL: {e}"

    def show_databases(self):
        try:
            connection = mysql.connector.connect(
                host=self.config['mysql_host'],
                port=self.config['mysql_port'],
                user=self.config['mysql_user'],
                password=self.config['mysql_pwd']
            )
            cursor = connection.cursor()
            cursor.execute("SHOW DATABASES")
            databases = [db[0] for db in cursor.fetchall()]
            return databases
        except mysql.connector.Error as err:
            print(f"error raised: {err}")
            return None

    def drop_db(self, db_name: str):
        try:
            connection = mysql.connector.connect(
                host=self.config['mysql_host'],
                port=self.config['mysql_port'],
                user=self.config['mysql_user'],
                password=self.config['mysql_pwd']
            )
            db_name = get_db_name(self.name, db_name)
            if db_name in self.conn_map:
                self.close_connect(db_name)
            cursor = connection.cursor()
            cursor.execute(f"DROP DATABASE `{db_name}`")
            connection.commit()
            cursor.close()
            connection.close()
            print(f"Database '{db_name}' dropped successfully!")
        except mysql.connector.Error as err:
            print(f"error raised: {err}")

    def _get_mysql_type_by_oid(self, type_code):
        if self.types is None:
            with open(os.path.join(get_proj_root_path(), 'src', 'sql_gen', 'generator', 'ele_type', 'mysql_types.json'),
                      'r') as file:
                self.types = json.loads(file.read())
        if str(type_code) in self.types:
            return self.types[str(type_code)]
        else:
            return "UNKNOWN"

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
            connection, cursor = self.connect(db_name)
            if db_param is not None:
                for key, value in db_param:
                    cursor.execute(f"SET SESSION {key} = '{value}'")
                connection.commit()
            sql = obj
            cursor.execute(sql)
            columns = cursor.description
            res = []
            i = 0
            for column in columns:
                col_name = column[0]
                col_type_code = column[1]
                col_type = self._get_mysql_type_by_oid(col_type_code)
                res.append({
                    "col": col_name.lower(),
                    "type": col_type
                })
                i = i + 1
            rows = cursor.fetchall()
            connection.commit()
            return True, res
        except mysql.connector.Error as e:
            print(obj)
            connection.rollback()
            return False, [str(e)]

    def close_connect(self, db_name: str):
        connection = self.conn_map[db_name]
        cursor = self.cursor_map[db_name]
        if connection.is_connected():
            cursor.close()
            connection.close()
            del self.conn_map[db_name]
            del self.cursor_map[db_name]
            print("MySQL connection is closed")

    def test_sql(self, ddls: list[str], sql: str):
        test_db_name = 'test'
        self.connect(test_db_name)
        for ddl in ddls:
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
            if col['type'].get_type_name(self.name) is None:
                continue
            assert isinstance(col, dict)
            attributes = build_attributes(col['type'], col.get('attribute', None), self.name)
            str_attribute = ''
            for attribute in attributes:
                str_attribute = str_attribute + ' '
                str_attribute = str_attribute + attribute
            type_def = (f"\t{self.get_table_col_name(col_name)} "
                        f"{col['type'].get_type_name(self.name)}{str_attribute}")
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
                f"ALTER TABLE {self.get_table_col_name(table)} ADD CONSTRAINT "
                f"{self.get_table_col_name(scale_name_into_length(f'FK_{table}_{idx}'))} "
                f"FOREIGN KEY ({column_list}) REFERENCES {self.get_table_col_name(ref_table)} ({ref_column}) "
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
                table_idx_map[table] = 0
            table_idx_map[table] = table_idx_map[table] + 1
            idx = table_idx_map[table]
            res.append(
                f"CREATE INDEX {scale_name_into_length(f'IDX_{table}_{idx}')} ON {self.get_table_col_name(table)} "
                f"({str_columns});")
        return res


    def get_table_col_name(self, name):
        if name.upper() in self.reserved_keywords:
            name = f"`{name}`"
        elif ' ' in name or '-' in name:
            name = f"`{name}`"
        return name


