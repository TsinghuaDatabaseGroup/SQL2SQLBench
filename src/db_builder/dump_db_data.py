import os.path
from datetime import date, datetime
from decimal import Decimal

import json

from tqdm import tqdm

from dialects.dialect_tools import get_table_col_name
from utils.db_connector import sql_execute
from utils.tools import get_all_db_name, get_data_path


def process_row(row, cols):
    assert len(row) == len(cols)
    row_data = []

    for i, value in enumerate(row):
        type_name = cols[i]['type']['type_name']
        if value is None:
            row_data.append(None)
            continue
        if type_name == 'NVARCHAR':
            # gen_value 需要 str
            row_data.append(str(value))
        elif type_name == 'INT':
            # gen_value 需要 int 或 str，直接给 int 最合适
            row_data.append(int(value))
        elif type_name == 'DATE':
            # DateType.gen_value 最稳妥的输入格式
            if isinstance(value, datetime):
                value = value.date()
            if isinstance(value, date):
                row_data.append({
                    "value": value.strftime("%Y-%m-%d"),
                    "format": "yyyy-MM-dd"
                })
            else:
                # 假设数据库返回的已经是 YYYY-MM-DD 或可转成这个格式
                row_data.append({
                    "value": str(value)[:10],
                    "format": "yyyy-MM-dd"
                })
        elif type_name == 'DECIMAL':
            # DecimalType 继承 FloatGeneralType，gen_value 接受 float 或 str
            if isinstance(value, Decimal):
                row_data.append(float(value))
            else:
                row_data.append(float(value))
        else:
            raise ValueError(f"Unsupported type_name: {type_name}")
    return row_data


def dump_database(dialect, db_name):
    with open(os.path.join(get_data_path(), f'{db_name}/schema.json'), 'r') as f:
        schema = json.load(f)

    # INT DECIMAL NVARCHAR DATE
    for table in schema:
        print(table)
        cols = [get_table_col_name(col['col_name'], dialect) for col in schema[table]['cols']]
        sql = f'SELECT {",".join(cols)} FROM {get_table_col_name(table, dialect)};'
        flag, res = sql_execute(dialect, get_all_db_name(dialect), sql)
        table_data = [[col['col_name'] for col in schema[table]['cols']]]
        for row in tqdm(res):
            row_data = process_row(row, schema[table]['cols'])
            table_data.append(row_data)
        with open(f'{get_data_path()}/{db_name}/data/' + table + '.json', 'w') as f:
            json.dump(table_data, f, indent=4)
