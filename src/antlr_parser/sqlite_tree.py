from antlr_parser.Tree import TreeNode
from dialects.dialect_tools import get_table_col_name


def rename_column_sqlite(select_element_node: TreeNode, name_dict: dict, extend_name=None):
    if extend_name is None:
        extend_name = 'col'
    idx = 0
    while f"{extend_name.lower()}_{idx}" in name_dict:
        idx += 1
    name_dict[f"{extend_name.lower()}_{idx}"] = 1
    if select_element_node.get_child_by_value('column_alias') is not None:
        uid_node = select_element_node.get_child_by_value('column_alias')
        new_name_node = TreeNode(f"{extend_name.lower()}_{idx}", 'sqlite', True)
        assert isinstance(uid_node, TreeNode)
        uid_node.children = [new_name_node]
    else:
        select_element_node.add_child(TreeNode('AS', 'sqlite', True))
        select_element_node.add_child(TreeNode(f"{extend_name.lower()}_{idx}", 'sqlite', True))
    return f"{extend_name}_{idx}"


def fetch_all_simple_select_from_select_stmt_sqlite(select_stmt_node: TreeNode):
    if select_stmt_node is None:
        return []

    node = select_stmt_node

    # Accept wrapper nodes that contain a nested select_stmt.
    while node.value not in {'select_stmt', 'select_core'}:
        child_select_stmt = node.get_child_by_value('select_stmt')
        if child_select_stmt is None:
            break
        node = child_select_stmt

    if node.value == 'select_core':
        return [] if node.get_child_by_value('values_clause') is not None else [node]

    if node.value != 'select_stmt':
        return []

    # SQLite grammar: select_stmt := with_clause? select_core (compound_operator select_core)* ...
    res = []
    for select_core_node in node.get_children_by_value('select_core'):
        if select_core_node.get_child_by_value('values_clause') is None:
            res.append(select_core_node)
    return res


def fetch_main_select_from_select_stmt_sqlite(select_stmt_node: TreeNode):
    if select_stmt_node is None:
        return None

    node = select_stmt_node
    if node.value != 'select_stmt':
        child_select_stmt = node.get_child_by_value('select_stmt')
        if child_select_stmt is not None:
            node = child_select_stmt

    if node.value == 'select_core':
        return node

    select_core_nodes = node.get_children_by_value('select_core')
    if len(select_core_nodes) > 0:
        # SQLite compound queries are left-associative; first select_core is the main branch.
        return select_core_nodes[0]

    return None


def analyze_table_or_subquery_sqlite(table_or_subqueries: list[TreeNode]):
    def normalize_identifier(value: str) -> str:
        return value.replace('"', '').replace('`', '').replace('[', '').replace(']', '').strip()

    def collect_explicit_alias(node: TreeNode) -> str | None:
        alias_node = node.get_child_by_value('table_alias')
        if alias_node is None:
            alias_node = node.get_child_by_value('table_alias_excluding_joins')
        if alias_node is None:
            return None
        return normalize_identifier(str(alias_node))

    def collect_column_names(node: TreeNode) -> list[str] | None:
        column_name_nodes = node.get_children_by_value('column_name')
        if len(column_name_nodes) == 0:
            return None
        return [normalize_identifier(str(col)) for col in column_name_nodes]

    def ensure_unique_alias(node: TreeNode, base_name: str, name_dict: dict[str, int]) -> tuple[str, bool]:
        rename_flag = False
        if base_name in name_dict:
            rename_flag = True
            alias = f"{base_name}_{name_dict[base_name]}"
            name_dict[base_name] += 1
        else:
            name_dict[base_name] = 1
            alias = base_name

        alias_node = node.get_child_by_value('table_alias')
        if alias_node is None:
            alias_node = node.get_child_by_value('table_alias_excluding_joins')
        if alias_node is not None:
            alias_node.children = [TreeNode(get_table_col_name(alias, 'sqlite').lower(), 'sqlite', True)]
        elif rename_flag:
            node.add_child(TreeNode('AS', 'sqlite', True))
            new_alias_node = TreeNode('table_alias', 'sqlite', False)
            new_alias_node.add_child(TreeNode(get_table_col_name(alias, 'sqlite').lower(), 'sqlite', True))
            node.add_child(new_alias_node)
        return alias, rename_flag

    res = []
    name_dict: dict[str, int] = {}
    subquery_idx = 0
    for table_or_subquery_node in table_or_subqueries:
        table_name_node = table_or_subquery_node.get_child_by_value('table_name')
        if table_name_node is not None:
            table_name = normalize_identifier(str(table_name_node))
            explicit_alias = collect_explicit_alias(table_or_subquery_node)
            final_name = explicit_alias if explicit_alias is not None else table_name
            alias, _ = ensure_unique_alias(table_or_subquery_node, final_name, name_dict)
            res.append({
                'type': 'table',
                'name': table_name,
                'alias': alias if alias != table_name else None,
                'column_names': collect_column_names(table_or_subquery_node)
            })
            continue

        select_stmt_node = table_or_subquery_node.get_child_by_value('select_stmt')
        if select_stmt_node is not None:
            explicit_alias = collect_explicit_alias(table_or_subquery_node)
            if explicit_alias is None:
                base_name = f'subquery_{subquery_idx}'
                subquery_idx += 1
            else:
                base_name = explicit_alias
            alias, rename_flag = ensure_unique_alias(table_or_subquery_node, base_name, name_dict)
            res.append({
                'type': 'subquery',
                'name': alias,
                'column_names': collect_column_names(table_or_subquery_node),
                'sub_query_node': select_stmt_node,
                'lateral': False,
                'rename_flag': rename_flag
            })
            continue

        join_clause_node = table_or_subquery_node.get_child_by_value('join_clause')
        if join_clause_node is not None:
            nested = join_clause_node.get_children_by_value('table_or_subquery')
            if len(nested) > 0:
                res.extend(analyze_table_or_subquery_sqlite(nested))
            continue

        res.append({
            'type': 'other',
            'name': None,
            'content': table_or_subquery_node
        })
    return res


def parse_sqlserver_group_by(group_by_elements_nodes: list):
    all_expressions = []
    for group_by_element_node in group_by_elements_nodes:
        all_expressions = all_expressions + get_all_expression_nodes(group_by_element_node)
    return all_expressions


def get_all_expression_nodes(node: TreeNode):
    if node.value == 'expression':
        return [node]
    else:
        res = []
        for child in node.children:
            res = res + get_all_expression_nodes(child)
        return res

