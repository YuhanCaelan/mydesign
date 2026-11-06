from datetime import date, time
from pydantic import BaseModel, Field, model_validator


class DoctorView(BaseModel):
    id: int
    doctor_no: str
    full_name: str
    department_id: int
    department_name: str
    title: str
    specialty: str
    introduction: str
    is_available: bool


class ScheduleCreate(BaseModel):
    doctor_id: int = Field(gt=0)
    schedule_date: date
    start_time: time
    end_time: time
    slot_minutes: int = Field(default=30, ge=10, le=120)

    @model_validator(mode="after")
    def check_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class ScheduleView(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    doctor_title: str
    department_id: int
    department_name: str
    schedule_date: date
    start_time: time
    end_time: time
    slot_minutes: int
    is_active: bool
    total_slots: int
    available_slots: int


class SlotView(BaseModel):
    id: int
    schedule_id: int
    schedule_date: date
    start_time: time
    end_time: time
    status: str


class AppointmentCreate(BaseModel):
    slot_id: int = Field(gt=0)
    reason: str = Field(min_length=2, max_length=300)


class AppointmentStatusUpdate(BaseModel):
    status: str = Field(pattern="^(pending|in_progress|completed|cancelled|no_show)$")


class AppointmentView(BaseModel):
    id: int
    appointment_no: str
    patient_id: int
    patient_name: str
    doctor_id: int
    doctor_name: str
    department_name: str
    visit_date: date
    start_time: time
    end_time: time
    reason: str
    status: str
    created_at: str
