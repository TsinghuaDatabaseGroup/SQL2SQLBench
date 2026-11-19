# -*- coding: utf-8 -*-
# @Project: SQL2SQL_Bench
# @Module: fetch_operand_type$

# @Time: 2025/5/17 12:56
from antlr_parser.Tree import TreeNode
from antlr_parser.general_tree_analysis import in_mysql_column_table_name_path, in_pg_column_table_name_path, \
    in_oracle_column_table_name_path, in_sqlite_column_table_name_path, in_snowflake_column_table_name_path, \
    in_sqlserver_column_table_name_path
from antlr_parser.mysql_tree import fetch_main_select_from_select_stmt_mysql
from antlr_parser.oracle_tree import fetch_main_select_from_subquery_oracle
from antlr_parser.pg_tree import fetch_main_select_from_select_stmt_pg
from antlr_parser.sqlite_tree import fetch_main_select_from_select_stmt_sqlite
from antlr_parser.snowflake_tree import fetch_main_select_from_query_statement_snowflake
from antlr_parser.sqlserver_tree import fetch_main_select_from_select_statement_standalone_sqlserver
from sql_gen.generator.ele_type.type_conversion import type_mapping
from sql_gen.generator.ele_type.type_def import BoolType, IntervalType, NumberType, StringGeneralType, BlobType, \
    NullType, IntType, TimestampType, DateType
from utils.ExecutionEnv import ExecutionEnv


def fetch_with_ctes(selectStatement: TreeNode, dialect: str):
    cur_node = selectStatement.father
    ctes = []
    cte_node_place = None
    if dialect == 'mysql':
        while cur_node is not None:
            assert isinstance(cur_node, TreeNode)
            if cur_node.value == 'commonTableExpression':
                cte_node_place = cur_node
            temp_cte_nodes = cur_node.get_children_by_path(['sqlStatement', 'dmlStatement',
                                                            'withStatement', 'commonTableExpression'])
            #     with_stmt_nodes = cur_node.get_children_by_path(['sqlStatement', 'dmlStatement',
            #                                                      'withStatement'])
            #     print(len(with_stmt_nodes))
            #     if len(with_stmt_nodes) > 0:
            #         if len(with_stmt_nodes[0].get_children_by_path(['withStatement', 'commonTableExpression'])) == 0:
            #             temp_cte_nodes = []
            #     ctes = temp_cte_nodes + ctes
            # else:
            #     temp_cte_nodes = cur_node.get_children_by_path(['dmlStatement', 'withStatement',
            #                                                     'commonTableExpression'])
            #     ctes = temp_cte_nodes + ctes
            if len(temp_cte_nodes) > 0:
                ctes = temp_cte_nodes + ctes
                break
            child_node = cur_node
            cur_node = cur_node.father
    elif dialect == 'pg':
        while cur_node is not None:
            assert isinstance(cur_node, TreeNode)
            if cur_node.value == 'common_table_expr':
                cte_node_place = cur_node
            with_stmt_nodes = cur_node.get_children_by_path(['with_clause', 'cte_list', 'common_table_expr'])
            ctes = with_stmt_nodes + ctes
            cur_node = cur_node.father
    elif dialect == 'oracle':
        while cur_node is not None:
            assert isinstance(cur_node, TreeNode)
            if cur_node.value == 'with_factoring_clause':
                cte_node_place = cur_node
            with_stmt_nodes = cur_node.get_children_by_path(['with_clause', 'with_factoring_clause'])
            ctes = with_stmt_nodes + ctes
            cur_node = cur_node.father
    elif dialect == 'sqlite':
        while cur_node is not None:
            assert isinstance(cur_node, TreeNode)
            if cur_node.value == 'common_table_expression':
                cte_node_place = cur_node
            with_stmt_nodes = cur_node.get_children_by_path(['with_clause', 'common_table_expression'])
            ctes = with_stmt_nodes + ctes
            cur_node = cur_node.father
    elif dialect == 'snowflake':
        while cur_node is not None:
            assert isinstance(cur_node, TreeNode)
            if cur_node.value == 'common_table_expression':
                cte_node_place = cur_node
            with_stmt_nodes = cur_node.get_children_by_path(['with_expression', 'common_table_expression'])
            ctes = with_stmt_nodes + ctes
            cur_node = cur_node.father
    elif dialect == 'sqlserver':
        while cur_node is not None:
            assert isinstance(cur_node, TreeNode)
            if cur_node.value == 'common_table_expression':
                cte_node_place = cur_node
            with_stmt_nodes = cur_node.get_children_by_path(['with_expression', 'common_table_expression'])
            ctes = with_stmt_nodes + ctes
            cur_node = cur_node.father
    if cte_node_place is None:
        return ctes
    res = []
    for cte in ctes:
        if cte != cte_node_place:
            res.append(cte)
        else:
            break
    return res


def have_only_one_child_path_to(ori_node: TreeNode, tgt_node_name: str) -> TreeNode | None:
    temp_node = ori_node
    while True:
        used_name = temp_node.value
        if temp_node.is_terminal and temp_node.terminal_node_name is not None:
            used_name = temp_node.terminal_node_name
        if used_name == tgt_node_name:
            return temp_node
        if len(temp_node.children) != 1:
            return None
        temp_node = temp_node.children[0]


