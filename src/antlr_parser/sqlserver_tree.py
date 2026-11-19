from antlr_parser.Tree import TreeNode
from dialects.dialect_tools import get_table_col_name


def rename_column_sqlserver(select_element_node: TreeNode, name_dict: dict, extend_name=None):
    if extend_name is None:
        extend_name = 'col'
    idx = 0
    while f"{extend_name.lower()}_{idx}" in name_dict:
        idx += 1
    name_dict[f"{extend_name.lower()}_{idx}"] = 1
    if select_element_node.get_child_by_value('udt_elem') is not None:
        uid_node = select_element_node.get_child_by_value('udt_elem').get_child_by_value('as_column_alias')
        if uid_node is not None:
            alias_node = uid_node.get_child_by_value('column_alias')
            new_name_node = TreeNode(f"{extend_name.lower()}_{idx}", 'sqlserver', True)
            assert isinstance(uid_node, TreeNode)
            alias_node.children = [new_name_node]
        else:
            as_column_alias_node = TreeNode('as_column_alias', 'sqlserver', False)
            as_column_alias_node.add_child(TreeNode('AS', 'sqlserver', True))
            as_column_alias_node.add_child(TreeNode(f"{extend_name.lower()}_{idx}", 'sqlserver', True))
            select_element_node.get_child_by_value('udt_elem').add_child(as_column_alias_node)
    elif select_element_node.get_child_by_value('expression_elem') is not None:
        uid_node = select_element_node.get_child_by_value('expression_elem').get_child_by_value('as_column_alias')
        if uid_node is not None:
            alias_node = uid_node.get_child_by_value('column_alias')
            new_name_node = TreeNode(f"{extend_name.lower()}_{idx}", 'sqlserver', True)
            assert isinstance(uid_node, TreeNode)
            alias_node.children = [new_name_node]
        else:
            as_column_alias_node = TreeNode('as_column_alias', 'sqlserver', False)
            as_column_alias_node.add_child(TreeNode('AS', 'sqlserver', True))
            as_column_alias_node.add_child(TreeNode(f"{extend_name.lower()}_{idx}", 'sqlserver', True))
            select_element_node.get_child_by_value('expression_elem').add_child(as_column_alias_node)
    return f"{extend_name}_{idx}"


def fetch_all_simple_select_from_select_statement_standalone_sqlserver(select_statement_standalone_node: TreeNode):
    if select_statement_standalone_node is None:
        return []

    node = select_statement_standalone_node
    if node.value == 'select_statement_standalone':
        node = node.get_child_by_value('select_statement')
        if node is None:
            return []

    if node.value == 'select_statement':
        node = node.get_child_by_value('query_expression')
        if node is None:
            return []

    if node.value == 'query_specification':
        return [node]
    if node.value != 'query_expression':
        return []

    res: list[TreeNode] = []

    def collect_query_expression(query_expression_node: TreeNode):
        # query_expression:
        #   query_specification ... sql_union*
        #   | '(' query_expression ')' (UNION ALL? query_expression)?
        query_specification_node = query_expression_node.get_child_by_value('query_specification')
        if query_specification_node is not None:
            res.append(query_specification_node)

            for sql_union_node in query_expression_node.get_children_by_value('sql_union'):
                union_spec_node = sql_union_node.get_child_by_value('query_specification')
                if union_spec_node is not None:
                    res.append(union_spec_node)
                    continue

                union_query_expression_node = sql_union_node.get_child_by_value('query_expression')
                if union_query_expression_node is not None:
                    collect_query_expression(union_query_expression_node)
            return

        for nested_query_expression_node in query_expression_node.get_children_by_value('query_expression'):
            collect_query_expression(nested_query_expression_node)

    collect_query_expression(node)
    return res


def fetch_main_select_from_select_statement_standalone_sqlserver(select_statement_standalone_node: TreeNode):
    if select_statement_standalone_node is None:
        return None

    node = select_statement_standalone_node
    if node.value == 'select_statement_standalone':
        node = node.get_child_by_value('select_statement')
        assert node is not None

    if node.value == 'select_statement':
        node = node.get_child_by_value('query_expression')
        assert node is not None

    while node is not None and node.value == 'query_expression':
        query_specification_nodes = node.get_children_by_value('query_specification')
        if len(query_specification_nodes) > 0:
            return query_specification_nodes[0]

        query_expression_nodes = node.get_children_by_value('query_expression')
        if len(query_expression_nodes) == 0:
            break
        # Follow the left-most branch for parenthesized/compound expressions.
        node = query_expression_nodes[0]

    return None


