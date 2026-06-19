"""SQLAlchemy models for the knowledge graph tables."""

from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer, LargeBinary, Text

from backend.db.base import Base


class KgNode(Base):
    __tablename__ = "kg_nodes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    label = Column(Text, nullable=False)
    node_type = Column(Text, default="concept", nullable=False)
    tag_path = Column(Text, nullable=True)
    note_path = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(Integer, nullable=True)


class KgEdge(Base):
    __tablename__ = "kg_edges"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("kg_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("kg_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(Text, nullable=True)
    weight = Column(Float, default=1.0, nullable=False)


class KgEmbedding(Base):
    __tablename__ = "kg_embeddings"

    node_id = Column(Integer, ForeignKey("kg_nodes.id", ondelete="CASCADE"), primary_key=True)
    vector_blob = Column(LargeBinary, nullable=True)
    model_name = Column(Text, nullable=True)


class KgObservation(Base):
    __tablename__ = "kg_observations"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("kg_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp = Column(Integer, nullable=True)
    interaction_type = Column(Text, nullable=True)
    value = Column(Float, nullable=True)
