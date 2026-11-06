from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.mappers import DepartmentMapper
from app.models import Department
from app.schemas import DepartmentSave


class DepartmentService:
    def __init__(self, db: Session): self.db, self.mapper = db, DepartmentMapper(db)

    def page(self, page, size, keyword=""):
        count, rows = self.mapper.page(page, size, keyword)
        return {"count": count, "page": page, "page_size": size, "results": rows}

    def save(self, payload: DepartmentSave, department_id: int | None = None):
        entity = self.mapper.find(department_id) if department_id else Department()
        if entity is None: raise HTTPException(404, "科室不存在")
        duplicate = self.mapper.find_by_name(payload.name)
        if duplicate and duplicate.id != department_id: raise HTTPException(400, "科室名称已存在")
        for field, value in payload.model_dump().items(): setattr(entity, field, value)
        self.mapper.save(entity); self.db.commit(); self.db.refresh(entity)
        return entity
