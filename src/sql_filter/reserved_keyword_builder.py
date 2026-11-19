import json
import os
from typing import Set

from utils.tools import get_data_path, get_proj_root_path


def _load_reserved_keywords(dialect: str) -> Set[str]:
    utils_dir = os.path.join(get_proj_root_path(), "src", "utils")
    file_path = os.path.join(utils_dir, f"{dialect.lower()}_reserved_keyword.json")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Reserved keyword file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        keywords = json.load(f)

    return {str(keyword).upper() for keyword in keywords}


def _resolve_data_root() -> str:
    configured_path = get_data_path()
    if configured_path and os.path.exists(configured_path):
        return configured_path

    # Fallback for local development where config points to a non-existent machine path.
    local_path = os.path.join(get_proj_root_path(), "database_data")
    if os.path.exists(local_path):
        return local_path

    raise FileNotFoundError(
        f"Cannot locate database_data folder. Tried: {configured_path}, {local_path}"
    )


def _collect_schema_identifiers(data_root: str) -> Set[str]:
    identifiers = set()
    for db_name in os.listdir(data_root):
        schema_path = os.path.join(data_root, db_name, "schema.json")
        if not os.path.isfile(schema_path):
            continue

        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        for _, table_info in schema.items():
            table_name = table_info.get("table")
            if table_name:
                identifiers.add(str(table_name).upper())

            for col in table_info.get("cols", []):
                col_name = col.get("col_name")
                if col_name:
                    identifiers.add(str(col_name).upper())

    return identifiers


def reserved_keyword_builder(src_dialect, tgt_dialect):
    src_reserved = _load_reserved_keywords(src_dialect)
    tgt_reserved = _load_reserved_keywords(tgt_dialect)

    data_root = _resolve_data_root()
    identifier_names = _collect_schema_identifiers(data_root)

    conflict_keywords = identifier_names.intersection(tgt_reserved - src_reserved)
    quote_style_front = {
        "mysql": "`",
        "pg": "\"",
        "oracle": "\"",
        "sqlite": "\"",
        "snowflake": "\"",
        "sqlserver": "["
    }
    quote_style_back = {
        "mysql": "`",
        "pg": "\"",
        "oracle": "\"",
        "sqlite": "\"",
        "snowflake": "\"",
        "sqlserver": "["
    }
    res = []
    for word in conflict_keywords:
        res.append({
            "Desc": f"{word}_R",
            "Dialect": {
                "Src": src_dialect,
                "Tgt":tgt_dialect
            },
            "Type": "RESERVED_KEYWORD",
            "SrcPattern": f"{word}",
            "TgtPattern": f"{quote_style_front[src_dialect]}{word}{quote_style_back[tgt_dialect]}",
            "Condition": None,
            "Return": None
        })

    with open(f'{get_proj_root_path()}/conv_point/object_name/{src_dialect}_{tgt_dialect}.json', 'w') as f:
        json.dump(res, f, indent=4)

    return sorted(conflict_keywords)


if __name__ == "__main__":
    src_dialect = 'sqlserver'
    for tgt_dialect in ['mysql', 'pg', 'oracle', 'sqlite', 'snowflake']:
        print(tgt_dialect)
        reserved_keywords = reserved_keyword_builder(src_dialect, tgt_dialect)
        print(reserved_keywords)
