from antlr_parser.Tree import TreeNode
from dialects.dialect_tools import get_table_col_name


def fetch_all_simple_select_from_query_stmt_snowflake(query_stmt_node: TreeNode):
    res = []
    visited = set()
    def add_select_statement(node: TreeNode):
        if node is None or node.value != 'select_statement':
            return
        node_id = id(node)
        if node_id in visited:
            return
        visited.add(node_id)
        res.append(node)

    def walk_with_expression(node: TreeNode):
        if node is None:
            return
        for cte_node in node.get_children_by_value('common_table_expression'):
            for stmt_in_paren in cte_node.get_children_by_value('select_statement_in_parentheses'):
                walk_select_statement_in_parentheses(stmt_in_paren)

    def walk_set_operators(node: TreeNode):
        if node is None:
            return
        for stmt_in_paren in node.get_children_by_value('select_statement_in_parentheses'):
            walk_select_statement_in_parentheses(stmt_in_paren)

    def walk_select_statement_in_parentheses(node: TreeNode):
        if node is None:
            return
        for child in node.children:
            if child.value == 'select_statement':
                add_select_statement(child)
            elif child.value == 'select_statement_in_parentheses':
                walk_select_statement_in_parentheses(child)
            elif child.value == 'set_operators':
                walk_set_operators(child)
            elif child.value == 'with_expression':
                walk_with_expression(child)
    if query_stmt_node is None:
        return res
    walk_with_expression(query_stmt_node.get_child_by_value('with_expression'))
    for stmt_in_paren in query_stmt_node.get_children_by_value('select_statement_in_parentheses'):
        walk_select_statement_in_parentheses(stmt_in_paren)
    for set_operator_node in query_stmt_node.get_children_by_value('set_operators'):
        walk_set_operators(set_operator_node)
    return res


def rename_column_snowflake(select_element_node: TreeNode, name_dict: dict, extend_name=None):
    if extend_name is None:
        extend_name = 'col'
    idx = 0
    while f"{extend_name.lower()}_{idx}" in name_dict:
        idx += 1
    name_dict[f"{extend_name.lower()}_{idx}"] = 1
    if select_element_node.get_child_by_value('as_alias') is not None:
        uid_node = select_element_node.get_child_by_value('as_alias').get_child_by_value('alias')
        new_name_node = TreeNode(f"{extend_name.lower()}_{idx}", 'snowflake', True)
        assert isinstance(uid_node, TreeNode)
        uid_node.children = [new_name_node]
    else:
        as_alias_node = TreeNode('as_alias', 'snowflake', False)
        as_alias_node.add_child(TreeNode('AS', 'snowflake', True))
        as_alias_node.add_child(TreeNode(f"{extend_name.lower()}_{idx}", 'snowflake', True))
        select_element_node.add_child(as_alias_node)
    return f"{extend_name}_{idx}"


def fetch_main_select_from_query_statement_snowflake(query_statement_node: TreeNode):
    if query_statement_node is None:
        return None

    def walk_select_statement_in_parentheses(node: TreeNode):
        if node is None:
            return None
        if node.value == 'select_statement':
            return node

        # Prefer the left-most branch for set operations.
        child_select = node.get_child_by_value('select_statement')
        if child_select is not None:
            return child_select

        nested_stmt = node.get_child_by_value('select_statement_in_parentheses')
        if nested_stmt is not None:
            res = walk_select_statement_in_parentheses(nested_stmt)
            if res is not None:
                return res

        set_operator_node = node.get_child_by_value('set_operators')
        if set_operator_node is not None:
            return walk_select_statement_in_parentheses(
                set_operator_node.get_child_by_value('select_statement_in_parentheses')
            )
        return None

    if query_statement_node.value == 'select_statement_in_parentheses':
        return walk_select_statement_in_parentheses(query_statement_node)

    stmt_in_paren = query_statement_node.get_child_by_value('select_statement_in_parentheses')
    return walk_select_statement_in_parentheses(stmt_in_paren)


