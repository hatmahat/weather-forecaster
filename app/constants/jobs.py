"""Job-related constants and enums."""
from enum import Enum


class TriggerType(str, Enum):
    """Job trigger type constants"""
    API = "API"
    SCHEDULER = "SCHEDULER"
    MANUAL = "MANUAL"


class JobStatus(str, Enum):
    """Job status constants"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class TrainingStatus(str, Enum):
    """Training status constants for individual model training results"""
    OK = "ok"  # All models trained successfully
    PARTIAL = "partial"  # Some models trained successfully
    INSUFFICIENT_DATA = "insufficient_data"  # Not enough data to train
    FAILED = "failed"  # Training failed with errors


class JobType:
    """Job type constants. Add one entry per kind of background job."""
    EXAMPLE_TASK = "EXAMPLE_TASK"
