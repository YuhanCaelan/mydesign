from datetime import date
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models import Appointment, AppointmentSlot, Department, Doctor, DoctorSchedule, Patient, User


class MedicalMapper:
    def __init__(self, db: Session): self.db = db

    def page_doctors(self, page, size, department_id=None, keyword=""):
        stmt = select(Doctor).options(joinedload(Doctor.user), joinedload(Doctor.department))
        if department_id: stmt = stmt.where(Doctor.department_id == department_id)
        if keyword: stmt = stmt.join(Doctor.user).where(User.full_name.contains(keyword) | Doctor.specialty.contains(keyword))
        count = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return count, self.db.scalars(stmt.order_by(Doctor.doctor_no).offset((page-1)*size).limit(size)).all()

    def find_doctor(self, doctor_id):
        return self.db.scalar(select(Doctor).options(joinedload(Doctor.user), joinedload(Doctor.department)).where(Doctor.id == doctor_id))

    def page_schedules(self, page, size, date_from=None, date_to=None, department_id=None, doctor_id=None):
        stmt = select(DoctorSchedule).options(joinedload(DoctorSchedule.doctor).joinedload(Doctor.user),
            joinedload(DoctorSchedule.doctor).joinedload(Doctor.department), selectinload(DoctorSchedule.slots))
        if date_from: stmt = stmt.where(DoctorSchedule.schedule_date >= date_from)
        if date_to: stmt = stmt.where(DoctorSchedule.schedule_date <= date_to)
        if department_id: stmt = stmt.join(DoctorSchedule.doctor).where(Doctor.department_id == department_id)
        if doctor_id: stmt = stmt.where(DoctorSchedule.doctor_id == doctor_id)
        count = self.db.scalar(select(func.count()).select_from(stmt.with_only_columns(DoctorSchedule.id).subquery())) or 0
        rows = self.db.scalars(stmt.order_by(DoctorSchedule.schedule_date, DoctorSchedule.start_time)
                               .offset((page-1)*size).limit(size)).unique().all()
        return count, rows

    def overlapping_schedule(self, doctor_id, day, start, end):
        return self.db.scalar(select(DoctorSchedule.id).where(DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.schedule_date == day, DoctorSchedule.start_time < end, DoctorSchedule.end_time > start))

    def save_schedule(self, schedule): self.db.add(schedule); self.db.flush(); return schedule
    def find_schedule(self, schedule_id):
        return self.db.scalar(select(DoctorSchedule).options(selectinload(DoctorSchedule.slots),
            joinedload(DoctorSchedule.doctor).joinedload(Doctor.user),
            joinedload(DoctorSchedule.doctor).joinedload(Doctor.department)).where(DoctorSchedule.id == schedule_id))

    def available_slots(self, schedule_id):
        return self.db.scalars(select(AppointmentSlot).join(AppointmentSlot.schedule)
            .where(AppointmentSlot.schedule_id == schedule_id, AppointmentSlot.status == "available",
                   DoctorSchedule.is_active.is_(True)).order_by(AppointmentSlot.start_time)).all()

    def lock_slot(self, slot_id):
        return self.db.scalar(select(AppointmentSlot).options(joinedload(AppointmentSlot.schedule)
            .joinedload(DoctorSchedule.doctor)).where(AppointmentSlot.id == slot_id).with_for_update())

    def save_appointment(self, appointment): self.db.add(appointment); self.db.flush(); return appointment
    def find_appointment(self, appointment_id): return self.db.get(Appointment, appointment_id)
    def find_appointment_detail(self, appointment_id):
        """加载预约详情及页面响应所需的所有关联对象。"""
        return self.db.scalar(select(Appointment).options(
            joinedload(Appointment.patient).joinedload(Patient.user),
            joinedload(Appointment.doctor).joinedload(Doctor.user),
            joinedload(Appointment.department),
            joinedload(Appointment.slot).joinedload(AppointmentSlot.schedule),
        ).where(Appointment.id == appointment_id))

    def page_appointments(self, page, size, patient_id=None, doctor_id=None, status=None):
        stmt = select(Appointment).options(joinedload(Appointment.patient).joinedload(Patient.user),
            joinedload(Appointment.doctor).joinedload(Doctor.user), joinedload(Appointment.department),
            joinedload(Appointment.slot).joinedload(AppointmentSlot.schedule))
        if patient_id: stmt = stmt.where(Appointment.patient_id == patient_id)
        if doctor_id: stmt = stmt.where(Appointment.doctor_id == doctor_id)
        if status: stmt = stmt.where(Appointment.status == status)
        count = self.db.scalar(select(func.count()).select_from(stmt.with_only_columns(Appointment.id).subquery())) or 0
        rows = self.db.scalars(stmt.order_by(Appointment.created_at.desc()).offset((page-1)*size).limit(size)).unique().all()
        return count, rows

    def dashboard_counts(self):
        today = date.today()
        return {
            "departments": self.db.scalar(select(func.count()).select_from(Department)) or 0,
            "doctors": self.db.scalar(select(func.count()).select_from(Doctor)) or 0,
            "patients": self.db.scalar(select(func.count()).select_from(Patient)) or 0,
            "today_appointments": self.db.scalar(select(func.count()).select_from(AppointmentSlot).join(AppointmentSlot.schedule)
                .join(Appointment, Appointment.slot_id == AppointmentSlot.id).where(DoctorSchedule.schedule_date == today)) or 0,
        }

    def appointment_status_stats(self):
        return [{"name": status, "value": count} for status, count in self.db.execute(
            select(Appointment.status, func.count()).group_by(Appointment.status)).all()]
