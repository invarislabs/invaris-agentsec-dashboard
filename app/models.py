from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    github_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    login: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Every account is on "free" at launch; see app/plans.py.
    plan: Mapped[str] = mapped_column(String(32), default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[List["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[List["Membership"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    tokens: Mapped[List["ApiToken"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    reports: Mapped[List["Report"]] = relationship(back_populates="project", cascade="all, delete-orphan",
                                                   passive_deletes=True)


class Membership(Base):
    """Who can see a project. At launch a project has one member, its owner; team members are planned."""
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class ApiToken(Base):
    """A project token for uploads from the CLI and CI. Only a SHA-256 hash is stored."""
    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="tokens")


class Report(Base):
    """One uploaded report.json or mcp-report.json. The summary columns are copied out of the report so
    lists and history never need to decompress the full document."""
    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_project_uploaded", "project_id", "uploaded_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    token_id: Mapped[Optional[str]] = mapped_column(ForeignKey("api_tokens.id", ondelete="SET NULL"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    kind: Mapped[str] = mapped_column(String(16))               # "test" or "mcp_scan"
    name: Mapped[str] = mapped_column(String(200))              # agent or MCP server name
    target: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    agentsec_version: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    policy_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    policy_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    scenarios: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    with_findings: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    errors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    not_observable: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    findings: Mapped[int] = mapped_column(Integer, default=0)
    critical: Mapped[int] = mapped_column(Integer, default=0)
    high: Mapped[int] = mapped_column(Integer, default=0)
    medium: Mapped[int] = mapped_column(Integer, default=0)
    low: Mapped[int] = mapped_column(Integer, default=0)

    branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    commit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ci_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    repository: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    traces_stripped: Mapped[bool] = mapped_column(Boolean, default=False)

    size_bytes: Mapped[int] = mapped_column(Integer, default=0)       # uncompressed JSON size
    content: Mapped[bytes] = mapped_column(LargeBinary)               # gzip-compressed report JSON

    project: Mapped[Project] = relationship(back_populates="reports")
