from pydantic import BaseModel, Field


class StandupNoteGenerateRequest(BaseModel):
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    force: bool = False

