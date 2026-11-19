import json
import os
import traceback
from typing import List

import pymssql

from dialects.BaseDialect import BaseDialect
from dialects.dialect_utils import convert_decimal_to_float, get_db_name, build_attributes, normalize_executable_sql
from sql_gen.generator.ele_type.type_def import BaseType
from sql_gen.generator.ele_type.type_operation import load_col_type
from utils.tools import load_sqlserver_config, get_empty_db_name, get_proj_root_path, get_all_db_name, \
    scale_name_into_length


class SQLServerDialect(BaseDialect):
    name = 'sqlserver'

    def __init__(self, config_file=None):
        self.config = load_sqlserver_config(config_file)
        self.conn_map = {}
        self.cursor_map = {}
        with open(os.path.join(get_proj_root_path(), 'src', 'utils', f'{self.name}_reserved_keyword.json'), 'r') as f:
            self.reserved_keywords = json.load(f)

    def execute(self, db_name: str, sql: str, db_param=None, emp_flag=False, restart_flag=False):
        sql = normalize_executable_sql(sql)
        if emp_flag:
            db_name = get_empty_db_name(db_name)
        db_name = get_db_name(self.name, db_name)
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
        except (Exception, pymssql.Error) as error:
            print(sql)
            connection.rollback()
            traceback.print_exc()
            return False, f"Error while executing SQL Server query: {error}"

    def dependent_execute(self, db_name: str, sql: str, db_param=None):
        sql = normalize_executable_sql(sql)
        db_name = get_db_name(self.name, db_name)
        connection = pymssql.connect(
            server=self.config['sqlserver_host'],
            user=self.config['sqlserver_user'],
            password=self.config['sqlserver_pwd'],
            port=self.config['sqlserver_port'],
            database=db_name
        )
        cursor = connection.cursor()
        try:
            if db_param is not None:
                for key, value in db_param.items():
                    cursor.execute(f"SET {key} {value}")
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
            conn = self.conn_map[db_name]
            if conn:
                return self.conn_map[db_name], self.cursor_map[db_name]
        try:
            conn = pymssql.connect(
                server=self.config["sqlserver_host"],
                user=self.config["sqlserver_user"],
                password=self.config["sqlserver_pwd"],
                database="master",
                port=self.config.get("sqlserver_port", 1433),
                autocommit=True
            )
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sys.databases ORDER BY name;")
            databases = [db[0] for db in cursor.fetchall()]

            if db_name not in databases:
                print(f"Database '{db_name}' does not exist, creating...")
                cursor.execute(f"CREATE DATABASE [{db_name}];")
                cursor.execute(f"ALTER DATABASE [{db_name}] COLLATE Chinese_PRC_CS_AI;")
                print(f"Database '{db_name}' created successfully!")
                conn.commit()
                flag = True
        except (Exception, pymssql.Error) as error:
            print(f"Error while connecting to SQL Server: {error}")

        try:
            conn = pymssql.connect(
                server=self.config["sqlserver_host"],
                user=self.config["sqlserver_user"],
                password=self.config["sqlserver_pwd"],
                database=db_name,
                port=self.config.get("sqlserver_port", 1433),
            )
            if conn:
                cursor = conn.cursor()

                self.conn_map[db_name] = conn
                self.cursor_map[db_name] = cursor
                return conn, cursor

        except (Exception, pymssql.Error) as error:
            print(f"Error while connecting to SQL Server: {error}")

    def close_connect(self, db_name: str):
        connection = self.conn_map[db_name]
        cursor = self.cursor_map[db_name]
        if connection:
            cursor.close()
            connection.close()
            self.conn_map.pop(db_name)
            self.cursor_map.pop(db_name)
            print("SQL Server connection is closed")

    def drop_db(self, db_name: str):
        try:
            db_name = get_db_name(self.name, db_name)
            conn = pymssql.connect(
                server=self.config["sqlserver_host"],
                user=self.config["sqlserver_user"],
                password=self.config["sqlserver_pwd"],
                database="master",
                port=self.config.get("sqlserver_port", 1433),
                autocommit=True
            )
            cursor = conn.cursor()
            if db_name in self.conn_map:
                self.close_connect(db_name)
            cursor.execute(f"DROP DATABASE [{db_name}];")
            conn.commit()
            cursor.close()
            conn.close()
            print(f"Database '{db_name}' dropped successfully!")
        except (Exception, pymssql.Error) as error:
            print(f"Error while connecting to SQL server: {error}")

    def show_databases(self):
        try:
            conn = pymssql.connect(
                server=self.config["sqlserver_host"],
                user=self.config["sqlserver_user"],
                password=self.config["sqlserver_pwd"],
                database="master",
                port=self.config.get("sqlserver_port", 1433),
            )
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sys.databases ORDER BY name;")
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error while connecting to SQL Server: {e}")
            return None
        finally:
            try:
                cursor.close()
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
                    cursor.execute(f"SET {key} {value}")
                connection.commit()
            sql = obj
            meta_sql = f"""
                SELECT
                    name,
                    system_type_name
                FROM sys.dm_exec_describe_first_result_set(
                    N'{sql.replace("'", "''")}',
                    NULL,
                    0
                );
            """
            cursor.execute(meta_sql.strip().strip(';'))
            rows = cursor.fetchall()
            return True, [{"col": row[0], "type": row[1]} for row in rows]
        except Exception as e:
            error_message = str(e)
            print(obj)
            print(f"Error executing SQL on database {db_name}: {error_message}")
            return False, [error_message]

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

            sqlserver_type = col['type'].get_type_name(self.name)
            if sqlserver_type is None:
                continue
            attributes = build_attributes(col['type'], col.get('attribute', None), self.name)
            str_attribute = " ".join(attributes) if attributes else ""
            col_def = f"\t{self.get_table_col_name(col_name)} {sqlserver_type} {str_attribute}".strip()
            col_defs_list.append(col_def)

        col_defs_str = ",\n".join(col_defs_list)
        create_stmt = f"CREATE TABLE {self.get_table_col_name(table_name)} (\n{col_defs_str}"

        all_constraints = []
        if primary_keys:
            pk_name = self.get_table_col_name(scale_name_into_length(f'PK_{table_name}'))
            all_constraints.append(f"CONSTRAINT {pk_name} PRIMARY KEY ({primary_keys})")

        all_constraints.extend(constraints)
        if all_constraints:
            create_stmt += ",\n\t" + ",\n\t".join(all_constraints)
        create_stmt += "\n);"
        return create_stmt

    def add_index(self, schema):
        table = schema['table']
        res = []
        table_idx_map = {}
        if 'index' not in schema:
            return res
        for index_cols in schema['index']:
            column_list = [self.get_table_col_name(col) for col in index_cols]
            str_columns = ', '.join(column_list)
            if table not in table_idx_map:
                table_idx_map[table] = 0
            table_idx_map[table] += 1
            idx = table_idx_map[table]
            index_name_raw = f"IDX_{table}_{idx}"
            index_name = scale_name_into_length(index_name_raw)

            formatted_table = self.get_table_col_name(table)
            res.append(f"CREATE INDEX {index_name} ON {formatted_table} ({str_columns});")
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
                # 使用 join 提高效率并保持代码整洁
                column_list = ', '.join([self.get_table_col_name(c) for c in ori_column])
                assert isinstance(ori_ref_column, list)
                ref_column_list = ', '.join([self.get_table_col_name(rc) for rc in ori_ref_column])
            else:
                column_list = self.get_table_col_name(ori_column)
                ref_column_list = self.get_table_col_name(ori_ref_column)

            if table not in table_idx_map:
                table_idx_map[table] = 1
            else:
                table_idx_map[table] += 1

            idx = table_idx_map[table]

            constraint_name = scale_name_into_length(f'FK_{table}_{idx}')

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
            name = f"[{name}]"
        elif ' ' in name or '-' in name:
            name = f"[{name}]"
        return name

