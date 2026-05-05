from pydantic import BaseModel, Field


class DailyOverviewGenerateRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    include_task_notes: bool = True
    include_meetings: bool = True
    force: bool = False


class WeeklyOverviewGenerateRequest(BaseModel):
    week_start: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    include_daily_overviews: bool = True
    include_task_notes: bool = True
    force: bool = False
