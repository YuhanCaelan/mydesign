from datetime import date, datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.mappers import MedicalMapper, UserMapper
from app.models import Appointment, AppointmentSlot, DoctorSchedule, User
from app.schemas import AppointmentCreate, ScheduleCreate

STATUS_LABELS = {"pending":"待就诊", "in_progress":"就诊中", "completed":"已完成", "cancelled":"已取消", "no_show":"爽约"}


class MedicalService:
    def __init__(self, db: Session): self.db, self.mapper, self.users = db, MedicalMapper(db), UserMapper(db)

    @staticmethod
    def doctor_view(row):
        return {"id":row.id,"doctor_no":row.doctor_no,"full_name":row.user.full_name,
                "department_id":row.department_id,"department_name":row.department.name,"title":row.title,
                "specialty":row.specialty,"introduction":row.introduction,"is_available":row.is_available}

    def page_doctors(self, page, size, department_id=None, keyword=""):
        count, rows = self.mapper.page_doctors(page,size,department_id,keyword)
        return {"count":count,"page":page,"page_size":size,"results":[self.doctor_view(x) for x in rows]}

    @staticmethod
    def schedule_view(row):
        available = sum(slot.status == "available" for slot in row.slots)
        return {"id":row.id,"doctor_id":row.doctor_id,"doctor_name":row.doctor.user.full_name,
                "doctor_title":row.doctor.title,"department_id":row.doctor.department_id,
                "department_name":row.doctor.department.name,"schedule_date":row.schedule_date,
                "start_time":row.start_time,"end_time":row.end_time,"slot_minutes":row.slot_minutes,
                "is_active":row.is_active,"total_slots":len(row.slots),"available_slots":available}

    def page_schedules(self,page,size,date_from=None,date_to=None,department_id=None,doctor_id=None):
        count,rows=self.mapper.page_schedules(page,size,date_from,date_to,department_id,doctor_id)
        return {"count":count,"page":page,"page_size":size,"results":[self.schedule_view(x) for x in rows]}

    def create_schedule(self,payload:ScheduleCreate,user:User):
        if payload.schedule_date < date.today(): raise HTTPException(400,"不能创建过去日期的排班")
        doctor=self.mapper.find_doctor(payload.doctor_id)
        if not doctor: raise HTTPException(404,"医师不存在")
        if user.role=="doctor" and doctor.user_id!=user.id:
            raise HTTPException(403,"医师只能创建自己的排班")
        if self.mapper.overlapping_schedule(payload.doctor_id,payload.schedule_date,payload.start_time,payload.end_time):
            raise HTTPException(400,"该医师在此时段已有排班")
        row=DoctorSchedule(**payload.model_dump()); cursor=datetime.combine(payload.schedule_date,payload.start_time)
        end=datetime.combine(payload.schedule_date,payload.end_time)
        while cursor+timedelta(minutes=payload.slot_minutes)<=end:
            finish=cursor+timedelta(minutes=payload.slot_minutes)
            row.slots.append(AppointmentSlot(start_time=cursor.time(),end_time=finish.time(),status="available"));cursor=finish
        self.mapper.save_schedule(row);self.db.commit()
        # 提交后重新加载关联对象，保证医师、科室和号源统计都已准备好。
        return self.schedule_view(self.mapper.find_schedule(row.id))

    def slots(self,schedule_id):
        schedule=self.mapper.find_schedule(schedule_id)
        if not schedule or not schedule.is_active: raise HTTPException(404,"排班不存在或已关闭")
        now=datetime.now()
        return [{"id":x.id,"schedule_id":x.schedule_id,"schedule_date":schedule.schedule_date,
                 "start_time":x.start_time,"end_time":x.end_time,"status":x.status}
                for x in self.mapper.available_slots(schedule_id)
                if datetime.combine(schedule.schedule_date,x.start_time)>now]

    def create_appointment(self,payload:AppointmentCreate,user:User):
        patient=self.users.find_patient_by_user(user.id)
        if not patient: raise HTTPException(403,"当前账号没有患者档案")
        try:
            slot=self.mapper.lock_slot(payload.slot_id)
            if not slot or slot.status!="available" or not slot.schedule.is_active:
                raise HTTPException(400,"该号源已不可预约")
            if datetime.combine(slot.schedule.schedule_date,slot.start_time)<=datetime.now():
                raise HTTPException(400,"不能预约已经开始的号源")
            # 微秒时间戳与患者编号组合，避免同一患者快速连续预约造成编号冲突。
            number=f"A{datetime.now():%Y%m%d%H%M%S%f}{patient.id:04d}"
            appointment=Appointment(appointment_no=number,patient_id=patient.id,doctor_id=slot.schedule.doctor_id,
                department_id=slot.schedule.doctor.department_id,slot_id=slot.id,reason=payload.reason,status="pending")
            slot.status="booked";self.mapper.save_appointment(appointment);self.db.commit()
            # 使用本次生成的主键精确查询，避免并发预约时返回其他患者的最新记录。
            return self.appointment_view(self.mapper.find_appointment_detail(appointment.id))
        except Exception:
            self.db.rollback();raise

    @staticmethod
    def appointment_view(row):
        return {"id":row.id,"appointment_no":row.appointment_no,"patient_id":row.patient_id,
                "patient_name":row.patient.user.full_name,"doctor_id":row.doctor_id,"doctor_name":row.doctor.user.full_name,
                "department_name":row.department.name,"visit_date":row.slot.schedule.schedule_date,
                "start_time":row.slot.start_time,"end_time":row.slot.end_time,"reason":row.reason,"status":row.status,
                "status_label":STATUS_LABELS.get(row.status,row.status),"created_at":row.created_at.isoformat()}

    def page_appointments(self,page,size,user,status=None):
        patient_id=doctor_id=None
        if user.role=="patient":
            profile=self.users.find_patient_by_user(user.id);patient_id=profile.id if profile else -1
        elif user.role=="doctor":
            profile=self.users.find_doctor_by_user(user.id);doctor_id=profile.id if profile else -1
        count,rows=self.mapper.page_appointments(page,size,patient_id,doctor_id,status)
        return {"count":count,"page":page,"page_size":size,"results":[self.appointment_view(x) for x in rows]}

    def update_status(self,appointment_id,new_status,user):
        row=self.mapper.find_appointment(appointment_id)
        if not row: raise HTTPException(404,"预约不存在")
        allowed={"pending":{"in_progress","cancelled","no_show"},"in_progress":{"completed"}}
        if new_status not in allowed.get(row.status,set()): raise HTTPException(400,"当前状态不允许此操作")
        if user.role=="patient" and new_status!="cancelled": raise HTTPException(403,"患者只能取消自己的待就诊预约")
        if user.role=="patient":
            profile=self.users.find_patient_by_user(user.id)
            if not profile or profile.id!=row.patient_id: raise HTTPException(403,"只能操作本人的预约")
        if user.role=="doctor":
            profile=self.users.find_doctor_by_user(user.id)
            if not profile or profile.id!=row.doctor_id: raise HTTPException(403,"医师只能操作自己的预约")
        row.status=new_status
        if new_status=="cancelled": row.slot.status="available"
        self.db.commit();return {"message":"预约状态更新成功"}

    def dashboard(self):
        return {"cards":self.mapper.dashboard_counts(),"appointment_status":self.mapper.appointment_status_stats()}
