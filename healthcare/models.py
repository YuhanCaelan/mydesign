from decimal import Decimal
from pathlib import Path
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator,MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN='admin','管理员';DOCTOR='doctor','医师';PATIENT='patient','患者'
    role=models.CharField('角色',max_length=12,choices=Role.choices)
    phone=models.CharField('手机号码',max_length=20,blank=True)
    avatar=models.ImageField('头像',upload_to='avatars/%Y/%m/',blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    def save(self,*args,**kwargs):
        if self.is_superuser:self.role=self.Role.ADMIN
        super().save(*args,**kwargs)


class TimeStampedModel(models.Model):
    created_at=models.DateTimeField(auto_now_add=True);updated_at=models.DateTimeField(auto_now=True)
    class Meta:abstract=True


class Department(TimeStampedModel):
    class Status(models.TextChoices):ACTIVE='active','启用';INACTIVE='inactive','停用'
    name=models.CharField('科室名称',max_length=80,unique=True)
    description=models.TextField('科室介绍',blank=True)
    status=models.CharField(max_length=10,choices=Status.choices,default=Status.ACTIVE,db_index=True)
    class Meta:ordering=['name']
    def __str__(self):return self.name


class DoctorProfile(TimeStampedModel):
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='doctor_profile',limit_choices_to={'role':User.Role.DOCTOR})
    doctor_no=models.CharField(max_length=20,unique=True,blank=True)
    department=models.ForeignKey(Department,on_delete=models.PROTECT,related_name='doctors')
    departments=models.ManyToManyField(Department,blank=True,related_name='member_doctors')
    title=models.CharField('职称',max_length=80,blank=True)
    specialty=models.CharField('专业方向',max_length=200,blank=True)
    introduction=models.TextField('个人介绍',blank=True)
    is_available=models.BooleanField(default=True)
    is_super_doctor=models.BooleanField(default=False,help_text='演示用全科医师，可参与全部科室业务。')
    def save(self,*args,**kwargs):
        if self.user_id and self.user.role!=User.Role.DOCTOR:raise ValidationError('医师档案只能关联医师账号。')
        fresh=self.pk is None;super().save(*args,**kwargs)
        if fresh and not self.doctor_no:self.doctor_no=f'D{self.pk:06d}';type(self).objects.filter(pk=self.pk).update(doctor_no=self.doctor_no)
    def __str__(self):return f'{self.user.get_full_name()} ({self.doctor_no})'


class PatientProfile(TimeStampedModel):
    class Gender(models.TextChoices):MALE='male','男';FEMALE='female','女';OTHER='other','其他';UNKNOWN='unknown','未填写'
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='patient_profile',limit_choices_to={'role':User.Role.PATIENT})
    patient_no=models.CharField(max_length=20,unique=True,blank=True)
    gender=models.CharField(max_length=10,choices=Gender.choices,default=Gender.UNKNOWN)
    birth_date=models.DateField(null=True,blank=True)
    address=models.CharField(max_length=300,blank=True)
    blood_group=models.CharField(max_length=8,blank=True)
    allergies=models.TextField(blank=True)
    medical_history=models.TextField(blank=True)
    emergency_contact_name=models.CharField(max_length=80,blank=True)
    emergency_contact_phone=models.CharField(max_length=20,blank=True)
    def save(self,*args,**kwargs):
        if self.user_id and self.user.role!=User.Role.PATIENT:raise ValidationError('患者档案只能关联患者账号。')
        fresh=self.pk is None;super().save(*args,**kwargs)
        if fresh and not self.patient_no:self.patient_no=f'P{self.pk:06d}';type(self).objects.filter(pk=self.pk).update(patient_no=self.patient_no)
    def __str__(self):return f'{self.user.get_full_name()} ({self.patient_no})'


class DoctorSchedule(TimeStampedModel):
    doctor=models.ForeignKey(DoctorProfile,on_delete=models.CASCADE,related_name='schedules')
    date=models.DateField(db_index=True)
    start_time=models.TimeField();end_time=models.TimeField()
    slot_minutes=models.PositiveSmallIntegerField(default=30,validators=[MinValueValidator(5)])
    is_active=models.BooleanField(default=True)
    class Meta:
        ordering=['date','start_time'];constraints=[models.UniqueConstraint(fields=['doctor','date','start_time','end_time'],name='uq_doctor_schedule_period')]
    def clean(self):
        if self.start_time>=self.end_time:raise ValidationError({'end_time':'结束时间必须晚于开始时间。'})