def analyze_table_source_snowflake(table_sources: list[TreeNode]):
    def normalize_identifier(value: str) -> str:
        return value.replace('"', '').replace('`', '').replace('[', '').replace(']', '').strip()

    def get_alias_node(object_ref_node: TreeNode) -> TreeNode | None:
        as_alias_node = object_ref_node.get_child_by_value('as_alias')
        if as_alias_node is None:
            return None
        return as_alias_node.get_child_by_value('alias')

    def get_explicit_alias(object_ref_node: TreeNode) -> str | None:
        alias_node = get_alias_node(object_ref_node)
        if alias_node is None:
            return None
        return normalize_identifier(str(alias_node))

    def ensure_alias(object_ref_node: TreeNode, base_name: str, name_dict: dict[str, int]) -> tuple[str, bool]:
        rename_flag = False
        if base_name in name_dict:
            rename_flag = True
            alias = f"{base_name}_{name_dict[base_name]}"
            name_dict[base_name] += 1
        else:
            name_dict[base_name] = 1
            alias = base_name

        alias_node = get_alias_node(object_ref_node)
        if alias_node is not None:
            alias_node.children = [TreeNode(get_table_col_name(alias, 'snowflake').lower(), 'snowflake', True)]
        elif rename_flag:
            as_alias_node = TreeNode('as_alias', 'snowflake', False)
            as_alias_node.add_child(TreeNode('AS', 'snowflake', True))
            alias_node = TreeNode('alias', 'snowflake', False)
            alias_node.add_child(TreeNode(get_table_col_name(alias, 'snowflake').lower(), 'snowflake', True))
            as_alias_node.add_child(alias_node)
            object_ref_node.add_child(as_alias_node)
        return alias, rename_flag

    def extract_column_names(object_ref_node: TreeNode) -> list[str] | None:
        col_list = object_ref_node.get_child_by_value('column_alias_list_in_brackets')
        if col_list is None:
            return None
        alias_nodes = col_list.get_children_by_value('alias')
        if len(alias_nodes) == 0:
            return None
        return [normalize_identifier(str(alias_node)) for alias_node in alias_nodes]

    def collect_object_refs(table_source_node: TreeNode) -> list[TreeNode]:
        res = []

        def walk_joined(node: TreeNode):
            if node is None:
                return
            obj_ref = node.get_child_by_value('object_ref')
            if obj_ref is not None:
                res.append(obj_ref)

            for join_clause_node in node.get_children_by_value('join_clause'):
                join_obj = join_clause_node.get_child_by_value('object_ref')
                if join_obj is not None:
                    res.append(join_obj)

            nested = node.get_child_by_value('table_source_item_joined')
            if nested is not None:
                walk_joined(nested)

        top_joined = table_source_node.get_child_by_value('table_source_item_joined')
        if top_joined is not None:
            walk_joined(top_joined)
        else:
            direct_ref = table_source_node.get_child_by_value('object_ref')
            if direct_ref is not None:
                res.append(direct_ref)
        return res

    res = []
    name_dict: dict[str, int] = {}
    generated_subquery_id = 0
    for table_source in table_sources:
        for object_ref_node in collect_object_refs(table_source):
            lateral_flag = object_ref_node.get_child_by_value('LATERAL') is not None
            object_name_node = object_ref_node.get_child_by_value('object_name')
            subquery_node = object_ref_node.get_child_by_value('subquery')

            if object_name_node is not None:
                table_name = normalize_identifier(str(object_name_node))
                explicit_alias = get_explicit_alias(object_ref_node)
                base_name = explicit_alias if explicit_alias is not None else table_name
                alias, _ = ensure_alias(object_ref_node, base_name, name_dict)
                res.append({
                    'type': 'table',
                    'name': table_name,
                    'alias': alias if alias != table_name else None,
                    'column_names': extract_column_names(object_ref_node)
                })
                continue

            if subquery_node is not None:
                explicit_alias = get_explicit_alias(object_ref_node)
                if explicit_alias is None:
                    base_name = f'subquery_{generated_subquery_id}'
                    generated_subquery_id += 1
                else:
                    base_name = explicit_alias
                alias, rename_flag = ensure_alias(object_ref_node, base_name, name_dict)
                query_statement_node = subquery_node.get_child_by_value('query_statement')
                if query_statement_node is None:
                    query_statement_node = subquery_node
                res.append({
                    'type': 'subquery',
                    'name': alias,
                    'column_names': extract_column_names(object_ref_node),
                    'sub_query_node': query_statement_node,
                    'lateral': lateral_flag,
                    'rename_flag': rename_flag
                })
                continue
            res.append({
                'type': 'other',
                'name': get_explicit_alias(object_ref_node),
                'content': object_ref_node
            })
    return res

