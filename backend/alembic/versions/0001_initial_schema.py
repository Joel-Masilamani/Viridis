"""Initial Viridis schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hospitals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=True),
        sa.Column("beds", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hospitals_id"), "hospitals", ["id"], unique=False)

    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hospital_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_departments_id"), "departments", ["id"], unique=False)

    op.create_table(
        "compliance_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hospital_id", sa.Integer(), nullable=True),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_compliance_reports_id"), "compliance_reports", ["id"], unique=False)

    op.create_table(
        "benchmarks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hospital_id", sa.Integer(), nullable=True),
        sa.Column("peer_group", sa.String(length=100), nullable=True),
        sa.Column("metric", sa.String(length=50), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("ranking", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_benchmarks_id"), "benchmarks", ["id"], unique=False)

    op.create_table(
        "emissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hospital_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("subcategory", sa.String(length=30), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=10), nullable=True),
        sa.Column("emission_factor", sa.Float(), nullable=True),
        sa.Column("co2e", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_emissions_id"), "emissions", ["id"], unique=False)

    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hospital_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("date_earned", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_achievements_id"), "achievements", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_achievements_id"), table_name="achievements")
    op.drop_table("achievements")
    op.drop_index(op.f("ix_emissions_id"), table_name="emissions")
    op.drop_table("emissions")
    op.drop_index(op.f("ix_benchmarks_id"), table_name="benchmarks")
    op.drop_table("benchmarks")
    op.drop_index(op.f("ix_compliance_reports_id"), table_name="compliance_reports")
    op.drop_table("compliance_reports")
    op.drop_index(op.f("ix_departments_id"), table_name="departments")
    op.drop_table("departments")
    op.drop_index(op.f("ix_hospitals_id"), table_name="hospitals")
    op.drop_table("hospitals")