class AppointmentSlot(TimeStampedModel):
    class Status(models.TextChoices):AVAILABLE='available','可预约';BOOKED='booked','已预约';CLOSED='closed','已关闭'
    schedule=models.ForeignKey(DoctorSchedule,on_delete=models.CASCADE,related_name='slots')
    start_time=models.TimeField();end_time=models.TimeField()
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.AVAILABLE,db_index=True)
    class Meta:
        ordering=['schedule__date','start_time'];constraints=[models.UniqueConstraint(fields=['schedule','start_time','end_time'],name='uq_schedule_slot_period')]
    def clean(self):
        if self.start_time>=self.end_time:raise ValidationError({'end_time':'号源结束时间必须晚于开始时间。'})


class Appointment(TimeStampedModel):
    class Status(models.TextChoices):PENDING='pending','待就诊';IN_PROGRESS='in_progress','就诊中';COMPLETED='completed','已完成';CANCELLED='cancelled','已取消';NO_SHOW='no_show','爽约'
    appointment_no=models.CharField(max_length=24,unique=True,blank=True)
    patient=models.ForeignKey(PatientProfile,on_delete=models.PROTECT,related_name='appointments')
    doctor=models.ForeignKey(DoctorProfile,on_delete=models.PROTECT,related_name='appointments')
    department=models.ForeignKey(Department,on_delete=models.PROTECT,null=True,blank=True,related_name='appointments',verbose_name='预约科室快照')
    slot=models.ForeignKey(AppointmentSlot,on_delete=models.PROTECT,related_name='appointments')
    status=models.CharField(max_length=16,choices=Status.choices,default=Status.PENDING,db_index=True)
    reason=models.TextField();cancelled_at=models.DateTimeField(null=True,blank=True);completed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['-slot__schedule__date','-slot__start_time']
        indexes=[models.Index(fields=['patient','status'],name='idx_appointment_patient_status'),models.Index(fields=['doctor','status'],name='idx_appointment_doctor_status'),models.Index(fields=['department','status'],name='idx_appointment_dept_status'),models.Index(fields=['status','created_at'],name='idx_appointment_status_created')]
        constraints=[models.UniqueConstraint(fields=['slot'],condition=models.Q(status__in=['pending','in_progress','completed']),name='uq_active_appointment_slot')]
    def save(self,*args,**kwargs):
        if self.department_id is None and self.doctor_id:self.department_id=self.doctor.department_id
        fresh=self.pk is None;super().save(*args,**kwargs)
        if fresh and not self.appointment_no:self.appointment_no=f'A{timezone.localdate():%Y%m%d}{self.pk:06d}';type(self).objects.filter(pk=self.pk).update(appointment_no=self.appointment_no)


class MedicalRecord(TimeStampedModel):
    class Status(models.TextChoices):DRAFT='draft','草稿';CONFIRMED='confirmed','已确认'
    record_no=models.CharField(max_length=24,unique=True,blank=True)
    appointment=models.OneToOneField(Appointment,on_delete=models.PROTECT,related_name='medical_record')
    chief_complaint=models.TextField();present_illness=models.TextField(blank=True);past_history=models.TextField(blank=True)
    examination=models.TextField(blank=True);diagnosis=models.TextField();treatment=models.TextField(blank=True)
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.DRAFT,db_index=True)
    confirmed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['-updated_at']
        indexes=[models.Index(fields=['status','confirmed_at'],name='idx_medrec_status_confirmed')]
    def save(self,*args,**kwargs):
        if self.pk:
            old=type(self).objects.filter(pk=self.pk).first()
            protected=('chief_complaint','present_illness','past_history','examination','diagnosis','treatment','appointment_id')
            if old and old.status==self.Status.CONFIRMED and any(getattr(old,f)!=getattr(self,f) for f in protected):raise ValidationError('已确认病历不可覆盖，请追加更正说明。')
        fresh=self.pk is None;super().save(*args,**kwargs)
        if fresh and not self.record_no:self.record_no=f'MR{timezone.localdate():%Y%m%d}{self.pk:06d}';type(self).objects.filter(pk=self.pk).update(record_no=self.record_no)


class MedicalRecordCorrection(models.Model):
    record=models.ForeignKey(MedicalRecord,on_delete=models.CASCADE,related_name='corrections')
    author=models.ForeignKey(User,on_delete=models.PROTECT,related_name='record_corrections')
    content=models.TextField();created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=['created_at']


