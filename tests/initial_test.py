from sqlalchemy import UniqueConstraint, text
from agentkit.db import models
from agentkit.db.session import Base, engine

def test_core_registered():
    assert {'integrations', 'tool_schemas', 'eval_runs'} <= set(Base.metadata.tables)

def test_tool_schema_versioning_constraint():
    table = Base.metadata.tables['tool_schemas']
    uniq = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    assert any({col.name for col in c.columns} == {'integration_id', 'tool_name', 'version'} for c in uniq)

def test_eval_run_fk_targets_tool_schema():
    fks = Base.metadata.tables['eval_runs'].foreign_keys
    assert any(fk.target_fullname.startswith('tool_schemas.') for fk in fks)

def test_database_reachable():
    with engine.connect() as conn:
        assert conn.execute(text('SELECT 1')).scalar_one() == 1