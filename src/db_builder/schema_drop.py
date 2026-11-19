from utils.db_connector import sql_execute, oracle_sql_execute, mysql_drop_db, oracle_drop_db, pg_drop_db
from utils.tools import get_all_db_name, get_db_ids, get_empty_db_name, get_data_path
from dialects.dialect_tools import get_table_col_name

from tqdm import tqdm
import json


def drop_schema(dialect: str):
    """
    Drop a schema from the database.
    """
    db_id = 'job'
    with open(f'{get_data_path()}/{db_id}/schema.json', 'r') as f:
        data = json.load(f)
    db_name = get_all_db_name(dialect)
    for key, value in tqdm(data.items()):
        flag, res = sql_execute(dialect, db_name, f'DROP TABLE {get_table_col_name(key, dialect)};')
        if flag:
            print(f"DROP TABLE {get_table_col_name(key, dialect)}")
        flag, res = sql_execute(dialect, get_empty_db_name(db_name), f'DROP TABLE {get_table_col_name(key, dialect)};')
        if flag:
            print(f"DROP TABLE {get_table_col_name(key, dialect)}")


# sql = """
# CREATE TABLE name (
# 	id NUMBER  NOT NULL,
# 	name VARCHAR2(4000)  NOT NULL,
# 	imdb_index VARCHAR2(12) ,
# 	imdb_id NUMBER ,
# 	gender VARCHAR2(1) ,
# 	name_pcode_cf VARCHAR2(5) ,
# 	name_pcode_nf VARCHAR2(5) ,
# 	surname_pcode VARCHAR2(5) ,
# 	md5sum VARCHAR2(32) ,
# 	CONSTRAINT PK_name PRIMARY KEY (id)
# );
# """
#
# print(oracle_sql_execute(get_all_db_name('oracle'), sql))