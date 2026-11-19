import json
import os
import sqlite3
import traceback
from typing import List


from dialects.BaseDialect import BaseDialect
from dialects.dialect_utils import build_attributes, normalize_executable_sql
from utils.tools import load_sqlite_config, scale_name_into_length, get_proj_root_path
from utils.tools import get_empty_db_name, get_proj_root_path


class SQLiteDialect(BaseDialect):
    name = 'sqlite'

    def __init__(self, config_file=None):
        self.conn_map = {}
        self.cursor_map = {}
        self.config = load_sqlite_config(config_file)
        with open(os.path.join(get_proj_root_path(), 'src', 'utils', f'{self.name}_reserved_keyword.json'), 'r') as f:
            self.reserved_keywords = json.load(f)


    def _get_db_path(self, db_name):
        return os.path.join(self.config['sqlite_db_path'], f"{db_name}.db")

    @staticmethod
    def _escape_sqlite_literal(value):
        if isinstance(value, bool):
            return '1' if value else '0'
        if isinstance(value, (int, float)):
            return str(value)
        if value is None:
            return 'NULL'
        return "'" + str(value).replace("'", "''") + "'"

    def _apply_db_param(self, cursor, db_param):
        if db_param is None:
            return
        for key, value in db_param.items():
            key = key.strip().strip(';')
            if key.upper().startswith('PRAGMA'):
                if value is None:
                    cursor.execute(key)
                else:
                    cursor.execute(f"{key} = {self._escape_sqlite_literal(value)}")
            else:
                cursor.execute(f"PRAGMA {key} = {self._escape_sqlite_literal(value)}")

    def execute(self, db_name: str, sql: str, db_param=None, emp_flag=False, restart_flag=False):
        sql = normalize_executable_sql(sql)
        if emp_flag:
            db_name = get_empty_db_name(db_name)
        connection, cursor = self.connect(db_name, restart_flag)
        try:
            self._apply_db_param(cursor, db_param)
            cursor.execute('PRAGMA case_sensitive_like = ON')
            cursor.execute(sql)
            if cursor.description:
                rows = cursor.fetchall()
            else:
                rows = None
            connection.commit()
            return True, rows
        except sqlite3.Error as e:
            print(sql)
            connection.rollback()
            traceback.print_exc()
            return False, f"Error while executing SQLite query: {e}"

    def dependent_execute(self, db_name: str, sql: str, db_param=None):
        sql = normalize_executable_sql(sql)
        connection = None
        cursor = None
        try:
            db_file_path = self._get_db_path(db_name)
            db_dir = os.path.dirname(db_file_path)
            if not os.path.exists(db_dir):
                os.mkdir(db_dir)
            connection = sqlite3.connect(db_file_path)
            cursor = connection.cursor()
            self._apply_db_param(cursor, db_param)
            cursor.execute(sql)
            if cursor.description:
                rows = cursor.fetchall()
            else:
                rows = None
            connection.commit()
            return True, rows
        except sqlite3.Error as e:
            print(sql)
            traceback.print_exc()
            return False, f"Error while executing SQLite query: {e}"
        finally:
            try:
                cursor.close()
                connection.close()
            except Exception:
                pass

    def connect(self, db_name: str, restart_flag=False):
        if not restart_flag and db_name in self.conn_map:
            conn = self.conn_map[db_name]
            try:
                conn.execute("SELECT 1")
                return self.conn_map[db_name], self.cursor_map[db_name]
            except sqlite3.Error:
                self.close_connect(db_name)

        db_file_path = self._get_db_path(db_name)
        db_dir = os.path.dirname(db_file_path)
        if not os.path.exists(db_dir):
            os.mkdir(db_dir)

        connection = sqlite3.connect(db_file_path)
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        connection.commit()

        self.conn_map[db_name] = connection
        self.cursor_map[db_name] = cursor
        return connection, cursor

    def close_connect(self, db_name: str):
        connection = self.conn_map.get(db_name)
        cursor = self.cursor_map.get(db_name)
        if connection:
            if cursor:
                cursor.close()
            connection.close()
            self.conn_map.pop(db_name, None)
            self.cursor_map.pop(db_name, None)
            print("SQLite connection is closed")

    def drop_db(self, db_name: str):
        try:
            if db_name in self.conn_map:
                self.close_connect(db_name)
            db_file_path = self._get_db_path(db_name)
            if os.path.exists(db_file_path):
                os.remove(db_file_path)
                print(f"Database '{db_name}' dropped successfully!")
        except OSError as e:
            print(f"Error while dropping SQLite database: {e}")

    def show_databases(self):
        try:
            configured_path = self.config['sqlite_db_path']
            base_dir = os.path.dirname(configured_path)
            configured_stem = os.path.splitext(os.path.basename(configured_path))[0]
            if not os.path.exists(base_dir):
                return [configured_stem]
            db_names = []
            for file_name in os.listdir(base_dir):
                if file_name.endswith('.db') or file_name.endswith('.sqlite'):
                    db_names.append(os.path.splitext(file_name)[0])
            if configured_stem not in db_names:
                db_names.append(configured_stem)
            return sorted(set(db_names))
        except OSError as e:
            print(f"Error while listing SQLite databases: {e}")
            return None

    @staticmethod
    def _normalize_sqlite_identifier(value: str) -> str:
        return value.replace('"', '').replace('`', '').replace('[', '').replace(']', '').strip()

    @staticmethod
    def _find_first_select_stmt(root_node):
        sql_stmt_list_node = root_node.get_child_by_value('sql_stmt_list')
        if sql_stmt_list_node is None:
            return None
        for child in sql_stmt_list_node.children:
            if child.value != 'sql_stmt':
                continue
            select_stmt_node = child.get_child_by_value('select_stmt')
            if select_stmt_node is not None:
                return select_stmt_node
        return None

    @staticmethod
    def _collect_sqlite_table_refs(node, refs: set[str]):
        if node.value == 'table_or_subquery':
            table_name_node = node.get_child_by_value('table_name')
            if table_name_node is not None:
                refs.add(SQLiteDialect._normalize_sqlite_identifier(str(table_name_node)).lower())
        for child in node.children:
            SQLiteDialect._collect_sqlite_table_refs(child, refs)

    @staticmethod
    def _extract_sqlite_ctes(select_stmt_node) -> dict:
        with_clause_node = select_stmt_node.get_child_by_value('with_clause')
        if with_clause_node is None:
            return {
                'is_recursive': False,
                'cte_list': []
            }

        cte_list = []
        for cte_node in with_clause_node.get_children_by_value('common_table_expression'):
            cte_table_name_node = cte_node.get_child_by_value('cte_table_name')
            query_body_node = cte_node.get_child_by_value('select_stmt')
            if cte_table_name_node is None or query_body_node is None:
                continue
            table_name_node = cte_table_name_node.get_child_by_value('table_name')
            if table_name_node is None:
                continue
            cte_name = SQLiteDialect._normalize_sqlite_identifier(str(table_name_node))
            column_nodes = cte_table_name_node.get_children_by_value('column_name')
            column_list = None if len(column_nodes) == 0 else [
                SQLiteDialect._normalize_sqlite_identifier(str(col_node)) for col_node in column_nodes
            ]
            cte_list.append({
                'cte_name': cte_name,
                'query': query_body_node.clone(),
                'column_list': column_list,
            })

        return {
            'is_recursive': with_clause_node.get_child_by_value('RECURSIVE') is not None,
            'cte_list': cte_list
        }

    @staticmethod
    def _resolve_needed_sqlite_ctes(main_select_stmt_node, ctes: dict) -> dict:
        cte_map = {
            cte['cte_name'].lower(): cte
            for cte in ctes['cte_list']
        }
        main_query_node = main_select_stmt_node.clone()
        if main_query_node.get_child_by_value('with_clause') is not None:
            main_query_node.rm_child_by_value('with_clause')

        initial_refs = set()
        SQLiteDialect._collect_sqlite_table_refs(main_query_node, initial_refs)
        needed_names = {
            ref for ref in initial_refs if ref in cte_map
        }

        pending_names = list(needed_names)
        while len(pending_names) > 0:
            cur_name = pending_names.pop()
            cur_cte = cte_map.get(cur_name)
            if cur_cte is None:
                continue
            cte_refs = set()
            SQLiteDialect._collect_sqlite_table_refs(cur_cte['query'], cte_refs)
            for ref in cte_refs:
                if ref in cte_map and ref not in needed_names:
                    needed_names.add(ref)
                    pending_names.append(ref)

        return {
            'is_recursive': ctes['is_recursive'],
            'cte_list': [
                cte for cte in ctes['cte_list']
                if cte['cte_name'].lower() in needed_names
            ]
        }

    @staticmethod
    def _rewrite_select_stmt_with_typeof(select_stmt_node) -> tuple[bool, list[str] | str]:
        select_core_nodes = select_stmt_node.get_children_by_value('select_core')
        if len(select_core_nodes) == 0:
            return False, 'No SELECT core found in SQL statement.'

        first_result_columns = select_core_nodes[0].get_children_by_value('result_column')
        if len(first_result_columns) == 0:
            return False, 'No result columns found in SQL statement.'

        output_columns = []
        internal_aliases = []
        for col_idx, result_column in enumerate(first_result_columns):
            expr_node = result_column.get_child_by_value('expr')
            if expr_node is None:
                return False, 'Wildcard result columns are not supported for SQLite typeof type inference.'
            alias_node = result_column.get_child_by_value('column_alias')
            if alias_node is not None:
                output_col_name = SQLiteDialect._normalize_sqlite_identifier(str(alias_node)).lower()
            else:
                output_col_name = str(expr_node).strip().lower()
            output_columns.append(output_col_name)
            internal_aliases.append(f'__type_col_{col_idx}')

        for select_core in select_core_nodes:
            result_columns = select_core.get_children_by_value('result_column')
            if len(result_columns) != len(output_columns):
                return False, 'Compound SELECT branches have inconsistent column counts.'
            for col_idx, result_column in enumerate(result_columns):
                expr_node = result_column.get_child_by_value('expr')
                if expr_node is None:
                    return False, 'Wildcard result columns are not supported for SQLite typeof type inference.'
                from antlr_parser.Tree import TreeNode
                result_column.children = [
                    TreeNode('typeof', 'sqlite', True),
                    TreeNode('(', 'sqlite', True),
                    expr_node.clone(),
                    TreeNode(')', 'sqlite', True),
                    TreeNode('AS', 'sqlite', True),
                    TreeNode(internal_aliases[col_idx], 'sqlite', True),
                ]

        return True, output_columns

    def get_data_type(self, db_name: str, obj: str, is_table: bool, db_param: dict | None = None) -> tuple[bool, List]:
        if is_table:
            table_name = obj
            with open(os.path.join(get_proj_root_path(), 'data', db_name, 'schema.json'), 'r') as file:
                schema = json.loads(file.read())
            if table_name not in schema:
                raise ValueError(f"Table {table_name} not found in schema")

            res = []
            for col in schema[table_name]['cols']:
                type_def = col.get('type', {})
                col_type = type_def.get('type_name', 'UNKNOWN')
                res.append({
                    "col": col['col'].lower(),
                    "type": col_type
                })
            return True, res

        connection = None
        try:
            # db_name = get_empty_db_name(db_name)
            connection, cursor = self.connect(db_name, restart_flag=True)
            self._apply_db_param(cursor, db_param)
            from antlr_parser.Tree import TreeNode
            from antlr_parser.general_tree_analysis import build_ctes
            from antlr_parser.parse_tree import parse_tree
            tree, line, col, msg = parse_tree(obj.strip().strip(';'), self.name)
            if tree is None:
                return False, [f'SQL parse failed at line {line}, column {col}: {msg}']
            root_node = TreeNode.make_g4_tree_by_node(tree, self.name)
            if root_node is None:
                return False, ['Failed to build parse tree for SQLite SQL.']

            first_select_stmt = self._find_first_select_stmt(root_node)
            if first_select_stmt is None:
                return False, ['No SELECT statement found in SQL.']

            ctes = self._extract_sqlite_ctes(first_select_stmt)
            ctes = self._resolve_needed_sqlite_ctes(first_select_stmt, ctes)

            rewritten_select_stmt = first_select_stmt.clone()
            if rewritten_select_stmt.get_child_by_value('with_clause') is not None:
                rewritten_select_stmt.rm_child_by_value('with_clause')
            ok, rewrite_res = self._rewrite_select_stmt_with_typeof(rewritten_select_stmt)
            if not ok:
                return False, [rewrite_res]
            output_columns = rewrite_res

            with_sql = build_ctes(ctes, self.name)
            rewritten_sql = str(rewritten_select_stmt)
            if with_sql != '':
                rewritten_sql = f'{with_sql} {rewritten_sql}'

            cursor.execute('PRAGMA case_sensitive_like = ON')
            cursor.execute(rewritten_sql.strip().strip(';'))
            rows = cursor.fetchall() if cursor.description else []
            connection.commit()

            type_values = []
            if len(rows) > 0:
                type_values = list(rows[0])

            res = []
            for col_idx, col_name in enumerate(output_columns):
                col_type = 'UNKNOWN'
                if col_idx < len(type_values) and type_values[col_idx] is not None:
                    col_type = str(type_values[col_idx])
                res.append({
                    'col': col_name,
                    'type': col_type
                })
            return True, res
        except sqlite3.Error as e:
            print(obj)
            print(f"Error while executing SQLite query: {e}")
            if connection:
                connection.rollback()
            return False, [f"Error while executing SQLite query: {e}"]

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
                self.drop_db(test_db_name)
                return flag, res
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
            create_stmt += ',\n\t' + f"PRIMARY KEY ({primary_keys})"
        create_stmt += '\n);'
        return create_stmt

    def add_foreign_key(self, schema):
        # TODO: SQLite don't support add foreign key after table created, so we don't implement this function for now
        return []

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
            name = f'"{name}"'
        elif ' ' in name or '-' in name:
            name = f'"{name}"'
        return name

    @staticmethod
    def dump_all_sqlite_keywords(output_path=f'{get_proj_root_path()}/src/utils/sqlite_reserved_keyword.json'):
        # used to get the reserved keyword list of the used sqlite database
        import ctypes
        import ctypes.util

        libname = ctypes.util.find_library("sqlite3")
        if not libname:
            raise RuntimeError("找不到 sqlite3 动态库")

        lib = ctypes.CDLL(libname)

        lib.sqlite3_keyword_count.argtypes = []
        lib.sqlite3_keyword_count.restype = ctypes.c_int

        lib.sqlite3_keyword_name.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.sqlite3_keyword_name.restype = ctypes.c_int
        def all_sqlite_keywords():
            count = lib.sqlite3_keyword_count()
            result = []

            for i in range(count):
                z = ctypes.c_char_p()
                l = ctypes.c_int()
                rc = lib.sqlite3_keyword_name(i, ctypes.byref(z), ctypes.byref(l))
                if rc != 0:
                    continue
                result.append(ctypes.string_at(z, l.value).decode("utf-8"))
            return result
        with open(output_path, 'w') as f:
            json.dump(all_sqlite_keywords(), f, indent=4)
