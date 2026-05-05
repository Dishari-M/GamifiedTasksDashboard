from pydantic import BaseModel, Field


class WorkingTodayRequest(BaseModel):
    is_working_today: bool
    row_version: int = Field(..., ge=1)

