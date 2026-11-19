import json
import os
import traceback
from typing import List

import snowflake.connector

from dialects.BaseDialect import BaseDialect
from dialects.dialect_utils import convert_decimal_to_float, get_db_name, build_attributes
from sql_gen.generator.ele_type.type_def import BaseType
from sql_gen.generator.ele_type.type_operation import load_col_type
from utils.tools import load_snowflake_config, get_empty_db_name, scale_name_into_length, \
    get_proj_root_path


class SnowflakeDialect(BaseDialect):
    name = "snowflake"

    def __init__(self, config_file=None):
        self.conn_map = {}
        self.cursor_map = {}
        self.config = load_snowflake_config(config_file)
        with open(os.path.join(get_proj_root_path(), 'src', 'utils', f'{self.name}_reserved_keyword.json'), 'r') as f:
            self.reserved_keywords = json.load(f)


    def execute(self, db_name: str, sql: str, db_param=None, emp_flag=False, restart_flag=False):
        if emp_flag:
            db_name = get_empty_db_name(db_name)
        db_name = get_db_name(self.name, db_name)

        connection, cursor = self.connect(db_name, restart_flag)
        if not connection or not cursor:
            return False, "Snowflake connection failed."
        try:
            if db_param is not None:
                for key, value in db_param.items():
                    safe_val = str(value).replace("'", "''")
                    cursor.execute(f"ALTER SESSION SET {key} = '{safe_val}';")
            cursor.execute(sql.strip().rstrip(';'))
            if cursor.description:
                rows = cursor.fetchall()
            else:
                rows = None
            rows = convert_decimal_to_float(rows)
            return True, rows
        except Exception as error:
            print(sql)
            traceback.print_exc()
            return False, f"Error while executing Snowflake query: {error}"

    def dependent_execute(self, db_name: str, sql: str, db_param=None):
        db_name = get_db_name(self.name, db_name)
        conn = None
        cursor = None
        try:
            conn = snowflake.connector.connect(
                account=self.config["snowflake_account"],
                user=self.config["snowflake_user"],
                password=self.config["snowflake_pwd"],
                role=self.config.get("snowflake_role"),
            )
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES;")
            dbs = {row[1] for row in cursor.fetchall()}
            if db_name not in dbs:
                print(f"Database '{db_name}' does not exist, creating...")
                cursor.execute(f"CREATE DATABASE \"{db_name}\";")
                print(f"Database '{db_name}' created successfully!")
            cursor.execute(f"USE DATABASE \"{db_name}\";")
            if self.config.get("sf_schema"):
                cursor.execute(f'USE SCHEMA \"{self.config["sf_schema"]}\";')
            if not conn or not cursor:
                return False, "Snowflake connection failed."
            try:
                if db_param is not None:
                    for key, value in db_param.items():
                        safe_val = str(value).replace("'", "''")
                        cursor.execute(f"ALTER SESSION SET {key} = '{safe_val}';")
                cursor.execute(sql.strip().rstrip(';'))
                if cursor.description:
                    rows = cursor.fetchall()
                else:
                    rows = None
                rows = convert_decimal_to_float(rows)
                return True, rows
            except Exception as error:
                print(sql)
                traceback.print_exc()
                return False, f"Error while executing Snowflake query: {error}"
        except Exception as error:
            print(f"Error while connecting to Snowflake: {error}")
            traceback.print_exc()
            try:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
            except Exception:
                pass
            return None, None

    def connect(self, db_name: str, restart_flag=False):
        if (not restart_flag) and db_name in self.conn_map:
            conn = self.conn_map.get(db_name)
            cur = self.cursor_map.get(db_name)
            if conn and cur:
                return conn, cur
        db_name = get_db_name(self.name, db_name)
        conn = None
        cursor = None
        try:
            conn = snowflake.connector.connect(
                account=self.config["snowflake_account"],
                user=self.config["snowflake_user"],
                password=self.config["snowflake_pwd"],
                role=self.config.get("snowflake_role"),
            )
            cursor = conn.cursor()

            # 不存在则创建
            cursor.execute("SHOW DATABASES;")
            dbs = {row[1] for row in cursor.fetchall()}
            if db_name not in dbs:
                print(f"Database '{db_name}' does not exist, creating...")
                cursor.execute(f"CREATE DATABASE \"{db_name}\";")
                print(f"Database '{db_name}' created successfully!")
            cursor.execute(f"USE DATABASE \"{db_name}\";")
            if self.config.get("sf_schema"):
                cursor.execute(f'USE SCHEMA \"{self.config["sf_schema"]}\";')

            self.conn_map[db_name] = conn
            self.cursor_map[db_name] = cursor
            return conn, cursor

        except Exception as error:
            print(f"Error while connecting to Snowflake: {error}")
            traceback.print_exc()
            try:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
            except Exception:
                pass
            return None, None

    def close_connect(self, db_name: str):
        connection = self.conn_map.get(db_name)
        cursor = self.cursor_map.get(db_name)
        try:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
        finally:
            self.conn_map.pop(db_name, None)
            self.cursor_map.pop(db_name, None)
            print("Snowflake connection is closed")

    def drop_db(self, db_name: str):
        conn = None
        cursor = None
        try:
            db_name = get_db_name(self.name, db_name)
            if db_name in self.conn_map:
                self.close_connect(db_name)

            conn = snowflake.connector.connect(
                account=self.config["snowflake_account"],
                user=self.config["snowflake_user"],
                password=self.config["snowflake_pwd"],
                role=self.config.get("snowflake_role")
            )
            cursor = conn.cursor()
            # cursor.execute(f"DROP DATABASE IF EXISTS {_sf_ident(db_name)} CASCADE;")
            cursor.execute(f"DROP DATABASE IF EXISTS \"{db_name}\";")

            print(f"Database '{db_name}' dropped successfully!")
        except Exception as error:
            print(f"Error while connecting to Snowflake: {error}")
            traceback.print_exc()
        finally:
            try:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
            except Exception:
                pass

    def show_databases(self):
        conn = None
        cursor = None
        try:
            conn = snowflake.connector.connect(
                account=self.config["snowflake_account"],
                user=self.config["snowflake_user"],
                password=self.config["snowflake_pwd"],
                role=self.config.get("snowflake_role"),
                schema=self.config.get("snowflake_schema"),
            )
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES;")
            return [row[1] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error while connecting to Snowflake: {e}")
            return None
        finally:
            try:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
            except Exception:
                pass

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
                    col_type, _, _ = load_col_type(col['type'], col['col_name'], 'snowflake', db_name, table_name)
                    res.append({
                        "col": col_name.lower(),
                        "type": col_type
                    })
                return True, res

        try:
            db_name = get_empty_db_name(db_name)
            db_name = get_db_name('pg', db_name)
            connection, cursor = self.connect(db_name)
            sql = obj
            if db_param is not None:
                for key, value in db_param.items():
                    safe_val = str(value).replace("'", "''")
                    cursor.execute(f"ALTER SESSION SET {key} = '{safe_val}';")
            cursor.execute(sql)

            res = []
            if cursor.description:
                for column in cursor.description:
                    col_name = getattr(column, "name", None)
                    if col_name is None:
                        col_name = column[0]

                    col_type = getattr(column, "type_code", None)
                    if col_type is None and len(column) > 1:
                        col_type = column[1]
                    res.append({
                        "col": str(col_name).lower(),
                        "type": str(col_type)
                    })
            return True, res

        except Exception as error:
            print(obj)
            traceback.print_exc()
            return False, [f"Error while executing Snowflake query: {error}"]

    def test_sql(self, ddls: list[str], sql: str):
        test_db_name = 'test'
        self.drop_db(test_db_name)
        self.connect(test_db_name, True)

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
            primary_keys = ", ".join([self.get_table_col_name(key) for key in primary_key])

        col_defs_list = []
        for col in cols:
            col_name = col['col_name']
            assert isinstance(col['type'], BaseType)
            snowflake_type = col['type'].get_type_name(self.name)
            if snowflake_type is None:
                continue
            attributes = build_attributes(col['type'], col.get('attribute', None), self.name)
            str_attribute = " ".join(attributes) if attributes else ""
            col_def = f"    {self.get_table_col_name(col_name)} {snowflake_type} {str_attribute}".strip()
            col_defs_list.append(col_def)

        col_defs_str = ",\n".join(col_defs_list)

        create_stmt = f"CREATE TABLE {self.get_table_col_name(table_name)} (\n{col_defs_str}"

        all_constraints = []
        if primary_keys:
            pk_name = self.get_table_col_name(scale_name_into_length(f'PK_{table_name}'))
            all_constraints.append(f"CONSTRAINT {pk_name} PRIMARY KEY ({primary_keys})")

        all_constraints.extend(constraints)

        if all_constraints:
            create_stmt += ",\n    " + ",\n    ".join(all_constraints)

        create_stmt += "\n);"
        return create_stmt

    def add_index(self, schema):
        table = schema['table']
        res = []
        if 'index' not in schema:
            return res
        for i, index_cols in enumerate(schema['index']):
            if i == 0:
                column_list = [self.get_table_col_name(col) for col in index_cols]
                str_columns = ', '.join(column_list)

                formatted_table = self.get_table_col_name(table)
                sql = f"ALTER TABLE {formatted_table} CLUSTER BY ({str_columns});"
                res.append(sql)
            else:
                continue
        return res

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
                column_list = ', '.join([self.get_table_col_name(c) for c in ori_column])
                assert isinstance(ori_ref_column, list)
                ref_column_list = ', '.join([self.get_table_col_name(rc) for rc in ori_ref_column])
            else:
                column_list = self.get_table_col_name(ori_column)
                ref_column_list = self.get_table_col_name(ori_ref_column)

            table_idx_map[table] = table_idx_map.get(table, 0) + 1
            idx = table_idx_map[table]

            constraint_name = self.get_table_col_name(scale_name_into_length(f'FK_{table}_{idx}'))

            sql = (
                f"ALTER TABLE {self.get_table_col_name(table)}\n"
                f"ADD CONSTRAINT {constraint_name} \n"
                f"FOREIGN KEY ({column_list})\n"
                f"REFERENCES {self.get_table_col_name(ref_table)} ({ref_column_list});"
            )
            res.append(sql)
        return res


    def get_table_col_name(self, name):
        if name.upper() in self.reserved_keywords:
            name = f"\"{name}\""
        elif ' ' in name or '-' in name:
            name = f"\"{name}\""
        return name
