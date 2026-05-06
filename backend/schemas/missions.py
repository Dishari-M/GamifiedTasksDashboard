from pydantic import BaseModel, Field


class MissionGenerateRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    candidate_task_ids: list[int] | None = None
    max_missions: int = Field(default=5, ge=1, le=10)
    include_ai_reasoning: bool = True
    force: bool = False
