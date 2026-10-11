from datetime import datetime,timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied,ValidationError
from .models import (Appointment,AppointmentSlot,AuditLog,BillingRecord,DoctorSchedule,
                     InpatientAdmission,Medicine,MedicineStockMovement,User,WardBed)

def audit(request,action,resource,obj=None,description=''):
    forwarded=request.META.get('HTTP_X_FORWARDED_FOR','').split(',')[0].strip()
    AuditLog.objects.create(user=request.user if request.user.is_authenticated else None,action=action,resource=resource,object_id=str(getattr(obj,'pk','') or ''),description=description,ip_address=forwarded or request.META.get('REMOTE_ADDR'))

def generate_slots(schedule:DoctorSchedule):
    schedule.full_clean()
    cursor=datetime.combine(schedule.date,schedule.start_time);end=datetime.combine(schedule.date,schedule.end_time)
    slots=[]
    while cursor+timedelta(minutes=schedule.slot_minutes)<=end:
        slot_end=cursor+timedelta(minutes=schedule.slot_minutes)
        slots.append(AppointmentSlot(schedule=schedule,start_time=cursor.time(),end_time=slot_end.time()))
        cursor=slot_end
    AppointmentSlot.objects.bulk_create(slots,ignore_conflicts=True)

@transaction.atomic
def book_appointment(*,patient,slot_id,reason):
    slot=AppointmentSlot.objects.select_for_update().select_related('schedule__doctor').get(pk=slot_id)
    if slot.status!=AppointmentSlot.Status.AVAILABLE or not slot.schedule.is_active:raise ValidationError('该号源已不可预约。')
    start=datetime.combine(slot.schedule.date,slot.start_time)
    if timezone.make_aware(start)<=timezone.now():raise ValidationError('不能预约已经开始的号源。')
    appointment=Appointment.objects.create(patient=patient,doctor=slot.schedule.doctor,slot=slot,reason=reason)
    slot.status=AppointmentSlot.Status.BOOKED;slot.save(update_fields=['status','updated_at'])
    return appointment

TRANSITIONS={
    'start':({Appointment.Status.PENDING},Appointment.Status.IN_PROGRESS),
    'complete':({Appointment.Status.IN_PROGRESS},Appointment.Status.COMPLETED),
    'cancel':({Appointment.Status.PENDING},Appointment.Status.CANCELLED),
    'no_show':({Appointment.Status.PENDING},Appointment.Status.NO_SHOW),
}
@transaction.atomic
def transition_appointment(*,appointment,user,action):
    appointment=Appointment.objects.select_for_update().select_related('doctor__user','patient__user','slot').get(pk=appointment.pk)
    if action not in TRANSITIONS:raise ValidationError('未知的预约操作。')
    allowed,target=TRANSITIONS[action]
    if appointment.status not in allowed:raise ValidationError('当前预约状态不允许执行此操作。')
    if action=='cancel' and user.role==User.Role.PATIENT and appointment.patient.user_id!=user.id:raise PermissionDenied('只能取消本人的预约。')
    if action in {'start','complete','no_show'} and (user.role!=User.Role.DOCTOR or appointment.doctor.user_id!=user.id):raise PermissionDenied('只能处理本人负责的预约。')
    appointment.status=target
    fields=['status','updated_at']
    if target==Appointment.Status.CANCELLED:
        appointment.cancelled_at=timezone.now();fields.append('cancelled_at');appointment.slot.status=AppointmentSlot.Status.AVAILABLE;appointment.slot.save(update_fields=['status','updated_at'])
    if target==Appointment.Status.COMPLETED:appointment.completed_at=timezone.now();fields.append('completed_at')
    appointment.save(update_fields=fields)
    return appointment

@transaction.atomic
def admit_patient(*,admission):
    admission=InpatientAdmission.objects.select_for_update().select_related('bed').get(pk=admission.pk)
    if admission.status!=InpatientAdmission.Status.PENDING:raise ValidationError('仅待入院记录可以办理入院。')
    if not admission.bed_id:raise ValidationError({'bed_id':'请选择床位。'})
    bed=WardBed.objects.select_for_update().get(pk=admission.bed_id)
    if not bed.is_active:raise ValidationError({'bed_id':'该床位已停用。'})
    if bed.is_occupied or InpatientAdmission.objects.filter(bed=bed,status=InpatientAdmission.Status.ADMITTED).exclude(pk=admission.pk).exists():raise ValidationError({'bed_id':'该床位已被占用。'})
    if bed.department_id!=admission.department_id:raise ValidationError({'bed_id':'床位与入院科室不匹配。'})
    admission.status=InpatientAdmission.Status.ADMITTED;admission.admitted_at=timezone.now();admission.ward=bed.ward_name;admission.bed_no=bed.bed_no;admission.daily_rate_snapshot=bed.daily_rate
    admission.save(update_fields=['status','admitted_at','ward','bed_no','daily_rate_snapshot','updated_at'])
    bed.is_occupied=True;bed.save(update_fields=['is_occupied','updated_at'])
    return admission

@transaction.atomic
def finish_admission(*,admission,summary='',cancel=False):
    admission=InpatientAdmission.objects.select_for_update().select_related('bed').get(pk=admission.pk)
    if cancel:
        if admission.status not in {InpatientAdmission.Status.PENDING,InpatientAdmission.Status.ADMITTED}:raise ValidationError('当前住院记录不可取消。')
        admission.status=InpatientAdmission.Status.CANCELLED
    else:
        if admission.status!=InpatientAdmission.Status.ADMITTED:raise ValidationError('仅住院中记录可以办理出院。')
        if not summary.strip():raise ValidationError({'discharge_summary':'请填写出院小结。'})
        admission.status=InpatientAdmission.Status.DISCHARGED;admission.discharge_summary=summary.strip();admission.discharged_at=timezone.now()
        start=timezone.localtime(admission.admitted_at).date() if admission.admitted_at else timezone.localdate();days=max(1,(timezone.localdate()-start).days+1);amount=admission.daily_rate_snapshot*days
        BillingRecord.objects.get_or_create(admission=admission,defaults={'patient':admission.patient,'appointment':admission.appointment,'category':BillingRecord.Category.INPATIENT,'description':f'{admission.ward}-{admission.bed_no} 住院 {days} 天','amount':amount})
    admission.save()
    if admission.bed_id:
        WardBed.objects.filter(pk=admission.bed_id).update(is_occupied=False,updated_at=timezone.now())
    return admission

def record_stock_movement(*,medicine,quantity,movement_type,operator=None,prescription=None,note=''):
    return MedicineStockMovement.objects.create(medicine=medicine,movement_type=movement_type,quantity=quantity,balance_after=medicine.stock,operator=operator,prescription=prescription,note=note)
