"""核心接口冒烟测试，使用临时 SQLite，不依赖开发者本机 MySQL。"""
import os
from datetime import date, time, timedelta

os.environ["DATABASE_URL"] = "sqlite:///./course_test.db"
os.environ["JWT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.main import app
from app.models import AppointmentSlot, Department, Doctor, DoctorSchedule, Patient, User


def setup_module():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    with SessionLocal() as db:
        admin=User(username="admin",password_hash=hash_password("Admin123!"),full_name="管理员",role="admin")
        doctor_user=User(username="doctor",password_hash=hash_password("Doctor123!"),full_name="张医生",role="doctor")
        patient_user=User(username="patient",password_hash=hash_password("Patient123!"),full_name="李患者",role="patient")
        department=Department(name="内科",description="测试科室",status="active")
        db.add_all([admin,doctor_user,patient_user,department]);db.flush()
        doctor=Doctor(user_id=doctor_user.id,department_id=department.id,doctor_no="D000001",title="主治医师",specialty="呼吸内科")
        patient=Patient(user_id=patient_user.id,patient_no="P000001",gender="male")
        db.add_all([doctor,patient]);db.flush()
        schedule=DoctorSchedule(doctor_id=doctor.id,schedule_date=date.today()+timedelta(days=1),start_time=time(9),end_time=time(10),slot_minutes=30)
        schedule.slots=[AppointmentSlot(start_time=time(9),end_time=time(9,30)),AppointmentSlot(start_time=time(9,30),end_time=time(10))]
        db.add(schedule);db.commit()


def token(username,password):
    response=client.post("/api/v1/auth/login",json={"username":username,"password":password})
    assert response.status_code==200,response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}


client=TestClient(app)


def test_login_pagination_and_dashboard():
    headers=token("admin","Admin123!")
    assert client.get("/api/v1/departments?page=1&page_size=10",headers=headers).json()["count"]==1
    assert client.get("/api/v1/dashboard",headers=headers).status_code==200


def test_patient_books_and_cancels_slot():
    headers=token("patient","Patient123!")
    schedules=client.get("/api/v1/schedules",headers=headers).json()["results"]
    slots=client.get(f"/api/v1/schedules/{schedules[0]['id']}/slots",headers=headers).json()
    created=client.post("/api/v1/appointments",headers=headers,json={"slot_id":slots[0]["id"],"reason":"咳嗽两天"})
    assert created.status_code==200,created.text
    appointment_id=created.json()["id"]
    cancelled=client.patch(f"/api/v1/appointments/{appointment_id}/status",headers=headers,json={"status":"cancelled"})
    assert cancelled.status_code==200,cancelled.text


def teardown_module():
    Base.metadata.drop_all(engine)
    if os.path.exists("course_test.db"): os.remove("course_test.db")