def try_get_constant_type(operand: TreeNode, dialect: str):
    if dialect == 'mysql':
        if have_only_one_child_path_to(operand, 'decimalLiteral') is not None:
            return NumberType()
        elif have_only_one_child_path_to(operand, 'stringLiteral') is not None:
            return StringGeneralType()
        elif have_only_one_child_path_to(operand, 'hexadecimalLiteral') is not None:
            return BlobType()
        elif have_only_one_child_path_to(operand, 'booleanLiteral') is not None:
            return BoolType()
        elif have_only_one_child_path_to(operand, 'REAL_LITERAL') is not None:
            return NumberType()
        elif have_only_one_child_path_to(operand, 'BIT_STRING') is not None:
            return BlobType()
        elif have_only_one_child_path_to(operand, 'constant') is not None:
            node = have_only_one_child_path_to(operand, 'constant')
            if node.get_child_by_value('decimalLiteral') is not None:
                return NumberType()
            if node.get_child_by_value('NULL') is not None:
                return NullType()
        only_node = have_only_one_child_path_to(operand, 'expressionAtom')
        if only_node is None:
            return None
        else:
            if only_node.get_child_by_value('intervalType') is not None:
                return IntervalType()
    elif dialect == 'pg':
        if have_only_one_child_path_to(operand, 'iconst') is not None:
            return IntType()
        elif have_only_one_child_path_to(operand, 'fconst') is not None:
            return NumberType()
        elif have_only_one_child_path_to(operand, 'sconst') is not None:
            return StringGeneralType()
        elif have_only_one_child_path_to(operand, 'bconst') is not None:
            return BlobType()
        elif have_only_one_child_path_to(operand, 'xconst') is not None:
            return BlobType()
        elif have_only_one_child_path_to(operand, 'TRUE_P') is not None:
            return BoolType()
        elif have_only_one_child_path_to(operand, 'FALSE_P') is not None:
            return BoolType()
        elif have_only_one_child_path_to(operand, 'NULL_P') is not None:
            return NullType()
        else:
            if have_only_one_child_path_to(operand, 'aexprconst') is not None:
                aexprconst_node = have_only_one_child_path_to(operand, 'aexprconst')
                if aexprconst_node.get_child_by_value('constinterval') is not None:
                    return IntervalType()
                elif aexprconst_node.get_child_by_value('consttypename') is not None:
                    type_name = str(aexprconst_node.get_child_by_value('consttypename'))
                    return type_mapping('pg', type_name.lower())
    elif dialect == 'sqlite':
        literal_node = have_only_one_child_path_to(operand, 'literal_value')
        if literal_node is not None:
            if literal_node.get_child_by_terminal('NUMERIC_LITERAL') is not None:
                return NumberType()
            if literal_node.get_child_by_terminal('STRING_LITERAL') is not None:
                return StringGeneralType()
            if literal_node.get_child_by_terminal('BLOB_LITERAL') is not None:
                return BlobType()
            if literal_node.get_child_by_terminal('NULL_') is not None:
                return NullType()
            if literal_node.get_child_by_terminal('TRUE_') is not None or literal_node.get_child_by_terminal('FALSE_') is not None:
                return BoolType()
            if literal_node.get_child_by_terminal('CURRENT_DATE_') is not None:
                return DateType()
            if (literal_node.get_child_by_terminal('CURRENT_TIMESTAMP_') is not None or
                    literal_node.get_child_by_terminal('CURRENT_TIME_') is not None):
                return TimestampType()
    elif dialect == 'snowflake':
        literal_node = have_only_one_child_path_to(operand, 'literal')
        if literal_node is not None:
            if literal_node.get_child_by_terminal('STRING') is not None:
                return StringGeneralType()
            if (literal_node.get_child_by_terminal('DECIMAL') is not None or
                    literal_node.get_child_by_terminal('REAL') is not None or
                    literal_node.get_child_by_terminal('FLOAT') is not None):
                return NumberType()
            if literal_node.get_child_by_terminal('NULL_') is not None:
                return NullType()
            if literal_node.get_child_by_value('true_false') is not None:
                return BoolType()
    elif dialect == 'sqlserver':
        primitive_constant_node = have_only_one_child_path_to(operand, 'primitive_constant')
        if primitive_constant_node is not None:
            if primitive_constant_node.get_child_by_terminal('STRING') is not None:
                return StringGeneralType()
            if primitive_constant_node.get_child_by_terminal('BINARY') is not None:
                return BlobType()
            if (primitive_constant_node.get_child_by_terminal('DECIMAL') is not None or
                    primitive_constant_node.get_child_by_terminal('REAL') is not None or
                    primitive_constant_node.get_child_by_terminal('FLOAT') is not None):
                return NumberType()
        primitive_expr_node = have_only_one_child_path_to(operand, 'primitive_expression')
        if primitive_expr_node is not None and primitive_expr_node.get_child_by_value('NULL_') is not None:
            return NullType()
    else:
        assert dialect == 'oracle'
        if have_only_one_child_path_to(operand, 'relational_expression') is not None:
            if operand.value == 'relational_expression':
                relational_expression_node = operand
            else:
                while operand.get_child_by_value('relational_expression') is None:
                    operand = operand.children[0]
                relational_expression_node = operand.get_child_by_value('relational_expression')
            if relational_expression_node.get_child_by_value('relational_operator') is not None:
                return BoolType()
            else:
                if relational_expression_node.get_child_by_value('compound_expression') is not None:
                    compound_expression_node = relational_expression_node.get_child_by_value('compound_expression')
                    if (compound_expression_node.get_child_by_value('IN') is not None or
                            compound_expression_node.get_child_by_value('BETWEEN') is not None or
                            compound_expression_node.get_child_by_value('LIKE') is not None):
                        return BoolType()

        if have_only_one_child_path_to(operand, 'quoted_string'):
            return StringGeneralType()
        if have_only_one_child_path_to(operand, 'numeric'):
            return NumberType()
        if have_only_one_child_path_to(operand, 'constant'):
            constant_node = have_only_one_child_path_to(operand, 'constant')
            if constant_node.get_child_by_value('TIMESTAMP') is not None:
                return TimestampType()
            elif constant_node.get_child_by_value('INTERVAL') is not None:
                return IntervalType()
            elif constant_node.get_child_by_value('DATE') is not None:
                return DateType()
            elif constant_node.get_child_by_value('NULL_') is not None:
                return NullType()
            elif constant_node.get_child_by_value('TRUE') is not None:
                return BoolType()
            elif constant_node.get_child_by_value('FALSE') is not None:
                return BoolType()
    return None