def analyze_table_source_sqlserver(table_sources: list[TreeNode]):
    def normalize_identifier(value: str) -> str:
        return value.replace('"', '').replace('`', '').replace('[', '').replace(']', '').strip()

    def extract_alias_node(table_source_item_node: TreeNode) -> TreeNode | None:
        as_table_alias_node = table_source_item_node.get_child_by_value('as_table_alias')
        if as_table_alias_node is None:
            return None
        return as_table_alias_node.get_child_by_value('table_alias')

    def extract_alias(table_source_item_node: TreeNode) -> str | None:
        alias_node = extract_alias_node(table_source_item_node)
        if alias_node is None:
            return None
        return normalize_identifier(str(alias_node))

    def ensure_alias(table_source_item_node: TreeNode, base_name: str,
                     name_dict: dict[str, int]) -> tuple[str, bool]:
        rename_flag = False
        if base_name in name_dict:
            rename_flag = True
            alias = f"{base_name}_{name_dict[base_name]}"
            name_dict[base_name] += 1
        else:
            name_dict[base_name] = 1
            alias = base_name

        alias_node = extract_alias_node(table_source_item_node)
        if alias_node is not None:
            alias_node.children = [TreeNode(get_table_col_name(alias, 'sqlserver').lower(), 'sqlserver', True)]
        elif rename_flag:
            as_alias = TreeNode('as_table_alias', 'sqlserver', False)
            as_alias.add_child(TreeNode('AS', 'sqlserver', True))
            alias_node = TreeNode('table_alias', 'sqlserver', False)
            alias_node.add_child(TreeNode(get_table_col_name(alias, 'sqlserver').lower(), 'sqlserver', True))
            as_alias.add_child(alias_node)
            table_source_item_node.add_child(as_alias)
        return alias, rename_flag

    def extract_column_alias_list(table_source_item_node: TreeNode) -> list[str] | None:
        column_alias_list_node = table_source_item_node.get_child_by_value('column_alias_list')
        if column_alias_list_node is None:
            return None
        column_alias_nodes = column_alias_list_node.get_children_by_value('column_alias')
        if len(column_alias_nodes) == 0:
            return None
        return [normalize_identifier(str(alias_node)) for alias_node in column_alias_nodes]

    def analyze_table_source_item(table_source_item_node: TreeNode,
                                  name_dict: dict[str, int],
                                  subquery_id: int) -> tuple[list, int]:
        full_table_name_node = table_source_item_node.get_child_by_value('full_table_name')
        if full_table_name_node is not None:
            table_name = normalize_identifier(str(full_table_name_node))
            explicit_alias = extract_alias(table_source_item_node)
            base_name = explicit_alias if explicit_alias is not None else table_name
            alias, _ = ensure_alias(table_source_item_node, base_name, name_dict)
            return [{
                'type': 'table',
                'name': table_name,
                'alias': alias if alias != table_name else None,
                'column_names': extract_column_alias_list(table_source_item_node)
            }], subquery_id

        derived_table_node = table_source_item_node.get_child_by_value('derived_table')
        if derived_table_node is not None:
            explicit_alias = extract_alias(table_source_item_node)
            if explicit_alias is None:
                base_name = f'subquery_{subquery_id}'
                subquery_id += 1
            else:
                base_name = explicit_alias
            alias, rename_flag = ensure_alias(table_source_item_node, base_name, name_dict)
            subquery_node = derived_table_node.get_child_by_value('subquery')
            if subquery_node is None:
                subquery_node = derived_table_node
            select_statement_node = subquery_node.get_child_by_value('select_statement')
            if select_statement_node is None:
                select_statement_node = subquery_node
            return [{
                'type': 'subquery',
                'name': alias,
                'column_names': extract_column_alias_list(table_source_item_node),
                'sub_query_node': select_statement_node,
                'lateral': False,
                'rename_flag': rename_flag
            }], subquery_id

        return [{
            'type': 'other',
            'name': extract_alias(table_source_item_node),
            'content': table_source_item_node
        }], subquery_id

    res = []
    name_dict: dict[str, int] = {}
    subquery_id = 0
    pending_table_sources = list(table_sources)
    while len(pending_table_sources) > 0:
        table_source_node = pending_table_sources.pop()
        table_source_item_node = table_source_node.get_child_by_value('table_source_item')
        if table_source_item_node is not None:
            analyzed, subquery_id = analyze_table_source_item(table_source_item_node, name_dict, subquery_id)
            res.extend(analyzed)

            nested_table_source = table_source_item_node.get_child_by_value('table_source')
            if nested_table_source is not None:
                pending_table_sources.append(nested_table_source)

        for join_part_node in table_source_node.get_children_by_value('join_part'):
            join_on_node = join_part_node.get_child_by_value('join_on')
            if join_on_node is not None:
                joined_table_source = join_on_node.get_child_by_value('table_source')
                if joined_table_source is not None:
                    pending_table_sources.append(joined_table_source)
                continue

            cross_join_node = join_part_node.get_child_by_value('cross_join')
            if cross_join_node is not None:
                cross_source = cross_join_node.get_child_by_value('table_source')
                if cross_source is not None:
                    pending_table_sources.append(cross_source)
                continue

            apply_node = join_part_node.get_child_by_value('apply_')
            if apply_node is not None:
                apply_source = apply_node.get_child_by_value('table_source')
                if apply_source is not None:
                    pending_table_sources.append(apply_source)
    return res
