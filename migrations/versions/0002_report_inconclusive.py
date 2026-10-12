"""reports.inconclusive: scenarios whose adversarial content never reached the agent (AgentSec 0.8.0)

Adds the column and fills it for runs already stored, from the stored report itself, so run lists and
history never show an inconclusive run as passed. Older reports have no inconclusive scenarios (0).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12 06:00:00
"""
import gzip
import json

from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

BATCH = 200


def _count(content: bytes) -> int:
    try:
        report = json.loads(gzip.decompress(content).decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return 0
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    value = summary.get("inconclusive")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return sum(1 for s in report.get("scenarios") or [] if isinstance(s, dict) and s.get("status") == "inconclusive")


def upgrade() -> None:
    op.add_column('reports', sa.Column('inconclusive', sa.Integer(), nullable=True))
    reports = sa.table('reports', sa.column('id', sa.String), sa.column('kind', sa.String),
                       sa.column('content', sa.LargeBinary), sa.column('inconclusive', sa.Integer))
    conn = op.get_bind()
    last = ""
    while True:
        rows = conn.execute(sa.select(reports.c.id, reports.c.content)
                            .where(reports.c.kind == 'test', reports.c.id > last)
                            .order_by(reports.c.id).limit(BATCH)).all()
        if not rows:
            break
        for rid, content in rows:
            conn.execute(reports.update().where(reports.c.id == rid).values(inconclusive=_count(content)))
        last = rows[-1][0]


def downgrade() -> None:
    op.drop_column('reports', 'inconclusive')
