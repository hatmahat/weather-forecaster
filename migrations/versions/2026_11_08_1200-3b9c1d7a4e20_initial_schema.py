"""initial_schema

Revision ID: 3b9c1d7a4e20
Revises:
Create Date: 2026-11-08 12:00:00.000000

Creates the generic job-tracking tables used by the background job queue:
- jobs:           one row per queued/running/finished background job
- job_heartbeats: liveness records for running jobs (runtime hang detection);
                  separate table to avoid races with job status updates

Add your own domain tables in later revisions (`make migrate-new MSG='...'`).
"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3b9c1d7a4e20'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE `jobs` (
      `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
      `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      `trigger_user_id` INT,
      `trigger_type` VARCHAR(50) NOT NULL,
      `job_type` VARCHAR(50) NOT NULL,
      `status` ENUM('PENDING','IN_PROGRESS','SUCCESS','PARTIAL_SUCCESS','FAILED') NOT NULL,
      `error` LONGTEXT,
      `completed_at` TIMESTAMP NULL DEFAULT NULL,
      `job_metadata` JSON
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    op.execute("CREATE INDEX `jobs_index_status` ON `jobs` (`status`, `created_at`)")

    op.execute("""
    CREATE TABLE `job_heartbeats` (
      `job_id` BIGINT NOT NULL,
      `last_heartbeat` DATETIME NOT NULL,
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`job_id`),
      KEY `idx_last_heartbeat` (`last_heartbeat`),
      CONSTRAINT `fk_job_heartbeats_job_id` FOREIGN KEY (`job_id`) REFERENCES `jobs` (`id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)


def downgrade() -> None:
    # Drop in reverse order (job_heartbeats has a foreign key to jobs)
    op.execute("DROP TABLE IF EXISTS `job_heartbeats`")
    op.execute("DROP TABLE IF EXISTS `jobs`")
