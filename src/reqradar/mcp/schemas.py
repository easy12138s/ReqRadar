from pydantic import BaseModel, Field


class SearchRequirementsInput(BaseModel):
    project_id: int | None = Field(default=None, description="Filter by project ID")
    query: str | None = Field(default=None, description="Search text in title/content")
    limit: int = Field(default=10, ge=1, le=50, description="Max results")


class RequirementSummary(BaseModel):
    id: int
    project_id: int
    release_code: str
    version: int
    title: str
    content: str
    published_at: str | None


class RequirementDetail(BaseModel):
    id: int
    release_code: str
    version: int
    title: str
    content: str
    context_json: dict


class ProjectMemoryOutput(BaseModel):
    project_id: int
    memory: dict | None
