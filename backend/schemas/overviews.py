from pydantic import BaseModel, Field


class DailyOverviewSaveRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    meeting_minutes: int | None = Field(default=None, ge=0)
    focus_minutes: int | None = Field(default=None, ge=0)
    new_learnings: list[str] = Field(default_factory=list)
    went_well: list[str] = Field(default_factory=list)
    went_wrong: list[str] = Field(default_factory=list)
    summary: str = ""


class DailyOverviewGenerateRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    include_daily_overviews: bool = True
    include_task_notes: bool = True
    include_meetings: bool = True
    force: bool = False


class WeeklyOverviewGenerateRequest(BaseModel):
    week_start: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    include_daily_overviews: bool = True
    include_task_notes: bool = True
    force: bool = False