class Medicine(TimeStampedModel):
    name=models.CharField(max_length=120);specification=models.CharField(max_length=100,blank=True);unit=models.CharField(max_length=30,default='盒')
    price=models.DecimalField(max_digits=10,decimal_places=2,default=0);stock=models.PositiveIntegerField(default=0);is_active=models.BooleanField(default=True)
    class Meta:ordering=['name'];constraints=[models.UniqueConstraint(fields=['name','specification'],name='uq_medicine_specification')]


class MedicineStockMovement(models.Model):
    class Type(models.TextChoices):RECEIPT='receipt','入库';ADJUSTMENT='adjustment','人工调整';DISPENSE='dispense','处方发药'
    medicine=models.ForeignKey(Medicine,on_delete=models.PROTECT,related_name='stock_movements')
    movement_type=models.CharField(max_length=16,choices=Type.choices)
    quantity=models.IntegerField(help_text='入库为正数，出库为负数。')
    balance_after=models.PositiveIntegerField()
    prescription=models.ForeignKey('Prescription',on_delete=models.PROTECT,null=True,blank=True,related_name='stock_movements')
    operator=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True,related_name='medicine_stock_movements')
    note=models.CharField(max_length=200,blank=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    class Meta:ordering=['-created_at','-id']


class Prescription(TimeStampedModel):
    class Status(models.TextChoices):ISSUED='issued','待缴费取药';DISPENSED='dispensed','已取药';CANCELLED='cancelled','已作废'
    prescription_no=models.CharField(max_length=24,unique=True,blank=True)
    record=models.ForeignKey(MedicalRecord,on_delete=models.PROTECT,related_name='prescriptions')
    doctor=models.ForeignKey(DoctorProfile,on_delete=models.PROTECT,related_name='prescriptions')
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.ISSUED,db_index=True);notes=models.TextField(blank=True);dispensed_at=models.DateTimeField(null=True,blank=True)
    class Meta:ordering=['-created_at']
    def save(self,*args,**kwargs):
        fresh=self.pk is None;super().save(*args,**kwargs)
        if fresh and not self.prescription_no:self.prescription_no=f'RX{timezone.localdate():%Y%m%d}{self.pk:06d}';type(self).objects.filter(pk=self.pk).update(prescription_no=self.prescription_no)


class PrescriptionItem(models.Model):
    prescription=models.ForeignKey(Prescription,on_delete=models.CASCADE,related_name='items')
    medicine=models.ForeignKey(Medicine,on_delete=models.PROTECT,related_name='prescription_items')
    dosage=models.CharField(max_length=80);frequency=models.CharField(max_length=80);duration=models.CharField(max_length=80,blank=True)
    quantity=models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price_snapshot=models.DecimalField('开具时单价',max_digits=10,decimal_places=2,null=True,blank=True,help_text='历史处方可能为空，展示时回退到原账单总额。')


class ExaminationItem(TimeStampedModel):
    class Category(models.TextChoices):LAB='lab','检验';IMAGING='imaging','影像';FUNCTION='function','功能检查';OTHER='other','其他'
    name=models.CharField(max_length=120,unique=True)
    category=models.CharField(max_length=16,choices=Category.choices)
    price=models.DecimalField(max_digits=10,decimal_places=2,validators=[MinValueValidator(0)])
    is_active=models.BooleanField(default=True,db_index=True)
    description=models.CharField(max_length=300,blank=True)
    class Meta:ordering=['category','name']
    def __str__(self):return self.name