def fetch_all_cols_in_op(operand: TreeNode, dialect: str):
    if dialect == 'mysql':
        if operand.value == 'fullColumnName':
            return [operand]
        elif in_mysql_column_table_name_path(operand):
            return [operand]
    elif dialect == 'pg':
        if operand.value == 'columnref':
            if operand.get_child_by_value('indirection') is not None:
                indirection_node = operand.get_child_by_value('indirection')
                indirection_el_nodes = indirection_node.get_children_by_value('indirection_el')
                for indirection_el_node in indirection_el_nodes:
                    return [operand]
        elif in_pg_column_table_name_path(operand):
            return [operand]
    elif dialect == 'sqlite':
        # SQLite qualified columns are parsed in expr_base as (schema_name DOT)? table_name DOT column_name.
        if operand.value == 'expr_base':
            has_dot = (operand.get_child_by_value('DOT') is not None or
                       operand.get_child_by_value('.') is not None)
            if (operand.get_child_by_value('table_name') is not None and
                    operand.get_child_by_value('column_name') is not None and
                    has_dot):
                return [operand]
        elif operand.value == 'column_name_excluding_string':
            return [operand]
        elif in_sqlite_column_table_name_path(operand):
            return [operand]
    elif dialect == 'snowflake':
        if operand.value == 'primitive_expression':
            if len(operand.get_children_by_value('id_')) > 0:
                return [operand]
        if operand.value == 'full_column_name':
            return [operand]
        elif operand.value == 'column_elem':
            return [operand]
        elif in_snowflake_column_table_name_path(operand):
            return [operand]
    elif dialect == 'sqlserver':
        if operand.value == 'full_column_name':
            return [operand]
        elif in_sqlserver_column_table_name_path(operand):
            return [operand]
    else:
        assert dialect == 'oracle'
        if operand.value == 'general_element':
            if operand.get_child_by_value('.') is not None:
                return [operand]
        elif in_oracle_column_table_name_path(operand):
            return [operand]
    res = []
    for child in operand.children:
        res = res + fetch_all_cols_in_op(child, dialect)
    return res


