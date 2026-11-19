# -*- coding: utf-8 -*-
# @Project: SQL2SQL_Bench
# @Module: generation_tool$

# @Time: 2025/5/22 0:19
from antlr_parser.Tree import TreeNode


def structural_complexity_stat(root_node: TreeNode, dialect: str) -> int:
    if dialect == 'mysql':
        return stat_mysql_complexity(root_node)
    elif dialect == 'pg':
        return stat_pg_complexity(root_node)
    elif dialect == 'oracle':
        return stat_oracle_complexity(root_node)
    elif dialect == 'sqlite':
        return stat_sqlite_complexity(root_node)
    elif dialect == 'sqlserver':
        return stat_sqlserver_complexity(root_node)
    elif dialect == 'snowflake':
        return stat_snowflake_complexity(root_node)
    else:
        raise ValueError("Unsupported dialect.")


def stat_mysql_complexity(node: TreeNode):
    cnt = 0
    for child in node.children:
        cnt += stat_mysql_complexity(child)
    if (not node.is_terminal and
            node.value == 'querySpecification' or node.value == 'querySpecificationNointo'):
        return cnt + 1
    else:
        return cnt


def stat_pg_complexity(node: TreeNode):
    cnt = 0
    for child in node.children:
        cnt += stat_pg_complexity(child)
    if not node.is_terminal and node.value == 'simple_select_pramary':
        return cnt + 1
    else:
        return cnt


def stat_oracle_complexity(node: TreeNode):
    cnt = 0
    for child in node.children:
        cnt += stat_oracle_complexity(child)
    if not node.is_terminal and node.value == 'query_block':
        return cnt + 1
    else:
        return cnt


def stat_sqlite_complexity(node: TreeNode):
    cnt = 0
    for child in node.children:
        cnt += stat_sqlite_complexity(child)
    if (not node.is_terminal and node.value == 'select_core'
            and node.get_child_by_value('values_clause') is None):
        return cnt + 1
    else:
        return cnt


def stat_sqlserver_complexity(node: TreeNode):
    cnt = 0
    for child in node.children:
        cnt += stat_sqlserver_complexity(child)
    if not node.is_terminal and node.value == 'query_specification':
        return cnt + 1
    else:
        return cnt


def stat_snowflake_complexity(node: TreeNode):
    cnt = 0
    for child in node.children:
        cnt += stat_snowflake_complexity(child)
    if not node.is_terminal and node.value == 'select_statement':
        return cnt + 1
    else:
        return cnt
