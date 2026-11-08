"""
Error response schemas for API error handling.

Provides standardized error response format.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Additional error details."""

    model_config = ConfigDict(extra="allow")

    field: Optional[str] = Field(None, description="Field name if applicable")
    message: Optional[str] = Field(None, description="Detailed error message")


class ErrorResponse(BaseModel):
    """Standardized error response format."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "NOT_FOUND",
                "message": "Job not found",
                "details": {
                    "job_id": 123
                }
            }
        }
    )

    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional context about the error"
    )
