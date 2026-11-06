from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.schemas import DepartmentSave, DepartmentView, PageResult
from app.services import DepartmentService

router = APIRouter(prefix="/departments", tags=["科室管理"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=PageResult[DepartmentView])
def page(page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=100),keyword:str="",db:Session=Depends(get_db)):
    return DepartmentService(db).page(page,page_size,keyword)


@router.post("", response_model=DepartmentView, dependencies=[Depends(require_roles("admin"))])
def create(payload:DepartmentSave,db:Session=Depends(get_db)):
    return DepartmentService(db).save(payload)


@router.put("/{department_id}", response_model=DepartmentView, dependencies=[Depends(require_roles("admin"))])
def update(department_id:int,payload:DepartmentSave,db:Session=Depends(get_db)):
    return DepartmentService(db).save(payload,department_id)
