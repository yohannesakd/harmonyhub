"""add abac subject and resource dimensions

Revision ID: 20260330_0012
Revises: 20260330_0011
Create Date: 2026-03-30 04:25:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260330_0012"
down_revision: Union[str, None] = "20260330_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("department", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("grade_level", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("class_code", sa.String(length=64), nullable=True))

    op.add_column("directory_entries", sa.Column("department", sa.String(length=64), nullable=True))
    op.add_column("directory_entries", sa.Column("grade_level", sa.String(length=32), nullable=True))
    op.add_column("directory_entries", sa.Column("class_code", sa.String(length=64), nullable=True))
    op.create_index("ix_directory_entries_department", "directory_entries", ["department"])
    op.create_index("ix_directory_entries_grade_level", "directory_entries", ["grade_level"])
    op.create_index("ix_directory_entries_class_code", "directory_entries", ["class_code"])

    op.add_column("menu_items", sa.Column("department_scope", sa.String(length=64), nullable=True))
    op.add_column("menu_items", sa.Column("grade_scope", sa.String(length=32), nullable=True))
    op.add_column("menu_items", sa.Column("class_scope", sa.String(length=64), nullable=True))
    op.create_index("ix_menu_items_department_scope", "menu_items", ["department_scope"])
    op.create_index("ix_menu_items_grade_scope", "menu_items", ["grade_scope"])
    op.create_index("ix_menu_items_class_scope", "menu_items", ["class_scope"])

    op.add_column("abac_rules", sa.Column("subject_department", sa.String(length=64), nullable=True))
    op.add_column("abac_rules", sa.Column("subject_grade", sa.String(length=32), nullable=True))
    op.add_column("abac_rules", sa.Column("subject_class", sa.String(length=64), nullable=True))
    op.add_column("abac_rules", sa.Column("resource_department", sa.String(length=64), nullable=True))
    op.add_column("abac_rules", sa.Column("resource_grade", sa.String(length=32), nullable=True))
    op.add_column("abac_rules", sa.Column("resource_class", sa.String(length=64), nullable=True))
    op.add_column("abac_rules", sa.Column("resource_field", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("abac_rules", "resource_field")
    op.drop_column("abac_rules", "resource_class")
    op.drop_column("abac_rules", "resource_grade")
    op.drop_column("abac_rules", "resource_department")
    op.drop_column("abac_rules", "subject_class")
    op.drop_column("abac_rules", "subject_grade")
    op.drop_column("abac_rules", "subject_department")

    op.drop_index("ix_menu_items_class_scope", table_name="menu_items")
    op.drop_index("ix_menu_items_grade_scope", table_name="menu_items")
    op.drop_index("ix_menu_items_department_scope", table_name="menu_items")
    op.drop_column("menu_items", "class_scope")
    op.drop_column("menu_items", "grade_scope")
    op.drop_column("menu_items", "department_scope")

    op.drop_index("ix_directory_entries_class_code", table_name="directory_entries")
    op.drop_index("ix_directory_entries_grade_level", table_name="directory_entries")
    op.drop_index("ix_directory_entries_department", table_name="directory_entries")
    op.drop_column("directory_entries", "class_code")
    op.drop_column("directory_entries", "grade_level")
    op.drop_column("directory_entries", "department")

    op.drop_column("users", "class_code")
    op.drop_column("users", "grade_level")
    op.drop_column("users", "department")
