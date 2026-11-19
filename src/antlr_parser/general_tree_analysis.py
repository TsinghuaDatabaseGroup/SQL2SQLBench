# -*- coding: utf-8 -*-
# @Project: SQL2SQL_Bench
# @Module: general_tree_analysis$

# @Time: 2025/6/18 16:53
import json
import os

from antlr_parser.Tree import TreeNode
from antlr_parser.mysql_tree import fetch_all_simple_select_from_select_stmt_mysql, rename_column_mysql, \
    fetch_main_select_from_select_stmt_mysql
from antlr_parser.oracle_tree import fetch_all_simple_select_from_subquery_oracle
from antlr_parser.parse_tree import parse_tree
from antlr_parser.pg_tree import get_pg_main_select_node_from_select_stmt, fetch_all_simple_select_from_select_stmt_pg
from antlr_parser.snowflake_tree import fetch_all_simple_select_from_query_stmt_snowflake
from sql_gen.generator.ele_type.type_def import OptionType
from utils.tools import get_proj_root_path
from dialects.dialect_tools import get_table_col_name

with open(os.path.join(get_proj_root_path(), 'src',
                       'antlr_parser', 'aggr_funcs.json'), 'r') as file:
    aggregate_functions = json.load(file)


def _sqlite_func_arg_count(func_expr: str) -> int:
    """Count top-level arguments in a SQLite function expression string."""
    left = func_expr.find('(')
    right = func_expr.rfind(')')
    if left == -1 or right == -1 or right <= left:
        return 0
    args = func_expr[left + 1:right].strip()
    if args == '':
        return 0
    depth = 0
    count = 1
    i = 0
    while i < len(args):
        ch = args[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            count += 1
        i += 1
    return count


def inside_aggregate_function(dialect, tree_node: TreeNode):
    if dialect == 'mysql':
        while tree_node is not None and tree_node.value != 'selectStatement':
            if tree_node.value == 'overClause':
                return False
            if (tree_node.value == 'functionCall' or
                    tree_node.value == 'specificFunction' or tree_node.value == 'aggregateWindowedFunction'
                    or tree_node.value == 'nonAggregateWindowedFunction'):
                if tree_node.get_child_by_value('overClause') is not None:
                    return False
                string = str(tree_node).upper().strip()
                val = string[:string.find('(')].strip()
                for value in aggregate_functions[dialect]:
                    if value.lower() == val.lower():
                        return True
            tree_node = tree_node.father
        return False
    elif dialect == 'pg':
        while tree_node is not None and tree_node.value != 'simple_select_pramary':
            if tree_node.value == 'over_clause':
                return False
            if tree_node.value == 'func_expr' or (tree_node.value == 'func_application'
                                                  and tree_node.father is None):
                string = str(tree_node).upper().strip()
                val = string[:string.find('(')].strip()
                for value in aggregate_functions[dialect]:
                    if value.lower() == val.lower():
                        return True
            tree_node = tree_node.father
        return False
    elif dialect == 'oracle':
        while tree_node is not None and tree_node.value != 'query_block':
            if tree_node.value == 'keep_clause' or tree_node.value == 'over_clause':
                return True
            if (tree_node.value == 'standard_function' or tree_node.value == 'string_function'
                    or tree_node.value == 'numeric_function_wrapper' or tree_node.value == 'json_function'
                    or tree_node.value == 'other_function' or tree_node.value == 'general_element_part'):
                string = str(tree_node).upper().strip()
                val = string[:string.find('(')].strip()
                for value in aggregate_functions[dialect]:
                    if value.lower() == val.lower():
                        return True
            tree_node = tree_node.father
        return False
    elif dialect == 'snowflake':
        while tree_node is not None and tree_node.value != 'query_statement':
            if tree_node.value == 'over_clause':
                return False
            if tree_node.value in ['function_call', 'round_expr', 'ranking_windowed_function', 'aggregate_function']:
                string = str(tree_node).upper().strip()
                val = string[:string.find('(')].strip()
                for value in aggregate_functions[dialect]:
                    if value.lower() == val.lower():
                        return True
            tree_node = tree_node.father
        return False
    elif dialect == 'sqlserver':
        while tree_node is not None and tree_node.value != 'select_statement':
            if tree_node.value == 'over_clause':
                return False
            if tree_node.value in ['function_call', 'ranking_windowed_function', 'aggregate_windowed_function',
                                   'analytic_windowed_function', 'built_in_functions',
                                   'freetext_function', 'partition_function', 'hierarchyid_static_method']:
                string = str(tree_node).upper().strip()
                val = string[:string.find('(')].strip()
                for value in aggregate_functions[dialect]:
                    if value.lower() == val.lower():
                        return True
            tree_node = tree_node.father
        return False
    elif dialect == 'sqlite':
        while tree_node is not None and tree_node.value != 'select_stmt':
            if tree_node.value == 'over_clause':
                return False
            if tree_node.value == 'expr_recursive':
                string = str(tree_node).upper().strip()
                val = string[:string.find('(')].strip()
                for value in aggregate_functions[dialect]:
                    if value.lower() == val.lower():
                        # SQLite MAX/MIN are scalar when called with >= 2 args.
                        if val in ['MAX', 'MIN'] and _sqlite_func_arg_count(string) > 1:
                            return False
                        return True
            tree_node = tree_node.father
        return False
    else:
        assert False


def father_value_list_compare(root_node: TreeNode, father_list: list[str | list]) -> bool:
    now_father = root_node.father
    for father in father_list:
        if isinstance(father, list):
            if now_father is None:
                return False
            else:
                flag = False
                for possible_father in father:
                    if now_father.value.lower() == possible_father.lower():
                        flag = True
                        break
                if not flag:
                    return False
        else:
            if now_father is None or now_father.value.lower() != father.lower():
                return False
        now_father = now_father.father
    return True


def child_value_list_compare(root_node: TreeNode, child_list: list[str]) -> bool:
    now_child = root_node
    for child in child_list:
        if len(now_child.children) == 0:
            return False
        now_child = now_child.children[0]
        if isinstance(child, list):
            flag = False
            for possible_child in child:
                if now_child.value.lower() == possible_child.lower():
                    flag = True
                    break
            if not flag:
                return False
        else:
            if now_child.value.lower() != child.lower():
                return False
    return True


def in_oracle_column_table_name_path(root_node: TreeNode) -> bool:
    if (father_value_list_compare(root_node, ['id_expression', 'general_element_part']) and
            not child_value_list_compare(root_node,
                                         ['non_reserved_keywords_pre12c',
                                          ['NULLIF', 'SYSDATE', "ROWNUM", "TRUNC", "GROUPING", "CURRENT_TIMESTAMP",
                                           "CURRENT_DATE"]])):
        return True
    elif father_value_list_compare(root_node, ['regular_id', 'id_expression', 'identifier',
                                               'tableview_name', 'dml_table_expression_clause',
                                               'table_ref_aux_internal',
                                               'table_ref_aux', 'table_ref']) and not root_node.value == 'dual':
        return True
    elif father_value_list_compare(root_node,
                                   ['id_expression', 'identifier', 'tableview_name']) and not child_value_list_compare(
        root_node, ['dual']):
        return True
    elif father_value_list_compare(root_node, ['id_expression', 'table_element']):
        return True
    elif father_value_list_compare(root_node, ['id_expression', 'tableview_name']):
        return True
    elif father_value_list_compare(root_node, ['id_expression', 'identifier', 'table_alias']):
        return True
    elif father_value_list_compare(root_node, ['id_expression', 'identifier', 'query_name']):
        return True
    elif father_value_list_compare(root_node, ['id_expression', 'identifier', 'column_alias']):
        return True
    elif father_value_list_compare(root_node, ['qualified_name', 'relation_expr']):
        return True
    return False


def in_pg_column_table_name_path(root_node: TreeNode) -> bool:
    if father_value_list_compare(root_node, ['colid', 'columnref']):
        return True
    elif father_value_list_compare(root_node, ['collabel', 'attr_name']):
        return True
    elif father_value_list_compare(root_node, ['collabel', 'target_el']):
        return True
    elif father_value_list_compare(root_node, ['table_alias']):
        return True
    elif father_value_list_compare(root_node, ['qualified_name', 'relation_expr']):
        return True
    else:
        return False


def in_mysql_column_table_name_path(root_node: TreeNode) -> bool:
    if father_value_list_compare(root_node, ['uid', 'tableSourceItem']):
        return True
    elif (father_value_list_compare(root_node, ['uid', 'fullId'])
          and not father_value_list_compare(root_node, ['uid', 'fullId', 'functionCall'])):
        return True
    # elif father_value_list_compare(root_node, ['stringLiteral', 'constant']):
    #     return True
    elif father_value_list_compare(root_node, ['uid', 'simpleId', 'cteName']):
        return True
    elif father_value_list_compare(root_node, ['uid', 'fullColumnName']):
        if len(root_node.children) != 0 and root_node.children[0].value == 'scalarFunctionName':
            if str(root_node.children[0]).upper() in ['CURRENT_TIMESTAMP', 'LOCALTIME', 'LOCALTIMESTAMP', 'SYSDATE',
                                                      'UTC_TIMESTAMP', 'UTC_DATE', 'UTC_TIME',
                                                      'CURRENT_DATE', 'CURRENT_TIME', 'CURTIME']:
                return False
        return True
    elif father_value_list_compare(root_node, ['uid', 'cteName', 'commonTableExpression']):
        return True
    elif father_value_list_compare(root_node, ['qualified_name', 'relation_expr']):
        return True
    elif father_value_list_compare(root_node, ['uid', 'selectElement']):
        return True
    return False


def in_sqlite_column_table_name_path(root_node: TreeNode) -> bool:
    if father_value_list_compare(root_node, ['any_name', 'name', 'type_name']):
        return False
    if father_value_list_compare(root_node, ['any_name']):
        return True
    elif father_value_list_compare(root_node, ['any_name_excluding_string']):
        return True
    elif father_value_list_compare(root_node, ['any_name_excluding_joins']):
        return True
    return False


def in_snowflake_column_table_name_path(root_node: TreeNode) -> bool:
    if (father_value_list_compare(root_node, ['id_']) and
            not root_node.value in ['builtin_function', 'unary_or_binary_builtin_function',
                                    'binary_builtin_function', 'binary_or_ternary_builtin_function',
                                    'ternary_builtin_function']):
        return True
    return False


def in_sqlserver_column_table_name_path(root_node: TreeNode) -> bool:
    if father_value_list_compare(root_node, ['id_', 'common_table_expression']):
        return True
    if father_value_list_compare(root_node, ['id_', 'full_table_name']):
        return True
    if father_value_list_compare(root_node, ['id_', 'full_column_name']):
        return True
    if father_value_list_compare(root_node, ['id_', 'column_alias']):
        return True
    if father_value_list_compare(root_node, ['id_', 'table_alias']):
        return True
    return False


def fetch_all_uppermost_subquery_in_select_stmt(select_stmt_node: TreeNode, dialect: str):
    res = []
    if dialect == 'mysql':
        if select_stmt_node.value == 'fromClause':
            if select_stmt_node.get_child_by_value('expression') is not None:
                return fetch_all_uppermost_subquery_in_select_stmt(select_stmt_node.get_child_by_value('expression'),
                                                                   dialect)
        if select_stmt_node.value == 'querySpecification' or select_stmt_node.value == 'querySpecificationNointo':
            return [select_stmt_node]
    elif dialect == 'pg':
        if select_stmt_node.value == 'from_clause':
            return []
        if select_stmt_node.value == 'simple_select_pramary':
            return [select_stmt_node]
    elif dialect == 'oracle':
        if select_stmt_node.value == 'from_clause':
            return []
        if select_stmt_node.value == 'query_block':
            return [select_stmt_node]
    elif dialect == 'sqlserver':
        if select_stmt_node.value == 'table_sources':
            return []
        if select_stmt_node.value == 'query_specification':
            return [select_stmt_node]
    elif dialect == 'snowflake':
        if select_stmt_node.value == 'from_clause':
            return []
        if select_stmt_node.value == 'select_statement':
            return [select_stmt_node]
    elif dialect == 'sqlite':
        if select_stmt_node.value == 'join_clause':
            return []
        if select_stmt_node.value == 'select_core':
            return [select_stmt_node]
    else:
        assert False
    for node in select_stmt_node.children:
        res = res + fetch_all_uppermost_subquery_in_select_stmt(node, dialect)
    return res


def dfs_table_ref_node(table_ref_node: TreeNode):
    res = [table_ref_node]
    if len(table_ref_node.get_children_by_value('table_ref')) > 0:
        for child in table_ref_node.get_children_by_value('table_ref'):
            res += dfs_table_ref_node(child)
    else:
        res.append(table_ref_node)
    return res


def analyze_select_stmt_used_tables(select_stmt_node: TreeNode, cte_names: list[list], dialect):
    res = set()
    cur_layer_tables = []
    if dialect == 'mysql':
        from_clause_node = select_stmt_node.get_child_by_value('fromClause')
        if from_clause_node is not None:
            table_source_nodes = from_clause_node.get_children_by_path(['tableSources', 'tableSource'])
            table_source_items = []
            for table_source_node in table_source_nodes:
                table_source_item_node = table_source_node.get_child_by_value('tableSourceItem')
                table_source_items.append(table_source_item_node)
                assert table_source_item_node is not None
                join_part_nodes = table_source_node.get_children_by_value('joinPart')
                for join_part_node in join_part_nodes:
                    table_source_item_node = join_part_node.get_child_by_value('tableSourceItem')
                    table_source_items.append(table_source_item_node)
            for table_source_item_node in table_source_items:
                if table_source_item_node.get_child_by_value('tableSources') is not None:
                    assert False
                if table_source_item_node.get_child_by_value('dmlStatement') is not None:
                    if table_source_item_node.get_child_by_value('LATERAL') is not None:
                        cte_names.append(cur_layer_tables)
                    query_body_node = table_source_item_node.get_child_by_value('dmlStatement')
                    select_statement_node = query_body_node.get_child_by_value('selectStatement')
                    select_stmts = fetch_all_simple_select_from_select_stmt_mysql(select_statement_node)
                    for simple_select_stmt_node in select_stmts:
                        select_res = analyze_select_stmt_used_tables(simple_select_stmt_node, cte_names, dialect)
                        for tbl in select_res:
                            res.add(tbl)
                    if table_source_item_node.get_child_by_value('LATERAL') is not None:
                        cte_names.remove(cur_layer_tables)
                    if table_source_item_node.get_child_by_value('uid') is not None:
                        name = str(table_source_item_node.get_child_by_value('uid')).strip('`')
                        cur_layer_tables.append(name)
                else:
                    assert table_source_item_node.get_child_by_value('tableName') is not None
                    name = str(table_source_item_node.get_child_by_value('tableName'))
                    name = name.strip('`')
                    if not find_in_stack(cte_names, name):
                        res.add(name)
                    if table_source_item_node.get_child_by_value('uid') is not None:
                        name = str(table_source_item_node.get_child_by_value('uid')).strip('`')
                    cur_layer_tables.append(name)
    elif dialect == 'pg':
        from_clause_node = select_stmt_node.get_child_by_value('from_clause')
        if from_clause_node is not None:
            assert isinstance(from_clause_node, TreeNode)
            table_ref_nodes = from_clause_node.get_children_by_path(['from_list', 'table_ref'])
            all_table_ref_nodes = []
            for table_ref_node in table_ref_nodes:
                all_table_ref_nodes += dfs_table_ref_node(table_ref_node)
            for table_ref_node in all_table_ref_nodes:
                if table_ref_node.get_child_by_value('relation_expr') is not None:
                    name = str(table_ref_node.get_child_by_value('relation_expr')).strip('"').strip('[').strip(']')
                    if not find_in_stack(cte_names, name):
                        res.add(name)
                    if table_ref_node.get_child_by_value('opt_alias_clause') is not None:
                        alias_name = table_ref_node.get_children_by_path(
                            ['opt_alias_clause', 'table_alias_clause', 'table_alias'])
                        assert len(alias_name) > 0
                        name = str(alias_name[0]).strip('"').strip('[').strip(']')
                    cur_layer_tables.append(name)
                elif table_ref_node.get_child_by_value('select_with_parens') is not None:
                    if table_ref_node.get_child_by_value('LATERAL') is not None:
                        cte_names.append(cur_layer_tables)
                    select_stmt_nodes = fetch_all_simple_select_from_select_stmt_pg(
                        table_ref_node.get_child_by_value('select_with_parens'))
                    for simple_select_stmt_node in select_stmt_nodes:
                        select_res = analyze_select_stmt_used_tables(simple_select_stmt_node, cte_names, dialect)
                        for tbl in select_res:
                            res.add(tbl)
                    if table_ref_node.get_child_by_value('LATERAL') is not None:
                        cte_names.remove(cur_layer_tables)
                    if table_ref_node.get_child_by_value('opt_alias_clause') is not None:
                        alias_name = table_ref_node.get_children_by_path(
                            ['opt_alias_clause', 'table_alias_clause', 'table_alias'])
                        assert len(alias_name) > 0
                        name = str(alias_name[0]).strip('"').strip('[').strip(']')
                        cur_layer_tables.append(name)
    elif dialect == 'oracle':
        from_clause_node = select_stmt_node.get_child_by_value('from_clause')
        if from_clause_node is not None:
            assert isinstance(from_clause_node, TreeNode)
            table_ref_nodes = from_clause_node.get_children_by_path(['table_ref_list', 'table_ref'])
            all_table_ref_aux_nodes = []
            for table_ref_node in table_ref_nodes:
                table_ref_aux_node = table_ref_node.get_child_by_value('table_ref_aux')
                assert table_ref_aux_node is not None
                all_table_ref_aux_nodes.append(table_ref_aux_node)
                for join_clause in table_ref_node.get_children_by_value('join_clause'):
                    table_ref_aux_node = join_clause.get_child_by_value('table_ref_aux')
                    assert table_ref_aux_node is not None
                    all_table_ref_aux_nodes.append(table_ref_aux_node)
            for table_ref_aux_node in all_table_ref_aux_nodes:
                table_ref_aux_internal_node = table_ref_aux_node.get_child_by_value('table_ref_aux_internal')
                assert table_ref_aux_internal_node is not None
                assert table_ref_aux_internal_node.get_child_by_value('table_ref_aux_internal') is None
                dml_table_expression_clause_node = table_ref_aux_internal_node.get_child_by_value(
                    'dml_table_expression_clause')
                if dml_table_expression_clause_node.get_child_by_value('tableview_name') is not None:
                    name = str(dml_table_expression_clause_node.get_child_by_value('tableview_name')).strip('"')
                    if not find_in_stack(cte_names, name):
                        # print(cte_names)
                        # print(name)
                        res.add(name)
                elif dml_table_expression_clause_node.get_child_by_value('select_statement') is not None:
                    subquery_node = dml_table_expression_clause_node.get_children_by_path(['select_statement',
                                                                                           'select_only_statement',
                                                                                           'subquery'])
                    assert len(subquery_node) == 1
                    subquery_node = subquery_node[0]
                    simple_select_nodes = fetch_all_simple_select_from_subquery_oracle(subquery_node)
                    for simple_select_node in simple_select_nodes:
                        select_res = analyze_select_stmt_used_tables(simple_select_node, cte_names, dialect)
                        for tbl in select_res:
                            res.add(tbl)
                    name = None
                elif dml_table_expression_clause_node.get_child_by_value('subquery') is not None:
                    subquery_node = dml_table_expression_clause_node.get_child_by_value('subquery')
                    if dml_table_expression_clause_node.get_child_by_value('LATERAL') is not None:
                        cte_names.append(cur_layer_tables)
                    simple_select_nodes = fetch_all_simple_select_from_subquery_oracle(subquery_node)
                    for simple_select_node in simple_select_nodes:
                        select_res = analyze_select_stmt_used_tables(simple_select_node, cte_names, dialect)
                        for tbl in select_res:
                            res.add(tbl)
                    if dml_table_expression_clause_node.get_child_by_value('LATERAL') is not None:
                        cte_names.remove(cur_layer_tables)
                    name = None
                else:
                    continue
                alias_node = table_ref_aux_node.get_child_by_value('table_alias')
                if alias_node is not None:
                    name = str(alias_node).strip('"')
                if name is not None:
                    cur_layer_tables.append(name)
    elif dialect == 'snowflake':
        from_clause_node = select_stmt_node.get_children_by_path(['select_optional_clauses', 'from_clause'])
        if len(from_clause_node) > 0:
            from_clause_node = from_clause_node[0]
        else:
            from_clause_node = None
        if from_clause_node is not None:
            def collect_snowflake_object_refs(joined_node: TreeNode, output_items: list[TreeNode]):
                if joined_node is None:
                    return

                base_object_ref = joined_node.get_child_by_value('object_ref')
                if base_object_ref is not None:
                    output_items.append(base_object_ref)

                for join_clause_node in joined_node.get_children_by_value('join_clause'):
                    join_object_ref = join_clause_node.get_child_by_value('object_ref')
                    if join_object_ref is not None:
                        output_items.append(join_object_ref)

                nested_joined_node = joined_node.get_child_by_value('table_source_item_joined')
                if nested_joined_node is not None:
                    collect_snowflake_object_refs(nested_joined_node, output_items)

            table_source_nodes = from_clause_node.get_children_by_path(['table_sources', 'table_source'])
            table_source_items = []
            for table_source_node in table_source_nodes:
                table_source_item_node = table_source_node.get_child_by_value('table_source_item_joined')
                if table_source_item_node is not None:
                    collect_snowflake_object_refs(table_source_item_node, table_source_items)
                else:
                    direct_object_ref = table_source_node.get_child_by_value('object_ref')
                    if direct_object_ref is not None:
                        table_source_items.append(direct_object_ref)
            for table_source_item_node in table_source_items:
                if table_source_item_node.get_child_by_value('subquery') is not None:
                    if table_source_item_node.get_child_by_value('LATERAL') is not None:
                        cte_names.append(cur_layer_tables)
                    query_body_node = table_source_item_node.get_child_by_value('subquery')
                    select_stmts = fetch_all_simple_select_from_query_stmt_snowflake(query_body_node.get_child_by_value('query_statement'))
                    for simple_select_stmt_node in select_stmts:
                        select_res = analyze_select_stmt_used_tables(simple_select_stmt_node, cte_names, dialect)
                        for tbl in select_res:
                            res.add(tbl)
                    if table_source_item_node.get_child_by_value('LATERAL') is not None:
                        cte_names.remove(cur_layer_tables)
                    if table_source_item_node.get_child_by_value('uid') is not None:
                        name = str(table_source_item_node.get_child_by_value('uid')).strip('`')
                        cur_layer_tables.append(name)
                else:
                    assert table_source_item_node.get_child_by_value('object_name') is not None
                    name = str(table_source_item_node.get_child_by_value('object_name'))
                    name = name.strip('"')
                    if not find_in_stack(cte_names, name):
                        res.add(name)
                    if table_source_item_node.get_child_by_value('as_alias') is not None:
                        alias_node = table_source_item_node.get_child_by_value('as_alias')
                        alias_name = alias_node.get_child_by_value('alias')
                        name = str(alias_name).strip('"')
                    cur_layer_tables.append(name)
    elif dialect == 'sqlite':
        def normalize_sqlite_identifier(value: str) -> str:
            return value.replace('"', '').replace('`', '').replace('[', '').replace(']', '').strip()

        join_clause_node = select_stmt_node.get_child_by_value('join_clause')
        if join_clause_node is not None:
            table_or_subquery_nodes = []
            pending_join_clause_nodes = [join_clause_node]
            while len(pending_join_clause_nodes) > 0:
                cur_join_clause_node = pending_join_clause_nodes.pop()
                for table_or_subquery_node in cur_join_clause_node.get_children_by_value('table_or_subquery'):
                    table_or_subquery_nodes.append(table_or_subquery_node)
                    nested_join_clause_node = table_or_subquery_node.get_child_by_value('join_clause')
                    if nested_join_clause_node is not None:
                        pending_join_clause_nodes.append(nested_join_clause_node)

            for table_or_subquery_node in table_or_subquery_nodes:
                table_name_node = table_or_subquery_node.get_child_by_value('table_name')
                if table_name_node is not None:
                    name = normalize_sqlite_identifier(str(table_name_node))
                    if not find_in_stack(cte_names, name):
                        res.add(name)
                    alias_node = table_or_subquery_node.get_child_by_value('table_alias')
                    if alias_node is None:
                        alias_node = table_or_subquery_node.get_child_by_value('table_alias_excluding_joins')
                    if alias_node is not None:
                        cur_layer_tables.append(normalize_sqlite_identifier(str(alias_node)))
                    else:
                        cur_layer_tables.append(name)
                    continue

                select_stmt_subquery_node = table_or_subquery_node.get_child_by_value('select_stmt')
                if select_stmt_subquery_node is not None:
                    simple_select_nodes = fetch_all_uppermost_subquery_in_select_stmt(select_stmt_subquery_node,
                                                                                       dialect)
                    for simple_select_node in simple_select_nodes:
                        select_res = analyze_select_stmt_used_tables(simple_select_node, cte_names, dialect)
                        for tbl in select_res:
                            res.add(tbl)
                    alias_node = table_or_subquery_node.get_child_by_value('table_alias')
                    if alias_node is not None:
                        cur_layer_tables.append(normalize_sqlite_identifier(str(alias_node)))
    elif dialect == 'sqlserver':
        def normalize_sqlserver_identifier(value: str) -> str:
            return value.replace('"', '').replace('`', '').replace('[', '').replace(']', '').strip()

        def add_table_source_item(table_source_item_node: TreeNode):
            full_table_name_node = table_source_item_node.get_child_by_value('full_table_name')
            if full_table_name_node is not None:
                name = normalize_sqlserver_identifier(str(full_table_name_node))
                if not find_in_stack(cte_names, name):
                    res.add(name)
                alias_node = table_source_item_node.get_children_by_path(['as_table_alias', 'table_alias'])
                if len(alias_node) > 0:
                    cur_layer_tables.append(normalize_sqlserver_identifier(str(alias_node[0])))
                else:
                    cur_layer_tables.append(name)
                return

            # In SQL Server grammar, reserved words such as USER can be parsed as built-in
            # function_call in table_source_item. Treat bare (no parentheses) calls as table names.
            function_call_node = table_source_item_node.get_child_by_value('function_call')
            if function_call_node is not None:
                name = normalize_sqlserver_identifier(str(function_call_node))
                if '(' not in name and ')' not in name:
                    if not find_in_stack(cte_names, name):
                        res.add(name)
                    alias_node = table_source_item_node.get_children_by_path(['as_table_alias', 'table_alias'])
                    if len(alias_node) > 0:
                        cur_layer_tables.append(normalize_sqlserver_identifier(str(alias_node[0])))
                    else:
                        cur_layer_tables.append(name)
                return

            derived_table_node = table_source_item_node.get_child_by_value('derived_table')
            if derived_table_node is not None:
                for subquery_node in derived_table_node.get_children_by_value('subquery'):
                    select_stmt_subquery_node = subquery_node.get_child_by_value('select_statement')
                    if select_stmt_subquery_node is None:
                        continue
                    simple_select_nodes = fetch_all_uppermost_subquery_in_select_stmt(select_stmt_subquery_node,
                                                                                       dialect)
                    for simple_select_node in simple_select_nodes:
                        select_res = analyze_select_stmt_used_tables(simple_select_node, cte_names, dialect)
                        for tbl in select_res:
                            res.add(tbl)
                alias_node = table_source_item_node.get_children_by_path(['as_table_alias', 'table_alias'])
                if len(alias_node) > 0:
                    cur_layer_tables.append(normalize_sqlserver_identifier(str(alias_node[0])))
                return

        from_clause_node = select_stmt_node.get_child_by_value('table_sources')
        if from_clause_node is not None:
            table_source_nodes = from_clause_node.get_children_by_value('table_source')
            table_source_nodes += from_clause_node.get_children_by_path(['non_ansi_join', 'table_source'])
            pending_table_source_nodes = list(table_source_nodes)
            while len(pending_table_source_nodes) > 0:
                table_source_node = pending_table_source_nodes.pop()
                table_source_item_node = table_source_node.get_child_by_value('table_source_item')
                if table_source_item_node is not None:
                    add_table_source_item(table_source_item_node)
                    nested_table_source_node = table_source_item_node.get_child_by_value('table_source')
                    if nested_table_source_node is not None:
                        pending_table_source_nodes.append(nested_table_source_node)
                for join_part_node in table_source_node.get_children_by_value('join_part'):
                    join_on_node = join_part_node.get_child_by_value('join_on')
                    if join_on_node is not None:
                        join_table_source_node = join_on_node.get_child_by_value('table_source')
                        if join_table_source_node is not None:
                            pending_table_source_nodes.append(join_table_source_node)
                        continue
                    cross_join_node = join_part_node.get_child_by_value('cross_join')
                    if cross_join_node is not None:
                        cross_table_source_node = cross_join_node.get_child_by_value('table_source')
                        if cross_table_source_node is not None:
                            pending_table_source_nodes.append(cross_table_source_node)
                        continue
                    apply_node = join_part_node.get_child_by_value('apply_')
                    if apply_node is not None:
                        apply_table_source_node = apply_node.get_child_by_value('table_source')
                        if apply_table_source_node is not None:
                            pending_table_source_nodes.append(apply_table_source_node)
    else:
        assert False
    to_dfs_select_stmt_nodes = []
    for child in select_stmt_node.children:
        to_dfs_select_stmt_nodes = to_dfs_select_stmt_nodes + fetch_all_uppermost_subquery_in_select_stmt(child,
                                                                                                          dialect)
    for select_stmt_node in to_dfs_select_stmt_nodes:
        res = res.union(analyze_select_stmt_used_tables(select_stmt_node, cte_names, dialect))
    return res


def find_in_stack(stack: list[list], value):
    for i in range(len(stack)):
        if value in stack[i]:
            return True
    return False


def add_to_stack(stack: list[list], value):
    assert len(stack) > 0
    stack[-1].append(value)


def fetch_all_table_in_sql(sql: str, dialect):
    # we do not allow using with statement in subquery
    root_node, _, _, _ = parse_tree(sql, dialect)
    if root_node is None:
        return None
    root_node = TreeNode.make_g4_tree_by_node(root_node, dialect)

    def normalize_identifier(value: str) -> str:
        return value.replace('`', '').replace('"', '').replace('[', '').replace(']', '').strip()

    def extract_identifier_from_node(node: TreeNode, candidates: list[str]) -> str | None:
        for value in candidates:
            child = node.get_child_by_value(value)
            if child is not None:
                return normalize_identifier(str(child))
        if node.get_child_by_value('id_') is not None:
            return normalize_identifier(str(node.get_child_by_value('id_')))
        return None

    # use stack
    derived_tables = [[]]
    used_tables_set = set()
    if dialect == 'mysql':
        with_stmt_node = root_node.get_children_by_path(
            ['sqlStatements', 'sqlStatement', 'dmlStatement', 'withStatement'])
        if len(with_stmt_node) != 0:
            assert len(with_stmt_node) == 1
            with_stmt_node = with_stmt_node[0]
            common_table_expressions = with_stmt_node.get_children_by_value('commonTableExpression')
            for cte_root_node in common_table_expressions:
                cte_name = str(cte_root_node.get_child_by_value('cteName')).strip('`')
                query_body_node = cte_root_node.get_child_by_value('dmlStatement')
                select_stmt_node = query_body_node.get_child_by_value('selectStatement')
                select_stmts = fetch_all_simple_select_from_select_stmt_mysql(select_stmt_node)
                add_to_stack(derived_tables, cte_name)
                for select_stmt_node in select_stmts:
                    res = analyze_select_stmt_used_tables(select_stmt_node, derived_tables, dialect)
                    for tbl in res:
                        used_tables_set.add(tbl)
        select_statement_node = root_node.get_children_by_path(['sqlStatements', 'sqlStatement',
                                                                'dmlStatement', 'selectStatement'])
        assert len(select_statement_node) == 1
        select_statement_node = select_statement_node[0]
        select_stmts = fetch_all_simple_select_from_select_stmt_mysql(select_statement_node)
        for select_stmt_nodes in select_stmts:
            res = analyze_select_stmt_used_tables(select_stmt_nodes, derived_tables, dialect)
            for tbl in res:
                used_tables_set.add(tbl)
    elif dialect == 'pg':
        select_stmt_node = root_node.get_children_by_path(['stmtblock', 'stmtmulti', 'stmt', 'selectstmt'])
        assert len(select_stmt_node) == 1
        select_stmt_node = select_stmt_node[0]
        select_main_node = get_pg_main_select_node_from_select_stmt(select_stmt_node)
        with_clause_node = select_main_node.get_child_by_value('with_clause')
        if with_clause_node is not None:
            cte_nodes = with_clause_node.get_children_by_path(['cte_list', 'common_table_expr'])
            for cte_node in cte_nodes:
                cte_name = str(cte_node.get_child_by_value('name')).strip('"')
                query_body_node = cte_node.get_children_by_path(['preparablestmt', 'selectstmt'])
                assert len(query_body_node) == 1
                query_body_node = query_body_node[0]
                simple_select_nodes = fetch_all_simple_select_from_select_stmt_pg(query_body_node)
                add_to_stack(derived_tables, cte_name)
                for simple_select_node in simple_select_nodes:
                    res = analyze_select_stmt_used_tables(simple_select_node, derived_tables, dialect)
                    for tbl in res:
                        used_tables_set.add(tbl)
        simple_select_nodes = fetch_all_simple_select_from_select_stmt_pg(select_stmt_node)
        for simple_select_node in simple_select_nodes:
            res = analyze_select_stmt_used_tables(simple_select_node, derived_tables, dialect)
            for tbl in res:
                used_tables_set.add(tbl)
    elif dialect == 'oracle':
        select_stmt_node = root_node.get_children_by_path(['unit_statement', 'data_manipulation_language_statements',
                                                           'select_statement', 'select_only_statement'])
        assert len(select_stmt_node) == 1
        select_stmt_node = select_stmt_node[0]
        with_clause_node = select_stmt_node.get_child_by_value('with_clause')
        if with_clause_node is not None:
            cte_nodes = with_clause_node.get_children_by_value('with_factoring_clause')
            for cte_node in cte_nodes:
                query_factoring_clause_node = cte_node.get_child_by_value('subquery_factoring_clause')
                query_body_node = query_factoring_clause_node.get_child_by_value('subquery')
                cte_name = str(query_factoring_clause_node.get_child_by_value('query_name')).strip('"')
                simple_select_nodes = fetch_all_simple_select_from_subquery_oracle(query_body_node)
                add_to_stack(derived_tables, cte_name)
                for simple_select_node in simple_select_nodes:
                    res = analyze_select_stmt_used_tables(simple_select_node, derived_tables, dialect)
                    for tbl in res:
                        used_tables_set.add(tbl)
        subquery_node = root_node.get_children_by_path(['unit_statement', 'data_manipulation_language_statements',
                                                        'select_statement', 'select_only_statement', 'subquery'])
        if len(subquery_node) != 1:
            print('FOR UPDATE haven\'t been supported yet')
            assert False
        select_stmt_node = subquery_node[0]
        simple_select_nodes = fetch_all_simple_select_from_subquery_oracle(select_stmt_node)
        for simple_select_node in simple_select_nodes:
            res = analyze_select_stmt_used_tables(simple_select_node, derived_tables, dialect)
            for tbl in res:
                used_tables_set.add(tbl)
    elif dialect == 'sqlite':
        select_stmt_nodes = root_node.get_children_by_path(['sql_stmt_list', 'sql_stmt', 'select_stmt'])
        assert len(select_stmt_nodes) == 1
        select_stmt_node = select_stmt_nodes[0]

        with_clause_node = select_stmt_node.get_child_by_value('with_clause')
        if with_clause_node is not None:
            cte_nodes = with_clause_node.get_children_by_value('common_table_expression')
            for cte_node in cte_nodes:
                cte_name = extract_identifier_from_node(cte_node, ['cte_table_name', 'table_name'])
                query_body_node = cte_node.get_child_by_value('select_stmt')
                if cte_name is not None:
                    add_to_stack(derived_tables, cte_name)
                if query_body_node is not None:
                    simple_select_nodes = fetch_all_uppermost_subquery_in_select_stmt(query_body_node, dialect)
                    for simple_select_node in simple_select_nodes:
                        res = analyze_select_stmt_used_tables(simple_select_node, derived_tables, dialect)
                        for tbl in res:
                            used_tables_set.add(tbl)

        simple_select_nodes = fetch_all_uppermost_subquery_in_select_stmt(select_stmt_node, dialect)
        for simple_select_node in simple_select_nodes:
            res = analyze_select_stmt_used_tables(simple_select_node, derived_tables, dialect)
            for tbl in res:
                used_tables_set.add(tbl)
    elif dialect == 'snowflake':
        query_statement_nodes = root_node.get_node_until('query_statement')
        assert len(query_statement_nodes) > 0
        query_statement_node = query_statement_nodes[0]

        with_expression_node = query_statement_node.get_child_by_value('with_expression')
        if with_expression_node is not None:
            cte_nodes = with_expression_node.get_children_by_value('common_table_expression')
            for cte_node in cte_nodes:
                cte_name = extract_identifier_from_node(cte_node, ['id_'])
                query_body_node = cte_node.get_child_by_value('select_statement_in_parentheses')
                simple_select_nodes = fetch_all_simple_select_from_query_stmt_snowflake(query_body_node)
                if cte_name is not None:
                    add_to_stack(derived_tables, cte_name)
                for simple_select_node in simple_select_nodes:
                    res = analyze_select_stmt_used_tables(simple_select_node, derived_tables, dialect)
                    for tbl in res:
                        used_tables_set.add(tbl)
        simple_select_nodes = fetch_all_simple_select_from_query_stmt_snowflake(query_statement_node)
        for simple_select_node in simple_select_nodes:
            res = analyze_select_stmt_used_tables(simple_select_node, derived_tables, dialect)
            for tbl in res:
                used_tables_set.add(tbl)
    elif dialect == 'sqlserver':
        select_statement_nodes = root_node.get_node_until('select_statement_standalone')
        assert len(select_statement_nodes) > 0
        select_statement_node = select_statement_nodes[0]

        with_expression_node = select_statement_node.get_child_by_value('with_expression')
        if with_expression_node is not None:
            cte_nodes = with_expression_node.get_children_by_value('common_table_expression')
            for cte_node in cte_nodes:
                cte_name = extract_identifier_from_node(cte_node, ['id_'])
                query_body_node = cte_node.get_child_by_value('select_statement')
                if cte_name is not None:
                    add_to_stack(derived_tables, cte_name)
                if query_body_node is not None:
                    simple_select_nodes = fetch_all_uppermost_subquery_in_select_stmt(query_body_node, dialect)
                    for simple_select_node in simple_select_nodes:
                        res = analyze_select_stmt_used_tables(simple_select_node, derived_tables, dialect)
                        for tbl in res:
                            used_tables_set.add(tbl)

        simple_select_nodes = fetch_all_uppermost_subquery_in_select_stmt(select_statement_node.get_child_by_value('select_statement'), dialect)
        for simple_select_node in simple_select_nodes:
            res = analyze_select_stmt_used_tables(simple_select_node, derived_tables, dialect)
            for tbl in res:
                used_tables_set.add(tbl)
    else:
        assert False
    return used_tables_set


def fetch_query_body_node(root_node: TreeNode, dialect: str) -> TreeNode:
    if dialect == 'oracle':
        main_node = root_node.get_children_by_path(['unit_statement', 'data_manipulation_language_statements',
                                                    'select_statement'])
        assert len(main_node) == 1
        main_node = main_node[0]
        select_only_node = main_node.get_child_by_value('select_only_statement')
        assert select_only_node is not None
        if select_only_node.get_child_by_value('with_clause') is not None:
            select_only_node.rm_child_by_value('with_clause')
    elif dialect == 'mysql':
        main_node = root_node.get_children_by_path(['sqlStatements', 'sqlStatement',
                                                    'dmlStatement', 'selectStatement'])
        assert len(main_node) == 1
        main_node = main_node[0]
    elif dialect == 'pg':
        main_node = root_node.get_children_by_path(['stmtblock', 'stmtmulti',
                                                    'stmt', 'selectstmt', 'select_no_parens'])
        assert len(main_node) == 1
        main_node = main_node[0]
        if main_node.get_child_by_value('with_clause') is not None:
            main_node.rm_child_by_value('with_clause')
    elif dialect == 'sqlserver':
        standalone_nodes = root_node.get_node_until('select_statement_standalone')
        assert len(standalone_nodes) > 0
        standalone_node = standalone_nodes[0]
        if standalone_node.get_child_by_value('with_expression') is not None:
            standalone_node.rm_child_by_value('with_expression')
        main_node = standalone_node.get_child_by_value('select_statement')
        assert main_node is not None
    elif dialect == 'sqlite':
        main_node = root_node.get_children_by_path(['sql_stmt_list', 'sql_stmt', 'select_stmt'])
        assert len(main_node) == 1
        main_node = main_node[0]
        if main_node.get_child_by_value('with_clause') is not None:
            main_node.rm_child_by_value('with_clause')
    elif dialect == 'snowflake':
        query_statement_nodes = root_node.get_node_until('query_statement')
        assert len(query_statement_nodes) > 0
        main_node = query_statement_nodes[0]
        if main_node.get_child_by_value('with_expression') is not None:
            main_node.rm_child_by_value('with_expression')
    else:
        assert False
    return main_node


def build_ctes(ctes: dict, dialect: str):
    if len(ctes['cte_list']) == 0:
        return ''
    if dialect == 'oracle':
        with_clauses = 'WITH '
        for cte in ctes['cte_list']:
            if 'search_clause' not in cte or cte['search_clause'] is None:
                search_clause = ''
            else:
                search_clause = cte['search_clause']
            if 'cycle_clause' not in cte or cte['cycle_clause'] is None:
                cycle_clause = ''
            else:
                cycle_clause = cte['cycle_clause']
            if cte['column_list'] is None:
                cte_str = (f'{get_table_col_name(cte["cte_name"], dialect)} AS ({str(cte["query"])}) '
                           f'{search_clause} {cycle_clause}')
            else:
                cols = ''
                for col in cte['column_list']:
                    if cols != '':
                        cols += ', '
                    cols += f'{get_table_col_name(col, dialect)}'
                cte_str = f'{cte["cte_name"]} ({cols}) AS ({str(cte["query"])}) {search_clause} {cycle_clause}'
            if with_clauses == 'WITH ':
                with_clauses += cte_str
            else:
                with_clauses += f',\n {cte_str}'
    else:
        with_clauses = 'WITH '
        if ctes['is_recursive']:
            with_clauses = 'WITH RECURSIVE '
        for cte in ctes['cte_list']:
            if cte['column_list'] is None:
                cte_str = f'{get_table_col_name(cte["cte_name"], dialect)} AS ({str(cte["query"])})'
            else:
                cols = ''
                for col in cte['column_list']:
                    if cols != '':
                        cols += ', '
                    cols += get_table_col_name(col, dialect)
                cte_str = f'{get_table_col_name(cte["cte_name"], dialect)} ({cols}) AS ({str(cte["query"])})'
            if with_clauses == 'WITH ' or with_clauses == 'WITH RECURSIVE ':
                with_clauses += cte_str
            else:
                with_clauses += f',\n {cte_str}'
    return with_clauses


def fetch_all_ctes(root_node: TreeNode, dialect: str) -> tuple[bool, dict]:
    cte_list = []
    is_recursive = False

    def normalize_identifier(value: str) -> str:
        return value.replace('`', '').replace('"', '').replace('[', '').replace(']', '').strip()

    def deduplicate_alias_nodes(alias_nodes: list[TreeNode], strip_chars: str) -> list[str] | None:
        if len(alias_nodes) == 0:
            return None
        rename_dict = {}
        column_list = []
        for col_node in alias_nodes:
            col_name = str(col_node).strip(strip_chars)
            if col_name in rename_dict:
                new_name = f"{col_name}_{rename_dict[col_name]}"
                assert len(col_node.children) == 1
                assert isinstance(col_node, TreeNode)
                col_node.children[0].value = new_name
                rename_dict[col_name] = rename_dict[col_name] + 1
                col_node.children[0].is_terminal = True
            else:
                new_name = col_name
                rename_dict[col_name] = 1
            column_list.append(new_name)
        return column_list

    if dialect == 'mysql':
        with_stmt_node = root_node.get_children_by_path(
            ['sqlStatements', 'sqlStatement', 'dmlStatement', 'withStatement'])
        if len(with_stmt_node) == 0:
            # No cte
            return True, {
                "is_recursive": False,
                "cte_list": []
            }
        assert len(with_stmt_node) == 1
        with_stmt_node = with_stmt_node[0]
        if with_stmt_node.get_child_by_value('RECURSIVE') is not None:
            is_recursive = True
        common_table_expressions = with_stmt_node.get_children_by_value('commonTableExpression')
        for cte_root_node in common_table_expressions:
            cte_name = str(cte_root_node.get_child_by_value('cteName')).strip('`')
            query_body_node = cte_root_node.get_children_by_path(
                ['dmlStatement', 'selectStatement'])
            assert len(query_body_node) == 1
            query_body_node = query_body_node[0]
            alias_nodes = cte_root_node.get_children_by_value('cteColumnName')
            column_list = deduplicate_alias_nodes(alias_nodes, '`')
            cte_list.append({
                'cte_name': cte_name,
                'query': query_body_node,
                'column_list': column_list,
            })
        return True, {
            "is_recursive": is_recursive,
            "cte_list": cte_list
        }
    elif dialect == 'pg':
        select_stmt_node = root_node.get_children_by_path(['stmtblock', 'stmtmulti', 'stmt', 'selectstmt'])
        assert len(select_stmt_node) == 1
        select_stmt_node = select_stmt_node[0]
        select_main_node = get_pg_main_select_node_from_select_stmt(select_stmt_node)
        with_clause_node = select_main_node.get_child_by_value('with_clause')
        if with_clause_node is None:
            return True, {
                "is_recursive": False,
                "cte_list": []
            }
        if with_clause_node.get_child_by_value('RECURSIVE') is not None:
            is_recursive = True
        cte_nodes = with_clause_node.get_children_by_path(['cte_list', 'common_table_expr'])
        for cte_node in cte_nodes:
            cte_name = str(cte_node.get_child_by_value('name')).strip('"')
            query_body_node = cte_node.get_children_by_path(['preparablestmt', 'selectstmt'])
            assert len(query_body_node) == 1
            query_body_node = query_body_node[0]
            alias_nodes = cte_node.get_children_by_path(['opt_name_list', 'name_list', 'name'])
            column_list = deduplicate_alias_nodes(alias_nodes, '"')
            cte_list.append(
                {
                    'cte_name': cte_name,
                    'query': query_body_node,
                    'column_list': column_list
                }
            )
        return True, {
            "is_recursive": is_recursive,
            "cte_list": cte_list
        }
    elif dialect == 'sqlserver':
        select_statement_nodes = root_node.get_node_until('select_statement_standalone')
        assert len(select_statement_nodes) > 0
        select_statement_node = select_statement_nodes[0]

        with_expression_node = select_statement_node.get_child_by_value('with_expression')
        if with_expression_node is None:
            return True, {
                "is_recursive": False,
                "cte_list": []
            }

        cte_nodes = with_expression_node.get_children_by_value('common_table_expression')
        for cte_node in cte_nodes:
            cte_name_node = cte_node.get_child_by_value('id_')
            assert cte_name_node is not None
            cte_name = normalize_identifier(str(cte_name_node))

            query_body_node = cte_node.get_child_by_value('select_statement')
            assert query_body_node is not None

            alias_nodes = []
            column_name_list_node = cte_node.get_child_by_value('column_name_list')
            if column_name_list_node is not None:
                alias_nodes = column_name_list_node.get_node_until('id_')
            column_list = deduplicate_alias_nodes(alias_nodes, '"`[]')

            cte_list.append(
                {
                    'cte_name': cte_name,
                    'query': query_body_node,
                    'column_list': column_list
                }
            )
        return True, {
            "is_recursive": False,
            "cte_list": cte_list
        }
    elif dialect == 'sqlite':
        select_stmt_nodes = root_node.get_children_by_path(['sql_stmt_list', 'sql_stmt', 'select_stmt'])
        assert len(select_stmt_nodes) == 1
        select_stmt_node = select_stmt_nodes[0]

        with_clause_node = select_stmt_node.get_child_by_value('with_clause')
        if with_clause_node is None:
            return True, {
                "is_recursive": False,
                "cte_list": []
            }

        if with_clause_node.get_child_by_value('RECURSIVE') is not None:
            is_recursive = True

        cte_nodes = with_clause_node.get_children_by_value('common_table_expression')
        for cte_node in cte_nodes:
            cte_name_nodes = cte_node.get_children_by_path(['cte_table_name', 'table_name'])
            assert len(cte_name_nodes) == 1
            cte_name = normalize_identifier(str(cte_name_nodes[0]))

            query_body_node = cte_node.get_child_by_value('select_stmt')
            assert query_body_node is not None

            alias_nodes = cte_node.get_children_by_path(['cte_table_name', 'column_name'])
            column_list = deduplicate_alias_nodes(alias_nodes, '"`[]')

            cte_list.append(
                {
                    'cte_name': cte_name,
                    'query': query_body_node,
                    'column_list': column_list
                }
            )
        return True, {
            "is_recursive": is_recursive,
            "cte_list": cte_list
        }
    elif dialect == 'snowflake':
        query_statement_nodes = root_node.get_node_until('query_statement')
        assert len(query_statement_nodes) > 0
        query_statement_node = query_statement_nodes[0]

        with_expression_node = query_statement_node.get_child_by_value('with_expression')
        if with_expression_node is None:
            return True, {
                "is_recursive": False,
                "cte_list": []
            }

        if with_expression_node.get_child_by_value('RECURSIVE') is not None:
            is_recursive = True

        cte_nodes = with_expression_node.get_children_by_value('common_table_expression')
        for cte_node in cte_nodes:
            cte_name_node = cte_node.get_child_by_value('id_')
            assert cte_name_node is not None
            cte_name = normalize_identifier(str(cte_name_node))

            query_body_node = cte_node.get_child_by_value('select_statement_in_parentheses')
            assert query_body_node is not None

            alias_nodes = cte_node.get_children_by_path(['column_list', 'column_name'])
            if len(alias_nodes) == 0:
                alias_nodes = cte_node.get_children_by_path(['column_list', 'id_'])
            column_list = deduplicate_alias_nodes(alias_nodes, '"`[]')

            cte_list.append(
                {
                    'cte_name': cte_name,
                    'query': query_body_node,
                    'column_list': column_list
                }
            )
        return True, {
            "is_recursive": is_recursive,
            "cte_list": cte_list
        }
    elif dialect == 'oracle':
        select_stmt_node = root_node.get_children_by_path(['unit_statement', 'data_manipulation_language_statements',
                                                           'select_statement', 'select_only_statement'])
        assert len(select_stmt_node) == 1
        select_stmt_node = select_stmt_node[0]
        with_clause_node = select_stmt_node.get_child_by_value('with_clause')
        if with_clause_node is None:
            return True, {
                "is_recursive": False,
                "cte_list": []
            }
        cte_nodes = with_clause_node.get_children_by_value('with_factoring_clause')
        for cte_node in cte_nodes:
            assert cte_node.get_child_by_value('subquery_factoring_clause') is not None
            query_factoring_clause_node = cte_node.get_child_by_value('subquery_factoring_clause')
            query_body_node = query_factoring_clause_node.get_child_by_value('subquery')
            search_clause = query_factoring_clause_node.get_child_by_value('search_clause')
            cycle_clause = query_factoring_clause_node.get_child_by_value('cycle_clause')
            if search_clause is not None:
                search_clause = str(search_clause)
            if cycle_clause is not None:
                cycle_clause = str(cycle_clause)
            cte_name = str(query_factoring_clause_node.get_child_by_value('query_name')).strip('"')
            column_list = None
            if query_factoring_clause_node.get_child_by_value('paren_column_list') is not None:
                column_alias_list_node = (query_factoring_clause_node.get_child_by_value('paren_column_list').
                                          get_child_by_value('column_list'))
                alias_nodes = column_alias_list_node.get_children_by_value('column_name')
                column_list = deduplicate_alias_nodes(alias_nodes, '"')
            cte_list.append({
                'cte_name': cte_name,
                'query': query_body_node,
                'column_list': column_list,
                'search_clause': search_clause,
                'cycle_clause': cycle_clause
            })
        return True, {
            "is_recursive": is_recursive,
            "cte_list": cte_list
        }
    else:
        assert False

