"""make evaluation foreign keys tenant-aware

Revision ID: 0002_tenant_aware_fks
Revises: 0001_eval_framework_tables
Create Date: 2026-11-20 16:10:00

The 0001 schema only checked ``suite_id`` in its composite foreign keys, so a
row could reference another tenant's suite as long as the UUID happened to
match.  This revision adds ``org_id`` and ``site_id`` to every cross-table
foreign key and backs the new tuples with matching unique constraints.

Read isolation (who may *see* a row) is still an application/RLS concern; this
revision only guarantees that rows cannot be *linked* across tenants.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_tenant_aware_fks"
down_revision: Union[str, Sequence[str], None] = "0001_eval_framework_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New unique keys required by the tenant-aware referenced tuples.
    op.create_unique_constraint(
        "uq_eval_suite_id_tenant",
        "eval_suite",
        ["id", "org_id", "site_id"],
    )
    op.create_unique_constraint(
        "uq_eval_case_id_suite_tenant",
        "eval_case",
        ["id", "suite_id", "org_id", "site_id"],
    )
    op.create_unique_constraint(
        "uq_eval_run_id_suite_tenant",
        "eval_run",
        ["id", "suite_id", "org_id", "site_id"],
    )

    # Drop the old FKs before their two-column unique keys.
    op.drop_constraint(
        "fk_eval_case_suite_id", "eval_case", type_="foreignkey"
    )
    op.drop_constraint("fk_eval_run_suite_id", "eval_run", type_="foreignkey")
    op.drop_constraint(
        "fk_eval_result_run", "eval_result", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_eval_result_case", "eval_result", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_eval_baseline_run", "eval_baseline", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_eval_baseline_suite", "eval_baseline", type_="foreignkey"
    )

    op.create_foreign_key(
        "fk_eval_case_suite_tenant",
        "eval_case",
        "eval_suite",
        ["suite_id", "org_id", "site_id"],
        ["id", "org_id", "site_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_eval_run_suite_tenant",
        "eval_run",
        "eval_suite",
        ["suite_id", "org_id", "site_id"],
        ["id", "org_id", "site_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_eval_result_run_tenant",
        "eval_result",
        "eval_run",
        ["run_id", "suite_id", "org_id", "site_id"],
        ["id", "suite_id", "org_id", "site_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_eval_result_case_tenant",
        "eval_result",
        "eval_case",
        ["case_id", "suite_id", "org_id", "site_id"],
        ["id", "suite_id", "org_id", "site_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_eval_baseline_run_tenant",
        "eval_baseline",
        "eval_run",
        ["run_id", "suite_id", "org_id", "site_id"],
        ["id", "suite_id", "org_id", "site_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_eval_baseline_suite_tenant",
        "eval_baseline",
        "eval_suite",
        ["suite_id", "org_id", "site_id"],
        ["id", "org_id", "site_id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint(
        "uq_eval_case_id_suite", "eval_case", type_="unique"
    )
    op.drop_constraint("uq_eval_run_id_suite", "eval_run", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_eval_case_id_suite", "eval_case", ["id", "suite_id"]
    )
    op.create_unique_constraint(
        "uq_eval_run_id_suite", "eval_run", ["id", "suite_id"]
    )

    op.drop_constraint(
        "fk_eval_baseline_suite_tenant", "eval_baseline", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_eval_baseline_run_tenant", "eval_baseline", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_eval_result_case_tenant", "eval_result", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_eval_result_run_tenant", "eval_result", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_eval_run_suite_tenant", "eval_run", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_eval_case_suite_tenant", "eval_case", type_="foreignkey"
    )

    op.create_foreign_key(
        "fk_eval_case_suite_id",
        "eval_case",
        "eval_suite",
        ["suite_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_eval_run_suite_id",
        "eval_run",
        "eval_suite",
        ["suite_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_eval_result_run",
        "eval_result",
        "eval_run",
        ["run_id", "suite_id"],
        ["id", "suite_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_eval_result_case",
        "eval_result",
        "eval_case",
        ["case_id", "suite_id"],
        ["id", "suite_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_eval_baseline_run",
        "eval_baseline",
        "eval_run",
        ["run_id", "suite_id"],
        ["id", "suite_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_eval_baseline_suite",
        "eval_baseline",
        "eval_suite",
        ["suite_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint(
        "uq_eval_suite_id_tenant", "eval_suite", type_="unique"
    )
    op.drop_constraint(
        "uq_eval_case_id_suite_tenant", "eval_case", type_="unique"
    )
    op.drop_constraint(
        "uq_eval_run_id_suite_tenant", "eval_run", type_="unique"
    )
