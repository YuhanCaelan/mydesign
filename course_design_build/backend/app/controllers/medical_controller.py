from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.schemas import AppointmentCreate, AppointmentStatusUpdate, ScheduleCreate
from app.services import MedicalService

router=APIRouter(tags=["医疗业务"],dependencies=[Depends(get_current_user)])


@router.get("/doctors")
def doctors(page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=100),department_id:int|None=None,
            keyword:str="",db:Session=Depends(get_db)):
    return MedicalService(db).page_doctors(page,page_size,department_id,keyword)


@router.get("/schedules")
def schedules(page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=100),date_from:date|None=None,date_to:date|None=None,
              department_id:int|None=None,doctor_id:int|None=None,db:Session=Depends(get_db)):
    return MedicalService(db).page_schedules(page,page_size,date_from,date_to,department_id,doctor_id)


@router.post("/schedules",dependencies=[Depends(require_roles("admin","doctor"))])
def create_schedule(payload:ScheduleCreate,user=Depends(get_current_user),db:Session=Depends(get_db)):
    return MedicalService(db).create_schedule(payload,user)


@router.get("/schedules/{schedule_id}/slots")
def slots(schedule_id:int,db:Session=Depends(get_db)):
    return MedicalService(db).slots(schedule_id)


@router.get("/appointments")
def appointments(page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=100),status:str|None=None,
                 user=Depends(get_current_user),db:Session=Depends(get_db)):
    return MedicalService(db).page_appointments(page,page_size,user,status)


@router.post("/appointments",dependencies=[Depends(require_roles("patient"))])
def create_appointment(payload:AppointmentCreate,user=Depends(get_current_user),db:Session=Depends(get_db)):
    return MedicalService(db).create_appointment(payload,user)


@router.patch("/appointments/{appointment_id}/status")
def update_appointment(appointment_id:int,payload:AppointmentStatusUpdate,user=Depends(get_current_user),db:Session=Depends(get_db)):
    return MedicalService(db).update_status(appointment_id,payload.status,user)


@router.get("/dashboard")
def dashboard(db:Session=Depends(get_db)):
    return MedicalService(db).dashboard()
