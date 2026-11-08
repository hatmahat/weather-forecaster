"""
Constants Package

Domain constants organized by topic (one module per topic).

Import patterns:
    from app.constants.jobs import JobStatus, JobType, TriggerType
"""

# Re-export for convenience
from app.constants.jobs import JobStatus, JobType, TriggerType, TrainingStatus

__all__ = [
    # Jobs
    "JobStatus", "JobType", "TriggerType", "TrainingStatus",
]
