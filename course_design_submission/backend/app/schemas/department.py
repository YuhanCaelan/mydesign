from pydantic import BaseModel, ConfigDict, Field


class DepartmentSave(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=500)
    status: str = Field(default="active", pattern="^(active|inactive)$")


class DepartmentView(DepartmentSave):
    id: int
    model_config = ConfigDict(from_attributes=True)