class ExaminationOrder(TimeStampedModel):
    class Type(models.TextChoices):BLOOD='blood','血液检查';LAB='lab','常规检验';XRAY='xray','X-Ray';CT='ct','CT';MRI='mri','MRI';OTHER='other','其他检查'
    class Status(models.TextChoices):REQUESTED='requested','已申请';IN_PROGRESS='in_progress','检查中';COMPLETED='completed','报告待发布';PUBLISHED='published','已发布';CANCELLED='cancelled','已取消'
    order_no=models.CharField(max_length=24,unique=True,blank=True)
    patient=models.ForeignKey(PatientProfile,on_delete=models.PROTECT,related_name='examination_orders')
    doctor=models.ForeignKey(DoctorProfile,on_delete=models.PROTECT,related_name='examination_orders')
    record=models.ForeignKey(MedicalRecord,on_delete=models.PROTECT,related_name='examination_orders')
    item=models.ForeignKey(ExaminationItem,on_delete=models.PROTECT,null=True,blank=True,related_name='orders')
    item_name_snapshot=models.CharField(max_length=120,blank=True)
    price_snapshot=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    type=models.CharField(max_length=12,choices=Type.choices);status=models.CharField(max_length=16,choices=Status.choices,default=Status.REQUESTED,db_index=True)
    clinical_question=models.TextField();completed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['-created_at']
        indexes=[models.Index(fields=['patient','status'],name='idx_examorder_patient_status'),models.Index(fields=['created_at'],name='idx_examorder_created')]
    def save(self,*args,**kwargs):
        fresh=self.pk is None;super().save(*args,**kwargs)
        if fresh and not self.order_no:self.order_no=f'EX{timezone.localdate():%Y%m%d}{self.pk:06d}';type(self).objects.filter(pk=self.pk).update(order_no=self.order_no)


class ExaminationReport(TimeStampedModel):
    class Status(models.TextChoices):DRAFT='draft','草稿';PUBLISHED='published','已发布'
    order=models.OneToOneField(ExaminationOrder,on_delete=models.PROTECT,related_name='report')
    findings=models.TextField();conclusion=models.TextField();status=models.CharField(max_length=12,choices=Status.choices,default=Status.DRAFT)
    published_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True,related_name='published_reports');published_at=models.DateTimeField(null=True,blank=True)


def medical_file_path(instance,filename):return f'examinations/{instance.order_id}/{timezone.localdate():%Y/%m}/{Path(filename).name}'
class MedicalFile(models.Model):
    order=models.ForeignKey(ExaminationOrder,on_delete=models.CASCADE,related_name='files')
    file=models.FileField(upload_to=medical_file_path,validators=[FileExtensionValidator(['jpg','jpeg','png','pdf','dcm','nii','gz'])])
    original_name=models.CharField(max_length=255);file_type=models.CharField(max_length=30);size=models.PositiveBigIntegerField()
    uploaded_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name='medical_files');uploaded_at=models.DateTimeField(auto_now_add=True)


class BillingRecord(TimeStampedModel):
    class Status(models.TextChoices):UNPAID='unpaid','待缴费';PAID='paid','已缴费';CANCELLED='cancelled','已取消'
    class Category(models.TextChoices):REGISTRATION='registration','挂号费';EXAMINATION='examination','检查费';MEDICINE='medicine','药品费';INPATIENT='inpatient','住院费';OTHER='other','其他'
    bill_no=models.CharField(max_length=24,unique=True,blank=True)
    patient=models.ForeignKey(PatientProfile,on_delete=models.PROTECT,related_name='billing_records');appointment=models.ForeignKey(Appointment,on_delete=models.PROTECT,null=True,blank=True,related_name='billing_records');prescription=models.OneToOneField(Prescription,on_delete=models.PROTECT,null=True,blank=True,related_name='billing_record')
    examination=models.OneToOneField(ExaminationOrder,on_delete=models.PROTECT,null=True,blank=True,related_name='billing_record')
    admission=models.OneToOneField('InpatientAdmission',on_delete=models.PROTECT,null=True,blank=True,related_name='billing_record')
    inpatient_admission=models.ForeignKey('InpatientAdmission',on_delete=models.PROTECT,null=True,blank=True,related_name='charges',verbose_name='所属住院')
    category=models.CharField(max_length=20,choices=Category.choices,default=Category.OTHER);description=models.CharField(max_length=200);amount=models.DecimalField(max_digits=10,decimal_places=2);status=models.CharField(max_length=12,choices=Status.choices,default=Status.UNPAID)
    payment_method=models.CharField(max_length=30,blank=True);paid_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['-created_at'];constraints=[models.CheckConstraint(condition=models.Q(amount__gte=0),name='ck_billing_amount_non_negative')]
        indexes=[models.Index(fields=['patient','category','created_at'],name='idx_billing_patient_cat_date'),models.Index(fields=['status','created_at'],name='idx_billing_status_created'),models.Index(fields=['inpatient_admission'],name='idx_billing_admission')]
    def save(self,*args,**kwargs):
        fresh=self.pk is None;super().save(*args,**kwargs)
        if fresh and not self.bill_no:self.bill_no=f'BL{timezone.localdate():%Y%m%d}{self.pk:06d}';type(self).objects.filter(pk=self.pk).update(bill_no=self.bill_no)
    @property
    def days_admitted(self):return self.admission.days_admitted if self.admission_id else None


