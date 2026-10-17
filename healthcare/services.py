from datetime import datetime,timedelta
from django.db import transaction
from django.db.models import Q
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
    appointment=Appointment.objects.create(patient=patient,doctor=slot.schedule.doctor,department=slot.schedule.doctor.department,slot=slot,reason=reason)
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
        days=admission.billable_days;amount=bed_fee_amount(admission=admission)
        BillingRecord.objects.get_or_create(admission=admission,defaults={'patient':admission.patient,'appointment':admission.appointment,'inpatient_admission':admission,'category':BillingRecord.Category.INPATIENT,'description':f'{admission.ward}-{admission.bed_no} 住院 {days} 天','amount':amount})
    admission.save()
    if admission.bed_id:
        WardBed.objects.filter(pk=admission.bed_id).update(is_occupied=False,updated_at=timezone.now())
    return admission

def record_stock_movement(*,medicine,quantity,movement_type,operator=None,prescription=None,note=''):
    return MedicineStockMovement.objects.create(medicine=medicine,movement_type=movement_type,quantity=quantity,balance_after=medicine.stock,operator=operator,prescription=prescription,note=note)

VALID_RELATIONSHIP_STATUSES=(Appointment.Status.PENDING,Appointment.Status.IN_PROGRESS,Appointment.Status.COMPLETED)

def has_doctor_patient_relationship(*,user,patient_id):
    """医师与患者的有效诊疗关系以未取消、未爽约的预约记录为准。"""
    return Appointment.objects.filter(doctor__user=user,patient_id=patient_id,status__in=VALID_RELATIONSHIP_STATUSES).exists()

def department_scope(department):
    """科室归属以预约时快照为准；历史预约缺少快照时回退到医师当前主科室。"""
    return Q(department=department)|Q(department__isnull=True,doctor__department=department)

def bed_fee_amount(*,admission):
    return admission.daily_rate_snapshot*admission.billable_days

def bed_status_key(bed,admission=None):
    """看板状态：住院中 / 停用 / 空闲，与卡片颜色和文字标签一一对应。"""
    if admission is not None or bed.is_occupied:return 'occupied'
    return 'inactive' if not bed.is_active else 'available'

def board_bed_payload(bed,admission=None):
    """单张床位卡片数据：位置（科室/病区/床号）、状态、日费与占用时的住院信息。"""
    status=bed_status_key(bed,admission)
    payload={'id':bed.pk,'department_id':bed.department_id,'department_name':bed.department.name,'ward_name':bed.ward_name,'bed_no':bed.bed_no,'display_name':str(bed),'daily_rate':str(bed.daily_rate),'is_active':bed.is_active,'is_occupied':bed.is_occupied,'status':status,'status_label':{'available':'空闲','occupied':'住院中','inactive':'停用'}[status],'data_warning':bool(bed.is_occupied and admission is None),'occupancy':None}
    if admission is not None:
        payload['occupancy']={'id':admission.pk,'admission_no':admission.admission_no,'patient_id':admission.patient_id,'patient_name':admission.patient.user.get_full_name(),'patient_no':admission.patient.patient_no,'doctor_name':admission.attending_doctor.user.get_full_name(),'admitted_at':admission.admitted_at.isoformat() if admission.admitted_at else None,'days_admitted':admission.days_admitted,'daily_rate_snapshot':str(admission.daily_rate_snapshot),'status_display':admission.get_status_display()}
    return payload

def ensure_admission_operator(*,admission,user):
    """住院状态变更（入院、出院、取消）仅管理员与该次住院的主治医师可执行。"""
    if user.role==User.Role.ADMIN:return
    if user.role==User.Role.DOCTOR and admission.attending_doctor.user_id==user.id:return
    if user.role==User.Role.DOCTOR:raise PermissionDenied('仅主治医师或管理员可以修改住院状态与办理出院。')
    raise PermissionDenied('无权修改住院状态。')

def link_inpatient(*,patient,admission_id=None,appointment=None):
    """为住院期间产生的费用确定所属住院：显式指定时严格校验，未指定时仅在唯一住院中时自动归集。"""
    if admission_id in (None,''):
        candidates=InpatientAdmission.objects.filter(patient=patient,status=InpatientAdmission.Status.ADMITTED)
        if appointment is not None:candidates=candidates.filter(Q(appointment=appointment)|Q(appointment__isnull=True))
        if candidates.count()==1:return candidates.first()
        return None
    try:admission=InpatientAdmission.objects.get(pk=admission_id)
    except (InpatientAdmission.DoesNotExist,ValueError,TypeError):raise ValidationError({'admission_id':'住院记录不存在。'})
    if admission.patient_id!=patient.pk:raise ValidationError({'admission_id':'住院记录与患者不匹配。'})
    if admission.status!=InpatientAdmission.Status.ADMITTED:raise ValidationError({'admission_id':'仅在院患者的费用可以归集到本次住院。'})
    return admission
