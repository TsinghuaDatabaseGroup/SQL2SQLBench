from db_builder.schema_builder import build_db, build_test_db

db_id = 'job'
for dialect in ['mysql', 'pg', 'oracle']:
    build_db(db_id, dialect, build_fk=False, all_flag=True, build_idx=True)
    build_test_db(db_id, dialect, all_flag=True)