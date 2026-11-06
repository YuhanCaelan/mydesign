"""核心数据表 ORM 映射。

模型只描述数据结构和关系；查询放在 Mapper，业务规则放在 Service。
"""
from datetime import date, datetime, time
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "sys_user"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20), index=True)  # admin / doctor / patient
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Department(Base):
    __tablename__ = "department"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Doctor(Base):
    __tablename__ = "doctor"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("department.id"), index=True)
    doctor_no: Mapped[str] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(String(50), default="医师")
    specialty: Mapped[str] = mapped_column(String(200), default="")
    introduction: Mapped[str] = mapped_column(Text, default="")
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped[User] = relationship()
    department: Mapped[Department] = relationship()


class Patient(Base):
    __tablename__ = "patient"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), unique=True)
    patient_no: Mapped[str] = mapped_column(String(20), unique=True)
    gender: Mapped[str] = mapped_column(String(10), default="unknown")
    birth_date: Mapped[date | None] = mapped_column(Date)
    address: Mapped[str] = mapped_column(String(255), default="")
    allergies: Mapped[str] = mapped_column(Text, default="")
    user: Mapped[User] = relationship()


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedule"
    __table_args__ = (UniqueConstraint("doctor_id", "schedule_date", "start_time", "end_time", name="uq_doctor_schedule"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctor.id"), index=True)
    schedule_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    slot_minutes: Mapped[int] = mapped_column(default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    doctor: Mapped[Doctor] = relationship()
    slots: Mapped[list["AppointmentSlot"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")


class AppointmentSlot(Base):
    __tablename__ = "appointment_slot"
    __table_args__ = (UniqueConstraint("schedule_id", "start_time", "end_time", name="uq_schedule_slot"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("doctor_schedule.id"), index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String(20), default="available", index=True)
    schedule: Mapped[DoctorSchedule] = relationship(back_populates="slots")


class Appointment(Base):
    __tablename__ = "appointment"
    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_no: Mapped[str] = mapped_column(String(30), unique=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctor.id"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("department.id"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("appointment_slot.id"), index=True)
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    patient: Mapped[Patient] = relationship()
    doctor: Mapped[Doctor] = relationship()
    department: Mapped[Department] = relationship()
    slot: Mapped[AppointmentSlot] = relationship()


class MedicalRecord(Base):
    __tablename__ = "medical_record"
    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointment.id"), unique=True)
    chief_complaint: Mapped[str] = mapped_column(Text)
    diagnosis: Mapped[str] = mapped_column(Text)
    treatment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Medicine(Base):
    __tablename__ = "medicine"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    specification: Mapped[str] = mapped_column(String(100), default="")
    unit: Mapped[str] = mapped_column(String(20), default="盒")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    stock: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
