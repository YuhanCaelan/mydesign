from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Department


class DepartmentMapper:
    def __init__(self, db: Session): self.db = db
    def page(self, page: int, size: int, keyword: str = ""):
        condition = Department.name.contains(keyword) if keyword else True
        total = self.db.scalar(select(func.count()).select_from(Department).where(condition)) or 0
        rows = self.db.scalars(select(Department).where(condition).order_by(Department.id)
                               .offset((page - 1) * size).limit(size)).all()
        return total, rows
    def find(self, department_id: int): return self.db.get(Department, department_id)
    def find_by_name(self, name: str):
        return self.db.scalar(select(Department).where(Department.name == name))
    def save(self, entity: Department): self.db.add(entity); self.db.flush(); return entity
