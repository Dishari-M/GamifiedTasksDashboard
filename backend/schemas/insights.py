from pydantic import BaseModel, Field


class TodayInsightGenerateRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    include_tasks: bool = True
    include_calendar: bool = True
    include_notes: bool = True
    force: bool = False
