from abc import ABC, abstractmethod
from typing import List


class BaseDialect(ABC):

    @abstractmethod
    def execute(self, db_name: str, sql: str, db_param=None, emp_flag=False, restart_flag=False):
        pass

    @abstractmethod
    def dependent_execute(self, db_name: str, sql: str, db_param=None):
        pass

    @abstractmethod
    def connect(self, db_name: str, restart_flag=False):
        pass

    @abstractmethod
    def close_connect(self, db_name: str):
        pass

    @abstractmethod
    def drop_db(self, db_name: str):
        pass

    @abstractmethod
    def show_databases(self):
        pass

    @abstractmethod
    def get_data_type(self, db_name: str, obj: str, is_table: bool, db_param: dict | None = None) -> tuple[bool, List]:
        pass

    @abstractmethod
    def test_sql(self, ddls: list[str], sql: str):
        pass

    @abstractmethod
    def create_table(self, table_schema, constraints):
        pass

    @abstractmethod
    def add_foreign_key(self, schema):
        pass

    @abstractmethod
    def add_index(self, schema):
        pass

    @abstractmethod
    def get_table_col_name(self, name):
        pass