def fetch_operand_type(operand: TreeNode, execution_env: ExecutionEnv):
    # specially process order by, because the cols used in order by can alias,
    # e.g. analyze the type SELECT a AS b FROM tbl ORDER BY b
    new_operand_node = TreeNode(str(operand), operand.dialect, True)
    order_by_mode = False
    constant_type = try_get_constant_type(operand, execution_env.dialect)
    cols_in_op = fetch_all_cols_in_op(operand, execution_env.dialect)
    if len(cols_in_op) > 0:
        new_group_by_clause = "GROUP BY " + ','.join(str(col) for col in cols_in_op)
    else:
        new_group_by_clause = ''
    if constant_type is not None:
        return constant_type
    if execution_env.dialect == 'mysql':
        if operand.value == 'predicate':
            if not (len(operand.children) == 1 and operand.children[0].value == 'expressionAtom'):
                return BoolType()
        while len(operand.children) == 1:
            operand = operand.children[0]
            if operand.value == 'predicate':
                if not (len(operand.children) == 1 and operand.children[0].value == 'expressionAtom'):
                    return BoolType()
        father_node = operand
        sql_root_node = None
        while father_node is not None:
            if father_node.value == 'orderByClause':
                order_by_mode = True
            if order_by_mode and father_node.value in ['queryExpressionNointo', 'queryExpression', 'selectStatement']:
                sql_root_node = fetch_main_select_from_select_stmt_mysql(father_node)
                break
            elif not order_by_mode:
                if father_node.value == 'querySpecificationNointo':
                    sql_root_node = father_node
                    break
                elif father_node.value == 'querySpecification':
                    sql_root_node = father_node
                    break
            father_node = father_node.father
        assert sql_root_node is not None
        if order_by_mode:
            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            ctes = ''
            if len(with_clauses) > 0:
                ctes = "WITH RECURSIVE "
                for with_clause in with_clauses:
                    if ctes != "WITH RECURSIVE ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
            sql = f"{ctes}SELECT {str(operand)} FROM ({sql_root_node}) AS temp"
            flag, res = execution_env.fetch_type(sql, False)
            if not flag:
                print(sql)
                print(res)
                print("Error in fetching operand type")
            return type_mapping('mysql', res[0]['type'])
        else:
            assert sql_root_node.value == 'querySpecification' or sql_root_node.value == 'querySpecificationNointo'
            ori_select_elements_node = sql_root_node.get_child_by_value('selectElements')
            sql_root_node.replace_child(ori_select_elements_node, new_operand_node)
            # remove order by
            order_by_node = sql_root_node.get_child_by_value('orderByClause')
            if order_by_node is not None:
                empty_node = TreeNode('', execution_env.dialect, True)
                sql_root_node.replace_child(order_by_node, empty_node)
            group_by_flag = False
            if sql_root_node.get_child_by_value('groupByClause') is not None:
                ori_node = sql_root_node.get_child_by_value('groupByClause')
                new_group_by_node = TreeNode(new_group_by_clause, execution_env.dialect, True)
                sql_root_node.replace_child(ori_node, new_group_by_node)
                group_by_flag = True
            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            if len(with_clauses) > 0:
                ctes = "WITH RECURSIVE "
                for with_clause in with_clauses:
                    if ctes != "WITH RECURSIVE ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
                used_sql1 = ctes + str(sql_root_node)
                if group_by_flag:
                    new_group_by_node.value = ''
                used_sql2 = ctes + str(sql_root_node)
            else:
                used_sql1 = str(sql_root_node)
                if group_by_flag:
                    new_group_by_node.value = ''
                used_sql2 = str(sql_root_node)
            if group_by_flag:
                sql_root_node.replace_child(new_group_by_node, ori_node)
            flag, res = execution_env.fetch_type(used_sql1, False)
            if not flag:
                if used_sql1 != used_sql2:
                    flag, res = execution_env.fetch_type(used_sql2, False)
                if not flag:
                    print(used_sql1)
                    print(used_sql2)
                    print("Error in fetching operand type")
            sql_root_node.replace_child(new_operand_node, ori_select_elements_node)
            if order_by_node is not None:
                sql_root_node.replace_child(empty_node, order_by_node)
            return type_mapping('mysql', res[0]['type'])
    elif execution_env.dialect == 'pg':
        father_node = operand
        sql_root_node = None
        while father_node is not None:
            if father_node.value == 'sort_clause':
                order_by_mode = True
            if father_node.value == 'selectstmt':
                sql_root_node = fetch_main_select_from_select_stmt_pg(father_node)
                break
            elif not order_by_mode and father_node.value == 'simple_select_pramary':
                sql_root_node = father_node
                break
            father_node = father_node.father
        assert sql_root_node is not None
        if order_by_mode:
            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            ctes = ''
            if len(with_clauses) > 0:
                ctes = "WITH RECURSIVE "
                for with_clause in with_clauses:
                    if ctes != "WITH RECURSIVE ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
            sql = f"{ctes}SELECT {str(operand)} FROM ({sql_root_node}) AS temp"
            flag, res = execution_env.fetch_type(sql, False)
            if not flag:
                print(sql)
                print(res)
                print("Error in fetching operand type")
            return type_mapping('pg', res[0]['type'])
        else:
            assert sql_root_node.value == 'simple_select_pramary'
            main_select_node = sql_root_node
            target_list_node = main_select_node.get_child_by_value('opt_target_list')
            if target_list_node is None:
                target_list_node = main_select_node.get_child_by_value('target_list')
            main_select_node.replace_child(target_list_node, new_operand_node)
            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            group_by_flag = False
            if main_select_node.get_child_by_value('group_clause') is not None:
                ori_node = main_select_node.get_child_by_value('group_clause')
                new_group_by_node = TreeNode(new_group_by_clause, execution_env.dialect, True)
                main_select_node.replace_child(ori_node, new_group_by_node)
                group_by_flag = True
            if len(with_clauses) > 0:
                ctes = "WITH RECURSIVE "
                for with_clause in with_clauses:
                    if ctes != "WITH RECURSIVE ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
                used_sql1 = ctes + str(main_select_node)
                if group_by_flag:
                    new_group_by_node.value = ''
                used_sql2 = ctes + str(main_select_node)
            else:
                used_sql1 = str(main_select_node)
                if group_by_flag:
                    new_group_by_node.value = ''
                used_sql2 = str(main_select_node)
            if group_by_flag:
                main_select_node.replace_child(new_group_by_node, ori_node)
            flag, res = execution_env.fetch_type(used_sql1, False)
            if not flag:
                if used_sql1 != used_sql2:
                    flag, res = execution_env.fetch_type(used_sql2, False)
                if not flag:
                    print(used_sql1)
                    print(used_sql2)
                    print(res)
                    print("Error in fetching operand type")
            main_select_node.replace_child(new_operand_node, target_list_node)
            return type_mapping('pg', res[0]['type'])
    elif execution_env.dialect == 'sqlite':
        father_node = operand
        sql_root_node = None
        while father_node is not None:
            if father_node.value == 'order_clause':
                order_by_mode = True
            if order_by_mode and father_node.value == 'select_stmt':
                sql_root_node = fetch_main_select_from_select_stmt_sqlite(father_node)
                break
            elif not order_by_mode and father_node.value == 'select_core':
                sql_root_node = father_node
                break
            father_node = father_node.father
        assert sql_root_node is not None
        if order_by_mode:
            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            ctes = ''
            if len(with_clauses) > 0:
                ctes = "WITH RECURSIVE "
                for with_clause in with_clauses:
                    if ctes != "WITH RECURSIVE ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
            sql = f"{ctes}SELECT {str(operand)} FROM ({sql_root_node}) AS temp"
            flag, res = execution_env.fetch_type(sql, False)
            if not flag:
                print(sql)
                print(res)
                print("Error in fetching operand type")
            return type_mapping('sqlite', res[0]['type'])
        else:
            assert sql_root_node.value == 'select_core'
            join_clause_node = sql_root_node.get_child_by_value('join_clause')
            group_by_clause_node = sql_root_node.get_child_by_value('group_clause')
            having_clause_node = sql_root_node.get_child_by_value('having_clause')
            where_expr_node = None
            for idx, child in enumerate(sql_root_node.children):
                if child.value.upper() == 'WHERE' or child.terminal_node_name == 'WHERE_':
                    if idx + 1 < len(sql_root_node.children):
                        next_node = sql_root_node.children[idx + 1]
                        if next_node.value == 'expr':
                            where_expr_node = next_node
                    break
            sql_main = f"SELECT {str(new_operand_node)}"
            if join_clause_node is not None:
                sql_main = sql_main + ' FROM ' + str(join_clause_node)
            if where_expr_node is not None:
                sql_main = sql_main + ' WHERE ' + str(where_expr_node)
            if len(cols_in_op) > 0:
                sql_main = sql_main + ' ' + new_group_by_clause
            elif group_by_clause_node is not None:
                sql_main = sql_main + ' ' + str(group_by_clause_node)
            if having_clause_node is not None:
                sql_main = sql_main + ' ' + str(having_clause_node)

            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            if len(with_clauses) > 0:
                ctes = "WITH RECURSIVE "
                for with_clause in with_clauses:
                    if ctes != "WITH RECURSIVE ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
                used_sql1 = ctes + sql_main
                if group_by_clause_node is not None and len(cols_in_op) > 0:
                    used_sql2 = ctes + sql_main.replace(' ' + new_group_by_clause, ' ' + str(group_by_clause_node), 1)
                else:
                    used_sql2 = used_sql1
            else:
                used_sql1 = sql_main
                if group_by_clause_node is not None and len(cols_in_op) > 0:
                    used_sql2 = sql_main.replace(' ' + new_group_by_clause, ' ' + str(group_by_clause_node), 1)
                else:
                    used_sql2 = used_sql1
            flag, res = execution_env.fetch_type(used_sql1, False)
            if not flag:
                if used_sql1 != used_sql2:
                    flag, res = execution_env.fetch_type(used_sql2, False)
                if not flag:
                    print(used_sql1)
                    print(used_sql2)
                    print(res)
                    print("Error in fetching operand type")
            return type_mapping('sqlite', res[0]['type'])
    elif execution_env.dialect == 'snowflake':
        father_node = operand
        sql_root_node = None
        while father_node is not None:
            if father_node.value == 'order_by_clause':
                order_by_mode = True
            if order_by_mode and father_node.value in ['query_statement', 'select_statement_in_parentheses']:
                sql_root_node = fetch_main_select_from_query_statement_snowflake(father_node)
                break
            elif father_node.value == 'select_statement':
                sql_root_node = father_node
                break
            father_node = father_node.father
        assert sql_root_node is not None
        if order_by_mode:
            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            ctes = ''
            if len(with_clauses) > 0:
                ctes = "WITH RECURSIVE "
                for with_clause in with_clauses:
                    if ctes != "WITH RECURSIVE ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
            sql = f"{ctes}SELECT {str(operand)} FROM ({sql_root_node}) AS temp"
            flag, res = execution_env.fetch_type(sql, False)
            if not flag:
                print(sql)
                print(res)
                print("Error in fetching operand type")
            return type_mapping('snowflake', res[0]['type'])
        else:
            assert sql_root_node.value == 'select_statement'
            select_optional_node = sql_root_node.get_child_by_value('select_optional_clauses')
            from_clause_node = None
            where_clause_node = None
            group_by_clause_node = None
            having_clause_node = None
            qualify_clause_node = None
            if select_optional_node is not None:
                from_clause_node = select_optional_node.get_child_by_value('from_clause')
                where_clause_node = select_optional_node.get_child_by_value('where_clause')
                group_by_clause_node = select_optional_node.get_child_by_value('group_by_clause')
                having_clause_node = select_optional_node.get_child_by_value('having_clause')
                qualify_clause_node = select_optional_node.get_child_by_value('qualify_clause')

            sql_main = f"SELECT {str(new_operand_node)}"
            if from_clause_node is not None:
                sql_main = sql_main + ' ' + str(from_clause_node)
            if where_clause_node is not None:
                sql_main = sql_main + ' ' + str(where_clause_node)
            if len(cols_in_op) > 0:
                sql_main = sql_main + ' ' + new_group_by_clause
            elif group_by_clause_node is not None:
                sql_main = sql_main + ' ' + str(group_by_clause_node)
            if having_clause_node is not None:
                sql_main = sql_main + ' ' + str(having_clause_node)
            if qualify_clause_node is not None:
                sql_main = sql_main + ' ' + str(qualify_clause_node)

            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            if len(with_clauses) > 0:
                ctes = "WITH RECURSIVE "
                for with_clause in with_clauses:
                    if ctes != "WITH RECURSIVE ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
                used_sql1 = ctes + sql_main
                if group_by_clause_node is not None and len(cols_in_op) > 0:
                    used_sql2 = ctes + sql_main.replace(' ' + new_group_by_clause, ' ' + str(group_by_clause_node), 1)
                else:
                    used_sql2 = used_sql1
            else:
                used_sql1 = sql_main
                if group_by_clause_node is not None and len(cols_in_op) > 0:
                    used_sql2 = sql_main.replace(' ' + new_group_by_clause, ' ' + str(group_by_clause_node), 1)
                else:
                    used_sql2 = used_sql1
            flag, res = execution_env.fetch_type(used_sql1, False)
            if not flag:
                if used_sql1 != used_sql2:
                    flag, res = execution_env.fetch_type(used_sql2, False)
                if not flag:
                    print(used_sql1)
                    print(used_sql2)
                    print(res)
                    print("Error in fetching operand type")
            return type_mapping('snowflake', res[0]['type'])
    elif execution_env.dialect == 'sqlserver':
        father_node = operand
        sql_root_node = None
        while father_node is not None:
            if father_node.value in ['order_by_clause', 'select_order_by_clause']:
                order_by_mode = True
            if order_by_mode and father_node.value in ['select_statement_standalone', 'select_statement', 'query_expression']:
                sql_root_node = fetch_main_select_from_select_statement_standalone_sqlserver(father_node)
                break
            elif not order_by_mode and father_node.value == 'query_specification':
                sql_root_node = father_node
                break
            father_node = father_node.father
        assert sql_root_node is not None
        if order_by_mode:
            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            ctes = ''
            if len(with_clauses) > 0:
                ctes = "WITH "
                for with_clause in with_clauses:
                    if ctes != "WITH ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
            sql = f"{ctes}SELECT {str(operand)} FROM ({sql_root_node}) AS temp"
            flag, res = execution_env.fetch_type(sql, False)
            if not flag:
                print(sql)
                print(res)
                print("Error in fetching operand type")
            return type_mapping('sqlserver', res[0]['type'])
        else:
            assert sql_root_node.value == 'query_specification'
            table_sources_node = sql_root_node.get_child_by_value('table_sources')
            search_condition_node = sql_root_node.get_child_by_value('search_condition')
            group_by_clause_node = sql_root_node.get_child_by_value('group_clause')
            having_clause_node = sql_root_node.get_child_by_value('having_clause')
            sql_main = f"SELECT {str(new_operand_node)}"
            if table_sources_node is not None:
                sql_main = sql_main + ' FROM ' + str(table_sources_node)
            if search_condition_node is not None:
                sql_main = sql_main + ' WHERE ' + str(search_condition_node)
            if len(cols_in_op) > 0:
                sql_main = sql_main + ' ' + new_group_by_clause
            elif group_by_clause_node is not None:
                sql_main = sql_main + ' ' + str(group_by_clause_node)
            if having_clause_node is not None:
                sql_main = sql_main + ' ' + str(having_clause_node)

            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            if len(with_clauses) > 0:
                ctes = "WITH "
                for with_clause in with_clauses:
                    if ctes != "WITH ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
                used_sql1 = ctes + sql_main
                if group_by_clause_node is not None and len(cols_in_op) > 0:
                    used_sql2 = ctes + sql_main.replace(' ' + new_group_by_clause, ' ' + str(group_by_clause_node), 1)
                else:
                    used_sql2 = used_sql1
            else:
                used_sql1 = sql_main
                if group_by_clause_node is not None and len(cols_in_op) > 0:
                    used_sql2 = sql_main.replace(' ' + new_group_by_clause, ' ' + str(group_by_clause_node), 1)
                else:
                    used_sql2 = used_sql1
            flag, res = execution_env.fetch_type(used_sql1, False)
            if not flag:
                if used_sql1 != used_sql2:
                    flag, res = execution_env.fetch_type(used_sql2, False)
                if not flag:
                    print(used_sql1)
                    print(used_sql2)
                    print(res)
                    print("Error in fetching operand type")
            return type_mapping('sqlserver', res[0]['type'])
    elif execution_env.dialect == 'oracle':
        father_node = operand
        sql_root_node = None
        while father_node is not None:
            if father_node.value == 'order_by_clause':
                order_by_mode = True
            if father_node.value == 'select_statement':
                select_only_statement_node = father_node.get_child_by_value('select_only_statement')
                assert select_only_statement_node is not None
                subquery_node = select_only_statement_node.get_child_by_value('subquery')
                assert subquery_node is not None
                sql_root_node = fetch_main_select_from_subquery_oracle(subquery_node)
                break
            elif not order_by_mode and father_node.value == 'query_block':
                sql_root_node = father_node
                break
            father_node = father_node.father
        assert sql_root_node is not None
        if order_by_mode:
            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            ctes = ''
            if len(with_clauses) > 0:
                ctes = "WITH "
                for with_clause in with_clauses:
                    if ctes != "WITH ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
            sql = f"{ctes}SELECT {str(operand)} FROM ({sql_root_node}) AS temp"
            flag, res = execution_env.fetch_type(sql, False)
            if not flag:
                print(sql)
                print(res)
                print("Error in fetching operand type")
            return type_mapping('oracle', res[0]['type'])
        else:
            assert sql_root_node.value == 'query_block'
            target_list_node = sql_root_node.get_child_by_value('selected_list')
            sql_root_node.replace_child(target_list_node, new_operand_node)

            order_by_node = sql_root_node.get_child_by_value('order_by_clause')
            if order_by_node is not None:
                empty_node = TreeNode('', execution_env.dialect, True)
                sql_root_node.replace_child(order_by_node, empty_node)
            group_by_flag = False
            if sql_root_node.get_child_by_value('group_by_clause') is not None:
                ori_node = sql_root_node.get_child_by_value('group_by_clause')
                new_group_by_node = TreeNode(new_group_by_clause, execution_env.dialect, True)
                sql_root_node.replace_child(ori_node, new_group_by_node)
                group_by_flag = True
            with_clauses = fetch_with_ctes(sql_root_node, execution_env.dialect)
            if len(with_clauses) > 0:
                ctes = "WITH "
                build_ctes = ''
                flag_add_cte = False
                for with_clause in with_clauses:
                    if ctes != "WITH ":
                        ctes += ", "
                    ctes += str(with_clause) + "\n\t"
                    query_name_node = with_clause.get_children_by_path(['subquery_factoring_clause', 'query_name'])
                    assert len(query_name_node) == 1
                    cte_name = str(query_name_node[0])
                    if not flag_add_cte:
                        build_ctes += f'SELECT null FROM {cte_name} WHERE ROWNUM = 1'
                    else:
                        flag_add_cte = True
                        build_ctes += f' UNION SELECT null FROM {cte_name} WHERE ROWNUM = 1'
                used_sql1 = ctes + f' {build_ctes} UNION ' + str(sql_root_node)
                if group_by_flag:
                    new_group_by_node.value = ''
                used_sql2 = ctes + f' {build_ctes} UNION ' + str(sql_root_node)
            else:
                used_sql1 = str(sql_root_node)
                if group_by_flag:
                    new_group_by_node.value = ''
                used_sql2 = str(sql_root_node)
            flag, res = execution_env.fetch_type(used_sql1, False)
            if not flag:
                if used_sql1 != used_sql2:
                    flag, res = execution_env.fetch_type(used_sql2, False)
                if not flag:
                    print(used_sql1)
                    print(res)
                    print("Error in fetching operand type")
            sql_root_node.replace_child(new_operand_node, target_list_node)
            if group_by_flag:
                sql_root_node.replace_child(new_group_by_node, ori_node)
            if order_by_node is not None:
                sql_root_node.replace_child(empty_node, order_by_node)
            return type_mapping('oracle', res[0]['type'])


