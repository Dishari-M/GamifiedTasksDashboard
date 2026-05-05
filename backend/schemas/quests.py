from pydantic import BaseModel, Field


class QuestGenerateRequest(BaseModel):
    quest_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    candidate_task_ids: list[int] | None = None
    max_quests: int = Field(default=5, ge=1, le=10)
    respect_working_today: bool = True
    from_missions: bool = False
    include_ai_reasoning: bool = True
    force: bool = False
