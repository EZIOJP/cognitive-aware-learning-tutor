"""Knowledge graph tables: kg_nodes, kg_edges, kg_embeddings, kg_observations."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_knowledge_graph"
down_revision: Union[str, None] = "0013_note_reading_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _insp().has_table(name)


def upgrade() -> None:
    if not _has_table("kg_nodes"):
        op.create_table(
            "kg_nodes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("label", sa.Text(), nullable=False),
            sa.Column("node_type", sa.Text(), server_default="concept", nullable=False),
            sa.Column("tag_path", sa.Text(), nullable=True),
            sa.Column("note_path", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=True),
        )
        op.create_index("ix_kg_nodes_user_label", "kg_nodes", ["user_id", "label"])
        op.create_index("ix_kg_nodes_tag_path", "kg_nodes", ["tag_path"])

    if not _has_table("kg_edges"):
        op.create_table(
            "kg_edges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("kg_nodes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_id", sa.Integer(), sa.ForeignKey("kg_nodes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("relation_type", sa.Text(), nullable=True),
            sa.Column("weight", sa.Float(), server_default="1.0", nullable=False),
        )
        op.create_index("ix_kg_edges_source", "kg_edges", ["source_id"])
        op.create_index("ix_kg_edges_target", "kg_edges", ["target_id"])

    if not _has_table("kg_embeddings"):
        op.create_table(
            "kg_embeddings",
            sa.Column("node_id", sa.Integer(), sa.ForeignKey("kg_nodes.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("vector_blob", sa.LargeBinary(), nullable=True),
            sa.Column("model_name", sa.Text(), nullable=True),
        )

    if not _has_table("kg_observations"):
        op.create_table(
            "kg_observations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("node_id", sa.Integer(), sa.ForeignKey("kg_nodes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("timestamp", sa.Integer(), nullable=True),
            sa.Column("interaction_type", sa.Text(), nullable=True),
            sa.Column("value", sa.Float(), nullable=True),
        )
        op.create_index("ix_kg_observations_node", "kg_observations", ["node_id"])
        op.create_index("ix_kg_observations_user", "kg_observations", ["user_id"])


def downgrade() -> None:
    for table in ("kg_observations", "kg_embeddings", "kg_edges", "kg_nodes"):
        if _has_table(table):
            op.drop_table(table)