def sample_value(operand: str, select_stmt_node: TreeNode, execution_env: ExecutionEnv):
    # wouldn't sample value used in order by
    if select_stmt_node is None or execution_env is None:
        return []
    new_operand_node = TreeNode(str(operand), execution_env.dialect, True)
    order_by_mode = False
    # constant_type = try_get_constant_type(operand, execution_env.dialect)
    # if constant_type is not None:
    #     if execution_env.dialect == 'oracle':
    #         sql = f"SELECT {str(operand)} FROM DUAL"
    #     else:
    #         sql = f"SELECT {str(operand)}"
    #     flag, res = execution_env.execute_sql(sql)
    #     if not flag:
    #         print(sql)
    #         raise ValueError(f"Error in sampling value {str(operand)}")
    #     return res
    # TODO: Need Further Revision For Whether GROUP BY IS NEED
    if execution_env.dialect == 'mysql':
        assert select_stmt_node.value == 'querySpecification' or select_stmt_node.value == 'querySpecificationNointo'
        from_clause_node = select_stmt_node.get_child_by_value('fromClause')
        group_by_clause_node = select_stmt_node.get_child_by_value('groupByClause')
        having_clause_node = select_stmt_node.get_child_by_value('havingClause')
        window_clause_node = select_stmt_node.get_child_by_value('windowClause')
        sql_main = f"SELECT {str(new_operand_node)}"
        if from_clause_node is not None:
            sql_main = sql_main + ' ' + str(from_clause_node)
        if group_by_clause_node is not None:
            sql_main = sql_main + ' ' + str(group_by_clause_node)
        if having_clause_node is not None:
            sql_main = sql_main + ' ' + str(having_clause_node)
        if window_clause_node is not None:
            sql_main = sql_main + ' ' + str(window_clause_node)
        # remove order by
        with_clauses = fetch_with_ctes(select_stmt_node, execution_env.dialect)
        if len(with_clauses) > 0:
            ctes = "WITH RECURSIVE "
            for with_clause in with_clauses:
                if ctes != "WITH RECURSIVE ":
                    ctes += ", "
                ctes += str(with_clause) + "\n\t"
            sql = ctes + sql_main
        else:
            sql = sql_main
        flag, res = execution_env.execute_sql(sql)
        if not flag:
            print(sql)
            print("Error in sample value")
        return res
    elif execution_env.dialect == 'pg':
        assert select_stmt_node.value == 'simple_select_pramary'
        from_clause_node = select_stmt_node.get_child_by_value('from_clause')
        where_clause_node = select_stmt_node.get_child_by_value('where_clause')
        group_by_clause_node = select_stmt_node.get_child_by_value('group_clause')
        window_clause_node = select_stmt_node.get_child_by_value('window_clause')
        having_clause_node = select_stmt_node.get_child_by_value('having_clause')
        sql_main = f"SELECT {str(new_operand_node)}"
        if from_clause_node is not None:
            sql_main = sql_main + ' ' + str(from_clause_node)
        if where_clause_node is not None:
            sql_main = sql_main + ' ' + str(where_clause_node)
        if group_by_clause_node is not None:
            sql_main = sql_main + ' ' + str(group_by_clause_node)
        if having_clause_node is not None:
            sql_main = sql_main + ' ' + str(having_clause_node)
        if window_clause_node is not None:
            sql_main = sql_main + ' ' + str(window_clause_node)
        with_clauses = fetch_with_ctes(select_stmt_node, execution_env.dialect)
        if len(with_clauses) > 0:
            ctes = "WITH RECURSIVE "
            for with_clause in with_clauses:
                if ctes != "WITH RECURSIVE ":
                    ctes += ", "
                ctes += str(with_clause) + "\n\t"
            sql = ctes + sql_main
        else:
            sql = sql_main
        flag, res = execution_env.execute_sql(sql)
        if not flag:
            print(sql)
            print("Error in sample value")
        return res
    elif execution_env.dialect == 'sqlite':
        assert select_stmt_node.value == 'select_core'
        join_clause_node = select_stmt_node.get_child_by_value('join_clause')
        group_by_clause_node = select_stmt_node.get_child_by_value('group_clause')
        having_clause_node = select_stmt_node.get_child_by_value('having_clause')
        where_expr_node = None
        # SQLite grammar defines WHERE as a token followed by expr instead of a where_clause rule.
        for idx, child in enumerate(select_stmt_node.children):
            if child.value.upper() == 'WHERE' or child.terminal_node_name == 'WHERE_':
                if idx + 1 < len(select_stmt_node.children):
                    next_node = select_stmt_node.children[idx + 1]
                    if next_node.value == 'expr':
                        where_expr_node = next_node
                break

        sql_main = f"SELECT {str(new_operand_node)}"
        if join_clause_node is not None:
            sql_main = sql_main + ' FROM ' + str(join_clause_node)
        if where_expr_node is not None:
            sql_main = sql_main + ' WHERE ' + str(where_expr_node)
        if group_by_clause_node is not None:
            sql_main = sql_main + ' ' + str(group_by_clause_node)
        if having_clause_node is not None:
            sql_main = sql_main + ' ' + str(having_clause_node)
        with_clauses = fetch_with_ctes(select_stmt_node, execution_env.dialect)
        if len(with_clauses) > 0:
            ctes = "WITH RECURSIVE "
            for with_clause in with_clauses:
                if ctes != "WITH RECURSIVE ":
                    ctes += ", "
                ctes += str(with_clause) + "\n\t"
            sql = ctes + sql_main
        else:
            sql = sql_main
        flag, res = execution_env.execute_sql(sql)
        if not flag:
            print(sql)
            print("Error in sample value")
        return res
    elif execution_env.dialect == 'snowflake':
        assert select_stmt_node.value == 'select_statement'
        select_optional_node = select_stmt_node.get_child_by_value('select_optional_clauses')
        from_clause_node = None
        where_clause_node = None
        group_by_clause_node = None
        having_clause_node = None
        qualify_clause_node = None
        if select_optional_node is not None:
            from_clause_node = select_optional_node.get_child_by_value('from_clause')
            where_clause_node = select_optional_node.get_child_by_value('where_clause')
            group_by_clause_node = select_optional_node.get_child_by_value('group_by_clause')
            having_clause_node = select_optional_node.get_child_by_value('having_clause')
            qualify_clause_node = select_optional_node.get_child_by_value('qualify_clause')
        sql_main = f"SELECT {str(new_operand_node)}"
        if from_clause_node is not None:
            sql_main = sql_main + ' ' + str(from_clause_node)
        if where_clause_node is not None:
            sql_main = sql_main + ' ' + str(where_clause_node)
        if group_by_clause_node is not None:
            sql_main = sql_main + ' ' + str(group_by_clause_node)
        if having_clause_node is not None:
            sql_main = sql_main + ' ' + str(having_clause_node)
        if qualify_clause_node is not None:
            sql_main = sql_main + ' ' + str(qualify_clause_node)
        with_clauses = fetch_with_ctes(select_stmt_node, execution_env.dialect)
        if len(with_clauses) > 0:
            ctes = "WITH RECURSIVE "
            for with_clause in with_clauses:
                if ctes != "WITH RECURSIVE ":
                    ctes += ", "
                ctes += str(with_clause) + "\n\t"
            sql = ctes + sql_main
        else:
            sql = sql_main
        flag, res = execution_env.execute_sql(sql)
        if not flag:
            print(sql)
            print("Error in sample value")
        return res
    elif execution_env.dialect == 'sqlserver':
        assert select_stmt_node.value == 'query_specification'
        table_sources_node = select_stmt_node.get_child_by_value('table_sources')
        search_condition_node = select_stmt_node.get_child_by_value('search_condition')
        group_by_clause_node = select_stmt_node.get_child_by_value('group_clause')
        having_clause_node = select_stmt_node.get_child_by_value('having_clause')
        sql_main = f"SELECT {str(new_operand_node)}"
        if table_sources_node is not None:
            sql_main = sql_main + ' FROM ' + str(table_sources_node)
        if search_condition_node is not None:
            sql_main = sql_main + ' WHERE ' + str(search_condition_node)
        if group_by_clause_node is not None:
            sql_main = sql_main + ' ' + str(group_by_clause_node)
        if having_clause_node is not None:
            sql_main = sql_main + ' ' + str(having_clause_node)
        with_clauses = fetch_with_ctes(select_stmt_node, execution_env.dialect)
        if len(with_clauses) > 0:
            ctes = "WITH "
            for with_clause in with_clauses:
                if ctes != "WITH ":
                    ctes += ", "
                ctes += str(with_clause) + "\n\t"
            sql = ctes + sql_main
        else:
            sql = sql_main
        flag, res = execution_env.execute_sql(sql)
        if not flag:
            print(sql)
            print("Error in sample value")
        return res
    elif execution_env.dialect == 'oracle':
        assert select_stmt_node.value == 'query_block'
        from_clause_node = select_stmt_node.get_child_by_value('from_clause')
        where_clause_node = select_stmt_node.get_child_by_value('where_clause')
        group_by_clause_node = select_stmt_node.get_child_by_value('group_by_clause')
        sql_main = f"SELECT {str(new_operand_node)}"
        if from_clause_node is not None:
            sql_main = sql_main + ' ' + str(from_clause_node)
        if where_clause_node is not None:
            sql_main = sql_main + " " + str(where_clause_node)
        # if group_by_clause_node is not None:
        #     sql_main = sql_main + ' ' + str(group_by_clause_node)
        with_clauses = fetch_with_ctes(select_stmt_node, execution_env.dialect)
        if len(with_clauses) > 0:
            ctes = "WITH "
            for with_clause in with_clauses:
                if ctes != "WITH ":
                    ctes += ", "
                ctes += str(with_clause) + "\n\t"
            sql = ctes + sql_main
        else:
            sql = sql_main
        flag, res = execution_env.execute_sql(sql)
        if not flag:
            print(sql)
            print("Error in sample value")
        return res
