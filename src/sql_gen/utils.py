# -*- coding: utf-8 -*-
from utils.tools import get_proj_root_path
# @Project: SQL2SQL_Bench
# @Module: utils.py$

# @Time: 2025/9/3 22:47
import json


class QueryPair(dict):
    def __init__(self, query_dict: dict):
        super().__init__(query_dict)
        self.src_dialect = None
        self.tgt_dialect = None
        for key, value in query_dict.items():
            if self.src_dialect is None:
                self.src_dialect = key
            elif self.tgt_dialect is None:
                self.tgt_dialect = key
            else:
                break
        self.src_sql = query_dict[self.src_dialect]
        self.tgt_sql = query_dict[self.tgt_dialect]
        self.points = query_dict['points']
        self.rewrite_tokens = query_dict['rewrite_tokens']
        self.tables = query_dict['tables']



def load_multi_points(src_dialect, tgt_dialect):
    with open(f'{get_proj_root_path()}/dataset/multiple_points/{src_dialect}_{tgt_dialect}'
              f'_final_sample_points.json', 'r') as file:
        return json.load(file)