class WardBed(TimeStampedModel):
    department=models.ForeignKey(Department,on_delete=models.PROTECT,related_name='ward_beds')
    ward_name=models.CharField(max_length=80)
    bed_no=models.CharField(max_length=30)
    daily_rate=models.DecimalField(max_digits=10,decimal_places=2,validators=[MinValueValidator(0)])
    is_active=models.BooleanField(default=True,db_index=True)
    is_occupied=models.BooleanField(default=False,db_index=True)
    class Meta:
        ordering=['department__name','ward_name','bed_no'];constraints=[models.UniqueConstraint(fields=['ward_name','bed_no'],name='uq_ward_bed_number')]
    def __str__(self):return f'{self.ward_name}-{self.bed_no}'


class InpatientAdmission(TimeStampedModel):
    class Status(models.TextChoices):PENDING='pending','待入院';ADMITTED='admitted','住院中';DISCHARGED='discharged','已出院';CANCELLED='cancelled','已取消'
    admission_no=models.CharField(max_length=24,unique=True,blank=True)
    patient=models.ForeignKey(PatientProfile,on_delete=models.PROTECT,related_name='admissions')
    attending_doctor=models.ForeignKey(DoctorProfile,on_delete=models.PROTECT,related_name='admissions')
    department=models.ForeignKey(Department,on_delete=models.PROTECT,related_name='admissions')
    appointment=models.ForeignKey(Appointment,on_delete=models.PROTECT,null=True,blank=True,related_name='admissions')
    bed=models.ForeignKey(WardBed,on_delete=models.PROTECT,null=True,blank=True,related_name='admissions')
    ward=models.CharField(max_length=80);bed_no=models.CharField(max_length=30)
    daily_rate_snapshot=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    admission_diagnosis=models.TextField();discharge_summary=models.TextField(blank=True)
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.PENDING,db_index=True)
    admitted_at=models.DateTimeField(null=True,blank=True);discharged_at=models.DateTimeField(null=True,blank=True)
    class Meta:ordering=['-created_at']
    def save(self,*args,**kwargs):
        fresh=self.pk is None;super().save(*args,**kwargs)
        if fresh and not self.admission_no:self.admission_no=f'IP{timezone.localdate():%Y%m%d}{self.pk:06d}';type(self).objects.filter(pk=self.pk).update(admission_no=self.admission_no)
    @property
    def billable_days(self):
        if not self.admitted_at:return 0
        start=timezone.localtime(self.admitted_at).date()
        end=timezone.localtime(self.discharged_at).date() if self.discharged_at else timezone.localdate()
        return max(1,(end-start).days+1)
    @property
    def days_admitted(self):
        if self.status!=self.Status.ADMITTED or not self.admitted_at:return 0
        return max(1,(timezone.localdate()-timezone.localtime(self.admitted_at).date()).days+1)
    @property
    def projected_bed_fee(self):
        if self.status!=self.Status.ADMITTED:return Decimal('0')
        return self.daily_rate_snapshot*self.days_admitted


class AIService(TimeStampedModel):
    name=models.CharField(max_length=100);service_type=models.CharField(max_length=50,unique=True);description=models.TextField(blank=True)
    is_enabled=models.BooleanField(default=False);endpoint=models.URLField(blank=True)


class AIAnalysisTask(TimeStampedModel):
    class Status(models.TextChoices):PENDING='pending','等待中';RUNNING='running','分析中';SUCCEEDED='succeeded','已完成';FAILED='failed','失败';CANCELLED='cancelled','已取消'
    patient=models.ForeignKey(PatientProfile,on_delete=models.PROTECT,related_name='ai_tasks');file=models.ForeignKey(MedicalFile,on_delete=models.PROTECT,related_name='ai_tasks')
    service=models.ForeignKey(AIService,on_delete=models.PROTECT,related_name='tasks');created_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name='ai_tasks')
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.PENDING);result=models.JSONField(default=dict,blank=True);error_message=models.TextField(blank=True)


class AuditLog(models.Model):
    user=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='audit_logs');action=models.CharField(max_length=50)
    resource=models.CharField(max_length=100);object_id=models.CharField(max_length=64,blank=True);description=models.CharField(max_length=300,blank=True)
    ip_address=models.GenericIPAddressField(null=True,blank=True);created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    class Meta:ordering=['-created_at']
