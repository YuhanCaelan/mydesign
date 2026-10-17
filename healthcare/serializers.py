from decimal import Decimal,InvalidOperation
from django.contrib.auth import authenticate,password_validation
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import *
from .services import book_appointment,generate_slots,link_inpatient

class SessionUserSerializer(serializers.ModelSerializer):
    full_name=serializers.SerializerMethodField();avatar=serializers.SerializerMethodField()
    class Meta:model=User;fields=('id','username','full_name','role','phone','email','avatar')
    def get_full_name(self,obj):return obj.get_full_name() or obj.username
    def get_avatar(self,obj):return self.context['request'].build_absolute_uri(obj.avatar.url) if obj.avatar and self.context.get('request') else None

class LoginSerializer(serializers.Serializer):
    username=serializers.CharField();password=serializers.CharField(write_only=True)
    def validate(self,attrs):
        user=authenticate(username=attrs['username'],password=attrs['password'])
        if not user or not user.is_active:raise serializers.ValidationError('用户名或密码错误。')
        token=RefreshToken.for_user(user);return{'access':str(token.access_token),'refresh':str(token),'user':SessionUserSerializer(user,context=self.context).data}

class RegisterSerializer(serializers.Serializer):
    username=serializers.CharField(max_length=150);password=serializers.CharField(write_only=True,min_length=8)
    password_confirm=serializers.CharField(write_only=True);full_name=serializers.CharField(max_length=80);phone=serializers.RegexField(r'^1\d{10}$')
    def validate_username(self,value):
        if User.objects.filter(username=value).exists():raise serializers.ValidationError('用户名已存在。')
        return value
    def validate(self,attrs):
        if attrs['password']!=attrs.pop('password_confirm'):raise serializers.ValidationError({'password_confirm':'两次输入的密码不一致。'})
        password_validation.validate_password(attrs['password']);return attrs
    @transaction.atomic
    def create(self,data):
        user=User.objects.create_user(username=data['username'],password=data['password'],first_name=data['full_name'],phone=data['phone'],role=User.Role.PATIENT)
        PatientProfile.objects.create(user=user);return user

class ChangePasswordSerializer(serializers.Serializer):
    current_password=serializers.CharField(write_only=True);new_password=serializers.CharField(write_only=True,min_length=8);new_password_confirm=serializers.CharField(write_only=True)
    def validate_current_password(self,value):
        if not self.context['request'].user.check_password(value):raise serializers.ValidationError('当前密码不正确。')
        return value
    def validate(self,attrs):
        if attrs['new_password']!=attrs['new_password_confirm']:raise serializers.ValidationError({'new_password_confirm':'两次输入的新密码不一致。'})
        password_validation.validate_password(attrs['new_password'],self.context['request'].user);return attrs

class DepartmentSerializer(serializers.ModelSerializer):
    status_display=serializers.CharField(source='get_status_display',read_only=True)
    class Meta:model=Department;fields='__all__';read_only_fields=('created_at','updated_at')

class DoctorSerializer(serializers.ModelSerializer):
    full_name=serializers.CharField(source='user.get_full_name',read_only=True);department_name=serializers.CharField(source='department.name',read_only=True);department_id=serializers.IntegerField(read_only=True);department_names=serializers.SerializerMethodField()
    class Meta:model=DoctorProfile;fields=('id','doctor_no','full_name','department_id','department_name','department_names','title','specialty','introduction','is_available','is_super_doctor');read_only_fields=('doctor_no','department_id','department_name','department_names','full_name','is_super_doctor')
    def get_department_names(self,obj):return list(obj.departments.values_list('name',flat=True)) or [obj.department.name]

class PatientSerializer(serializers.ModelSerializer):
    full_name=serializers.CharField(source='user.get_full_name',read_only=True);phone=serializers.CharField(source='user.phone',read_only=True);email=serializers.EmailField(source='user.email',read_only=True);gender_display=serializers.CharField(source='get_gender_display',read_only=True)
    username=serializers.CharField(source='user.username',read_only=True);user_id=serializers.IntegerField(read_only=True);is_active=serializers.BooleanField(source='user.is_active',read_only=True)
    class Meta:model=PatientProfile;fields=('id','user_id','username','patient_no','full_name','phone','email','is_active','gender','gender_display','birth_date','address','blood_group','allergies','medical_history','emergency_contact_name','emergency_contact_phone','created_at');read_only_fields=('patient_no','created_at')

class AdminUserSerializer(serializers.ModelSerializer):
    full_name=serializers.CharField(source='first_name');password=serializers.CharField(write_only=True,min_length=8,required=False)
    department_id=serializers.PrimaryKeyRelatedField(source='department',queryset=Department.objects.filter(status=Department.Status.ACTIVE),write_only=True,required=False)
    title=serializers.CharField(write_only=True,required=False,allow_blank=True);specialty=serializers.CharField(write_only=True,required=False,allow_blank=True)
    gender=serializers.ChoiceField(source='patient_gender',choices=PatientProfile.Gender.choices,write_only=True,required=False)
    birth_date=serializers.DateField(source='patient_birth_date',write_only=True,required=False,allow_null=True)
    address=serializers.CharField(source='patient_address',write_only=True,required=False,allow_blank=True)
    role_display=serializers.CharField(source='get_role_display',read_only=True);is_active_display=serializers.SerializerMethodField();doctor_no=serializers.SerializerMethodField();department_name=serializers.SerializerMethodField()
    patient_no=serializers.SerializerMethodField();doctor_id=serializers.SerializerMethodField();patient_id=serializers.SerializerMethodField();doctor_title=serializers.SerializerMethodField();doctor_specialty=serializers.SerializerMethodField()
    class Meta:model=User;fields=('id','username','full_name','password','role','role_display','phone','email','is_active','is_active_display','department_id','department_name','doctor_no','doctor_id','doctor_title','doctor_specialty','patient_no','patient_id','gender','birth_date','address','title','specialty','created_at');read_only_fields=('created_at',)
    def get_is_active_display(self,obj):return '启用' if obj.is_active else '禁用'
    def _doctor(self,obj):
        try:return obj.doctor_profile
        except DoctorProfile.DoesNotExist:return None
    def _patient(self,obj):
        try:return obj.patient_profile
        except PatientProfile.DoesNotExist:return None
    def get_doctor_no(self,obj):
        doctor=self._doctor(obj);return doctor.doctor_no if doctor else None
    def get_doctor_id(self,obj):
        doctor=self._doctor(obj);return doctor.pk if doctor else None
    def get_doctor_title(self,obj):
        doctor=self._doctor(obj);return doctor.title if doctor else None
    def get_doctor_specialty(self,obj):
        doctor=self._doctor(obj);return doctor.specialty if doctor else None
    def get_patient_no(self,obj):
        patient=self._patient(obj);return patient.patient_no if patient else None
    def get_patient_id(self,obj):
        patient=self._patient(obj);return patient.pk if patient else None
    def get_department_name(self,obj):
        doctor=self._doctor(obj);return doctor.department.name if doctor else None
    def validate_password(self,value):
        password_validation.validate_password(value);return value
    def validate(self,attrs):
        if self.instance is None and not attrs.get('password'):raise serializers.ValidationError({'password':'创建账户必须设置初始密码。'})
        if self.instance is None and attrs.get('role')==User.Role.DOCTOR and not attrs.get('department'):raise serializers.ValidationError({'department_id':'创建医师必须选择科室。'})
        if self.instance is None and attrs.get('role')==User.Role.ADMIN:raise serializers.ValidationError({'role':'不能通过接口创建管理员。'})
        return attrs
    @transaction.atomic
    def create(self,data):
        department=data.pop('department',None);title=data.pop('title','');specialty=data.pop('specialty','');password=data.pop('password',None)
        gender=data.pop('patient_gender',PatientProfile.Gender.UNKNOWN);birth_date=data.pop('patient_birth_date',None);address=data.pop('patient_address','')
        user=User.objects.create_user(password=password,**data)
        if user.role==User.Role.DOCTOR:
            doctor=DoctorProfile.objects.create(user=user,department=department,title=title,specialty=specialty);doctor.departments.add(department)
        elif user.role==User.Role.PATIENT:PatientProfile.objects.create(user=user,gender=gender,birth_date=birth_date,address=address)
        return user
    def update(self,user,data):
        department=data.pop('department',None);title=data.pop('title',None);specialty=data.pop('specialty',None);password=data.pop('password',None)
        gender=data.pop('patient_gender',None);birth_date=data.pop('patient_birth_date',None);address=data.pop('patient_address',None)
        if 'role' in data and data['role']!=user.role:raise serializers.ValidationError({'role':'已有账户不可直接更换角色。'})
        for key,value in data.items():setattr(user,key,value)
        if password:user.set_password(password)
        user.save()
        doctor=self._doctor(user)
        if doctor is not None:
            fields=[]
            if department is not None:doctor.department=department;fields.append('department');doctor.departments.add(department)
            if title is not None:doctor.title=title;fields.append('title')
            if specialty is not None:doctor.specialty=specialty;fields.append('specialty')
            if fields:doctor.save(update_fields=fields+['updated_at'])
        patient=self._patient(user)
        if patient is not None:
            fields=[]
            if gender is not None:patient.gender=gender;fields.append('gender')
            if birth_date is not None:patient.birth_date=birth_date;fields.append('birth_date')
            if address is not None:patient.address=address;fields.append('address')
            if fields:patient.save(update_fields=fields+['updated_at'])
        return user

class SlotSerializer(serializers.ModelSerializer):
    date=serializers.DateField(source='schedule.date',read_only=True);doctor_id=serializers.IntegerField(source='schedule.doctor_id',read_only=True)
    class Meta:model=AppointmentSlot;fields=('id','doctor_id','date','start_time','end_time','status')

class ScheduleSerializer(serializers.ModelSerializer):
    doctor_name=serializers.CharField(source='doctor.user.get_full_name',read_only=True);doctor_title=serializers.CharField(source='doctor.title',read_only=True);doctor_specialty=serializers.CharField(source='doctor.specialty',read_only=True);department_id=serializers.IntegerField(source='doctor.department_id',read_only=True);department_name=serializers.CharField(source='doctor.department.name',read_only=True)
    time_range=serializers.SerializerMethodField();total_slots=serializers.IntegerField(source='slots.count',read_only=True);available_slots=serializers.SerializerMethodField();booked_slots=serializers.SerializerMethodField()
    class Meta:model=DoctorSchedule;fields=('id','doctor','doctor_name','doctor_title','doctor_specialty','department_id','department_name','date','start_time','end_time','time_range','slot_minutes','is_active','total_slots','available_slots','booked_slots','created_at');read_only_fields=('created_at',)
    def get_time_range(self,obj):return f'{obj.start_time:%H:%M}–{obj.end_time:%H:%M}'
    def get_available_slots(self,obj):return obj.slots.filter(status=AppointmentSlot.Status.AVAILABLE).count()
    def get_booked_slots(self,obj):return obj.slots.filter(status=AppointmentSlot.Status.BOOKED).count()
    def validate(self,data):
        doctor=data.get('doctor',getattr(self.instance,'doctor',None));day=data.get('date',getattr(self.instance,'date',None));start=data.get('start_time',getattr(self.instance,'start_time',None));end=data.get('end_time',getattr(self.instance,'end_time',None))
        if day and day<timezone.localdate():raise serializers.ValidationError({'date':'不能创建过去日期的排班。'})
        if start and end and start>=end:raise serializers.ValidationError({'end_time':'结束时间必须晚于开始时间。'})
        overlap=DoctorSchedule.objects.filter(doctor=doctor,date=day,start_time__lt=end,end_time__gt=start)
        if self.instance:overlap=overlap.exclude(pk=self.instance.pk)
        if overlap.exists():raise serializers.ValidationError('该医师在此时间段已有排班。')
        return data
    def create(self,data):
        schedule=super().create(data);generate_slots(schedule);return schedule
    @transaction.atomic
    def update(self,instance,data):
        changed=any(field in data and data[field]!=getattr(instance,field) for field in ('date','start_time','end_time','slot_minutes'))
        if changed and instance.slots.filter(status=AppointmentSlot.Status.BOOKED).exists():raise serializers.ValidationError('已有预约的排班不能修改时间或号源时长。')
        schedule=super().update(instance,data)
        if changed:schedule.slots.all().delete();generate_slots(schedule)
        return schedule

class AppointmentSerializer(serializers.ModelSerializer):
    slot=SlotSerializer(read_only=True);slot_id=serializers.PrimaryKeyRelatedField(source='selected_slot',queryset=AppointmentSlot.objects.all(),write_only=True,required=False)
    patient_name=serializers.CharField(source='patient.user.get_full_name',read_only=True);patient_no=serializers.CharField(source='patient.patient_no',read_only=True);patient_phone=serializers.CharField(source='patient.user.phone',read_only=True);patient_gender_display=serializers.CharField(source='patient.get_gender_display',read_only=True);patient_allergies=serializers.CharField(source='patient.allergies',read_only=True)
    doctor_name=serializers.CharField(source='doctor.user.get_full_name',read_only=True);doctor_title=serializers.CharField(source='doctor.title',read_only=True);doctor_specialty=serializers.CharField(source='doctor.specialty',read_only=True);doctor_introduction=serializers.CharField(source='doctor.introduction',read_only=True)
    department_name=serializers.SerializerMethodField();status_display=serializers.CharField(source='get_status_display',read_only=True);visit_date=serializers.DateField(source='slot.schedule.date',read_only=True)
    record_id=serializers.SerializerMethodField();record_no=serializers.SerializerMethodField();record_status=serializers.SerializerMethodField();record_status_display=serializers.SerializerMethodField()
    class Meta:model=Appointment;fields=('id','appointment_no','patient_id','patient_name','patient_no','patient_phone','patient_gender_display','patient_allergies','doctor_id','doctor_name','doctor_title','doctor_specialty','doctor_introduction','department_id','department_name','slot','slot_id','visit_date','status','status_display','reason','record_id','record_no','record_status','record_status_display','created_at');read_only_fields=('appointment_no','status','created_at','department_id')
    def get_department_name(self,obj):return obj.department.name if obj.department_id else obj.doctor.department.name
    def _record(self,obj):
        try:return obj.medical_record
        except MedicalRecord.DoesNotExist:return None
    def get_record_id(self,obj):
        record=self._record(obj);return record.pk if record else None
    def get_record_no(self,obj):
        record=self._record(obj);return record.record_no if record else None
    def get_record_status(self,obj):
        record=self._record(obj);return record.status if record else None
    def get_record_status_display(self,obj):
        record=self._record(obj);return record.get_status_display() if record else None
    def create(self,data):
        slot=data.pop('selected_slot');return book_appointment(patient=self.context['request'].user.patient_profile,slot_id=slot.pk,reason=data['reason'])

class CorrectionSerializer(serializers.ModelSerializer):
    author_name=serializers.CharField(source='author.get_full_name',read_only=True)
    class Meta:model=MedicalRecordCorrection;fields=('id','author_name','content','created_at')

class MedicalRecordSerializer(serializers.ModelSerializer):
    appointment_id=serializers.PrimaryKeyRelatedField(source='appointment',queryset=Appointment.objects.all())
    patient_id=serializers.IntegerField(source='appointment.patient_id',read_only=True);patient_no=serializers.CharField(source='appointment.patient.patient_no',read_only=True);patient_name=serializers.CharField(source='appointment.patient.user.get_full_name',read_only=True);doctor_name=serializers.CharField(source='appointment.doctor.user.get_full_name',read_only=True);doctor_title=serializers.CharField(source='appointment.doctor.title',read_only=True)
    visit_at=serializers.DateField(source='appointment.slot.schedule.date',read_only=True);appointment_status=serializers.CharField(source='appointment.status',read_only=True);corrections=CorrectionSerializer(many=True,read_only=True)
    department_id=serializers.SerializerMethodField();department_name=serializers.SerializerMethodField();examinations=serializers.SerializerMethodField();prescription_count=serializers.SerializerMethodField();admission_count=serializers.SerializerMethodField()
    class Meta:model=MedicalRecord;fields=('id','record_no','appointment_id','patient_id','patient_no','appointment_status','patient_name','doctor_name','doctor_title','department_id','department_name','visit_at','chief_complaint','present_illness','past_history','examination','diagnosis','treatment','status','confirmed_at','updated_at','corrections','examinations','prescription_count','admission_count');read_only_fields=('record_no','patient_id','status','confirmed_at','updated_at','department_id','department_name','examinations','prescription_count','admission_count')
    def get_department_id(self,obj):return obj.appointment.department_id or obj.appointment.doctor.department_id
    def get_department_name(self,obj):
        department=obj.appointment.department or obj.appointment.doctor.department
        return department.name if department else None
    def get_examinations(self,obj):
        request=self.context.get('request') if isinstance(self.context,dict) else None
        patient_view=request is not None and getattr(request.user,'role',None)==User.Role.PATIENT
        rows=[]
        for order in obj.examination_orders.all():
            # 患者仅能看到已发布检查，未发布报告不随已确认病历提前展示。
            if patient_view and order.status!=ExaminationOrder.Status.PUBLISHED:continue
            report=getattr(order,'report',None)
            if patient_view and (report is None or report.status!=ExaminationReport.Status.PUBLISHED):continue
            rows.append({'id':order.pk,'order_no':order.order_no,'item_name':order.item_name_snapshot or (order.item.name if order.item_id else ''),'type':order.type,'type_display':order.get_type_display(),'status':order.status,'status_display':order.get_status_display(),'clinical_question':order.clinical_question,'created_at':order.created_at,'completed_at':order.completed_at,'report':None if report is None else {'id':report.pk,'findings':report.findings,'conclusion':report.conclusion,'status':report.status,'published_at':report.published_at},'files':[{'id':item.pk,'original_name':item.original_name,'file_type':item.file_type,'size':item.size,'uploaded_at':item.uploaded_at,'download_url':request.build_absolute_uri(f'/api/v1/medical-files/{item.pk}/download/') if request else None} for item in order.files.all()]})
        return rows
    def get_prescription_count(self,obj):return obj.prescriptions.count()
    def get_admission_count(self,obj):return obj.appointment.admissions.count()
    def validate_appointment(self,value):
        user=self.context['request'].user
        if user.role!=User.Role.DOCTOR or value.doctor.user_id!=user.id:raise serializers.ValidationError('只能为本人负责的预约创建病历。')
        if value.status!=Appointment.Status.IN_PROGRESS:raise serializers.ValidationError('只能为就诊中的预约创建病历。')
        return value

class MedicineSerializer(serializers.ModelSerializer):
    class Meta:model=Medicine;fields='__all__';read_only_fields=('created_at','updated_at')

class MedicineStockMovementSerializer(serializers.ModelSerializer):
    medicine_name=serializers.CharField(source='medicine.name',read_only=True);movement_type_display=serializers.CharField(source='get_movement_type_display',read_only=True);operator_name=serializers.CharField(source='operator.get_full_name',read_only=True)
    class Meta:model=MedicineStockMovement;fields=('id','medicine','medicine_name','movement_type','movement_type_display','quantity','balance_after','prescription','operator_name','note','created_at');read_only_fields=fields

class ExaminationItemSerializer(serializers.ModelSerializer):
    category_display=serializers.CharField(source='get_category_display',read_only=True)
    class Meta:model=ExaminationItem;fields=('id','name','category','category_display','price','is_active','description','created_at');read_only_fields=('created_at',)

class WardBedSerializer(serializers.ModelSerializer):
    department_name=serializers.CharField(source='department.name',read_only=True);display_name=serializers.SerializerMethodField()
    occupancy=serializers.SerializerMethodField()
    class Meta:model=WardBed;fields=('id','department','department_name','ward_name','bed_no','display_name','daily_rate','is_active','is_occupied','created_at','updated_at','occupancy');read_only_fields=('is_occupied','created_at','updated_at','occupancy')
    def get_display_name(self,obj):return str(obj)
    def get_occupancy(self,obj):
        if not obj.is_occupied:return None
        admission=obj.admissions.filter(status=InpatientAdmission.Status.ADMITTED).select_related('patient__user','attending_doctor__user','department','bed').order_by('-admitted_at').first()
        return None if admission is None else BedOccupancySerializer(admission,context=self.context).data

class BillingSerializer(serializers.ModelSerializer):
    patient_id=serializers.PrimaryKeyRelatedField(source='patient',queryset=PatientProfile.objects.all());appointment_id=serializers.PrimaryKeyRelatedField(source='appointment',queryset=Appointment.objects.all(),required=False,allow_null=True)
    admission_id=serializers.PrimaryKeyRelatedField(source='inpatient_admission',queryset=InpatientAdmission.objects.all(),required=False,allow_null=True)
    patient_name=serializers.CharField(source='patient.user.get_full_name',read_only=True);category_display=serializers.CharField(source='get_category_display',read_only=True);status_display=serializers.CharField(source='get_status_display',read_only=True);prescription_no=serializers.CharField(source='prescription.prescription_no',read_only=True)
    prescription_id=serializers.IntegerField(read_only=True);examination_id=serializers.IntegerField(read_only=True);admission_id_display=serializers.IntegerField(source='admission_id',read_only=True)
    examination_no=serializers.CharField(source='examination.order_no',read_only=True);examination_item_name=serializers.CharField(source='examination.item_name_snapshot',read_only=True,default=None);admission_no=serializers.CharField(source='admission.admission_no',read_only=True);inpatient_admission_no=serializers.CharField(source='inpatient_admission.admission_no',read_only=True,default=None);source_type=serializers.SerializerMethodField()
    charge_date=serializers.SerializerMethodField();charge_date_display=serializers.SerializerMethodField();payment_date=serializers.SerializerMethodField();unit_price=serializers.SerializerMethodField();payable=serializers.SerializerMethodField();days_admitted=serializers.IntegerField(read_only=True)
    charge_kind=serializers.SerializerMethodField();charge_details=serializers.SerializerMethodField()
    class Meta:model=BillingRecord;fields=('id','bill_no','patient_id','patient_name','appointment_id','prescription_id','prescription_no','examination_id','examination_no','examination_item_name','admission_id','admission_id_display','admission_no','inpatient_admission_no','source_type','category','category_display','description','amount','unit_price','charge_kind','charge_details','days_admitted','charge_date','charge_date_display','payment_date','payable','status','status_display','payment_method','paid_at','created_at');read_only_fields=('bill_no','status','payment_method','paid_at','created_at','unit_price','charge_kind','charge_details','charge_date','charge_date_display','payment_date','payable','days_admitted','inpatient_admission_no','admission_id_display','examination_item_name')
    def get_source_type(self,obj):
        if obj.prescription_id:return 'prescription'
        if obj.examination_id:return 'examination'
        if obj.admission_id:return 'admission'
        return 'manual'
    def get_charge_date(self,obj):
        """费用发生日期固定为账单创建日期，支付不改变发生日期。"""
        return timezone.localtime(obj.created_at).date().isoformat() if obj.created_at else None
    def get_charge_date_display(self,obj):
        return timezone.localtime(obj.created_at).strftime('%Y-%m-%d %H:%M') if obj.created_at else None
    def get_payment_date(self,obj):
        return timezone.localtime(obj.paid_at).strftime('%Y-%m-%d %H:%M') if obj.paid_at else None
    def get_unit_price(self,obj):
        if obj.days_admitted:return str((Decimal(obj.amount)/obj.days_admitted).quantize(Decimal('0.01')))
        if obj.prescription_id:
            items=list(obj.prescription.items.all())
            if len(items)==1:return str(prescription_item_unit_price(items[0]))
        return str(obj.amount)
    def get_payable(self,obj):return obj.status==BillingRecord.Status.UNPAID
    def get_charge_kind(self,obj):
        if obj.prescription_id:
            items=list(obj.prescription.items.all())
            return 'prescription' if items and all(item.unit_price_snapshot is not None for item in items) else 'prescription_legacy'
        if obj.admission_id:return 'inpatient_bed'
        if obj.examination_id:return 'examination'
        return 'manual'
    def get_charge_details(self,obj):
        """真实费用明细行：多药品处方按药品拆行；历史缺少快照的处方回退为原账单汇总行。"""
        if not obj.prescription_id:return []
        items=list(obj.prescription.items.all())
        if not items or any(item.unit_price_snapshot is None for item in items):
            names='、'.join(item.medicine.name for item in items)
            return [{'prescription_item_id':None,'medicine_name':names or '药品明细缺失','specification':'','quantity':sum(item.quantity for item in items),'unit_price':None,'amount':str(Decimal(obj.amount).quantize(Decimal('0.01'))),'price_snapshot':False}]
        amounts=prescription_item_amounts(items,Decimal(obj.amount))
        return [{'prescription_item_id':item.pk,'medicine_name':item.medicine.name,'specification':item.medicine.specification,'quantity':item.quantity,'unit_price':str(prescription_item_unit_price(item)),'amount':str(amounts[index]),'price_snapshot':True} for index,item in enumerate(items)]
    def validate(self,data):
        patient=data.get('patient',getattr(self.instance,'patient',None));appointment=data.get('appointment',getattr(self.instance,'appointment',None))
        if appointment and patient and appointment.patient_id!=patient.id:raise serializers.ValidationError({'appointment_id':'预约与患者不匹配。'})
        admission=data.get('inpatient_admission',getattr(self.instance,'inpatient_admission',None))
        if admission:
            if patient and admission.patient_id!=patient.id:raise serializers.ValidationError({'admission_id':'住院记录与患者不匹配。'})
            if admission.status!=InpatientAdmission.Status.ADMITTED:raise serializers.ValidationError({'admission_id':'仅在院患者的费用可以归集到本次住院。'})
        return data

class InpatientSerializer(serializers.ModelSerializer):
    patient_id=serializers.PrimaryKeyRelatedField(source='patient',queryset=PatientProfile.objects.all());doctor_id=serializers.PrimaryKeyRelatedField(source='attending_doctor',queryset=DoctorProfile.objects.filter(user__is_active=True));department_id=serializers.PrimaryKeyRelatedField(source='department',queryset=Department.objects.filter(status=Department.Status.ACTIVE));appointment_id=serializers.PrimaryKeyRelatedField(source='appointment',queryset=Appointment.objects.all(),required=False,allow_null=True);bed_id=serializers.PrimaryKeyRelatedField(source='bed',queryset=WardBed.objects.filter(is_active=True),required=False,allow_null=True)
    patient_no=serializers.CharField(source='patient.patient_no',read_only=True);patient_name=serializers.CharField(source='patient.user.get_full_name',read_only=True);doctor_name=serializers.CharField(source='attending_doctor.user.get_full_name',read_only=True);department_name=serializers.CharField(source='department.name',read_only=True);status_display=serializers.CharField(source='get_status_display',read_only=True);bed_display=serializers.CharField(source='bed.__str__',read_only=True)
    bed_ward_name=serializers.CharField(source='bed.ward_name',read_only=True,default=None);bed_no_display=serializers.CharField(source='bed.bed_no',read_only=True,default=None);bed_daily_rate=serializers.DecimalField(source='bed.daily_rate',max_digits=10,decimal_places=2,read_only=True,default=None)
    days_admitted=serializers.IntegerField(read_only=True);projected_bed_fee=serializers.DecimalField(max_digits=10,decimal_places=2,read_only=True);billable_days=serializers.IntegerField(read_only=True)
    charge_summary=serializers.SerializerMethodField();timeline=serializers.SerializerMethodField()
    class Meta:model=InpatientAdmission;fields=('id','admission_no','patient_id','patient_no','patient_name','doctor_id','doctor_name','department_id','department_name','appointment_id','bed_id','bed_display','bed_ward_name','bed_no_display','bed_daily_rate','ward','bed_no','daily_rate_snapshot','days_admitted','billable_days','projected_bed_fee','admission_diagnosis','discharge_summary','status','status_display','admitted_at','discharged_at','created_at','updated_at','charge_summary','timeline');read_only_fields=('admission_no','status','ward','bed_no','daily_rate_snapshot','admitted_at','discharged_at','created_at','updated_at','days_admitted','billable_days','projected_bed_fee','charge_summary','timeline')
    def get_charge_summary(self,obj):
        totals=self.context.get('charge_totals') if isinstance(self.context,dict) else None
        if totals is None:
            rows=BillingRecord.objects.filter(inpatient_admission=obj).exclude(status=BillingRecord.Status.CANCELLED).values('status').annotate(total=Sum('amount'))
            totals={row['status']:row['total'] or Decimal('0') for row in rows}
        def money(value):return str(Decimal(value).quantize(Decimal('0.01')))
        billed=sum((amount for amount in totals.values()),Decimal('0'))
        paid=totals.get(BillingRecord.Status.PAID,Decimal('0'));unpaid=totals.get(BillingRecord.Status.UNPAID,Decimal('0'))
        projected=obj.projected_bed_fee if obj.status==InpatientAdmission.Status.ADMITTED else Decimal('0')
        request=self.context.get('request') if isinstance(self.context,dict) else None
        if request is not None:
            cache=getattr(request,'_bed_bill_flags',None)
            if cache is None:cache={};request._bed_bill_flags=cache
            if obj.pk not in cache:cache[obj.pk]=BillingRecord.objects.filter(admission=obj).exists()
            has_bed_bill=cache[obj.pk]
        else:has_bed_bill=BillingRecord.objects.filter(admission=obj).exists()
        return {'billed_amount':money(billed),'paid_amount':money(paid),'unpaid_amount':money(unpaid),'projected_bed_fee':money(projected),'estimated_total':money(billed+projected),'has_bed_bill':has_bed_bill}
    def get_timeline(self,obj):
        events=[{'key':'created','label':'创建住院申请','at':obj.created_at,'done':True}]
        if obj.admitted_at:events.append({'key':'admitted','label':'办理入院','at':obj.admitted_at,'done':True})
        if obj.discharged_at:events.append({'key':'discharged','label':'办理出院','at':obj.discharged_at,'done':True})
        if obj.status in {InpatientAdmission.Status.PENDING,InpatientAdmission.Status.ADMITTED}:events.append({'key':'pending_discharge','label':'办理出院','at':None,'done':False})
        return events
    def validate(self,data):
        patient=data.get('patient',getattr(self.instance,'patient',None));appointment=data.get('appointment',getattr(self.instance,'appointment',None))
        if appointment and patient and appointment.patient_id!=patient.id:raise serializers.ValidationError({'appointment_id':'预约与患者不匹配。'})
        bed=data.get('bed',getattr(self.instance,'bed',None));department=data.get('department',getattr(self.instance,'department',None))
        if bed and department and bed.department_id!=department.id:raise serializers.ValidationError({'bed_id':'床位与入院科室不匹配。'})
        if self.instance and self.instance.status==InpatientAdmission.Status.ADMITTED:
            if bed and bed.pk!=self.instance.bed_id:raise serializers.ValidationError({'bed_id':'住院中的床位不可更改。'})
            if department and department.pk!=self.instance.department_id:raise serializers.ValidationError({'department_id':'住院中的科室不可更改。'})
        return data

class BedOccupancySerializer(serializers.ModelSerializer):
    patient_id=serializers.IntegerField(read_only=True);patient_name=serializers.CharField(source='patient.user.get_full_name',read_only=True);patient_no=serializers.CharField(source='patient.patient_no',read_only=True);patient_phone=serializers.CharField(source='patient.user.phone',read_only=True)
    doctor_name=serializers.CharField(source='attending_doctor.user.get_full_name',read_only=True);department_name=serializers.CharField(source='department.name',read_only=True)
    status_display=serializers.CharField(source='get_status_display',read_only=True);days_admitted=serializers.IntegerField(read_only=True);bed_display=serializers.CharField(source='bed.__str__',read_only=True)
    class Meta:model=InpatientAdmission;fields=('id','admission_no','patient_id','patient_name','patient_no','patient_phone','doctor_name','department_name','status','status_display','ward','bed_no','bed_display','daily_rate_snapshot','admitted_at','days_admitted','admission_diagnosis','discharge_summary')

class InpatientChargeSummarySerializer(serializers.ModelSerializer):
    patient_name=serializers.CharField(source='patient.user.get_full_name',read_only=True);patient_no=serializers.CharField(source='patient.patient_no',read_only=True);doctor_name=serializers.CharField(source='attending_doctor.user.get_full_name',read_only=True);department_name=serializers.CharField(source='department.name',read_only=True);status_display=serializers.CharField(source='get_status_display',read_only=True)
    days_admitted=serializers.IntegerField(read_only=True);billable_days=serializers.IntegerField(read_only=True);projected_bed_fee=serializers.DecimalField(max_digits=10,decimal_places=2,read_only=True)
    charge_summary=serializers.SerializerMethodField();category_totals=serializers.SerializerMethodField()
    class Meta:model=InpatientAdmission;fields=('id','admission_no','patient_name','patient_no','doctor_name','department_name','status','status_display','ward','bed_no','daily_rate_snapshot','admission_diagnosis','discharge_summary','admitted_at','discharged_at','days_admitted','billable_days','projected_bed_fee','charge_summary','category_totals')
    def get_category_totals(self,obj):
        rows=BillingRecord.objects.filter(inpatient_admission=obj).exclude(status=BillingRecord.Status.CANCELLED).values('category').annotate(total=Sum('amount'))
        return [{'category':row['category'],'label':dict(BillingRecord.Category.choices).get(row['category'],row['category']),'total':str(row['total'] or 0)} for row in rows]
    def get_charge_summary(self,obj):return InpatientSerializer().get_charge_summary(obj)

def _as_decimal(value):
    try:return Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError):return Decimal('0')

def prescription_item_unit_price(item):
    """药品单价快照；历史明细缺少快照时回退到原账单总额均摊。"""
    if item.unit_price_snapshot is not None:return _as_decimal(item.unit_price_snapshot)
    bill=getattr(item.prescription,'billing_record',None)
    if bill is not None and item.quantity:
        return (_as_decimal(bill.amount)/item.quantity).quantize(Decimal('0.01'))
    return _as_decimal(item.medicine.price)

def prescription_item_amounts(items,total):
    """按药品数量与快照单价分摊账单总额：有快照时用快照价，无快照时按原账单总额均摊，末行吸收分位误差。"""
    total=_as_decimal(total);unit_prices=[prescription_item_unit_price(item) for item in items]
    snapshots=[item.unit_price_snapshot is not None for item in items]
    raw=[(unit_prices[index]*item.quantity if snapshots[index] else Decimal('0')) for index,item in enumerate(items)]
    snapped_total=sum(raw,Decimal('0'))
    remaining_quantity=sum(item.quantity for index,item in enumerate(items) if not snapshots[index])
    amounts=[]
    for index,item in enumerate(items):
        if snapshots[index]:amounts.append(raw[index].quantize(Decimal('0.01')))
        elif remaining_quantity:amounts.append((total-snapped_total)*item.quantity/remaining_quantity)
        else:amounts.append(Decimal('0'))
    amounts=[amount.quantize(Decimal('0.01')) for amount in amounts]
    if amounts:
        amounts[-1]=amounts[-1]+(total-sum(amounts,Decimal('0')))
    return amounts

class PrescriptionItemSerializer(serializers.ModelSerializer):
    medicine_id=serializers.PrimaryKeyRelatedField(source='medicine',queryset=Medicine.objects.filter(is_active=True));medicine_name=serializers.CharField(source='medicine.name',read_only=True);specification=serializers.CharField(source='medicine.specification',read_only=True)
    unit_price=serializers.SerializerMethodField()
    class Meta:model=PrescriptionItem;fields=('id','medicine_id','medicine_name','specification','dosage','frequency','duration','quantity','unit_price_snapshot','unit_price')
    def get_unit_price(self,obj):return str(prescription_item_unit_price(obj))

class PrescriptionSerializer(serializers.ModelSerializer):
    record_id=serializers.PrimaryKeyRelatedField(source='record',queryset=MedicalRecord.objects.all());items=PrescriptionItemSerializer(many=True)
    admission_id=serializers.IntegerField(required=False,allow_null=True)
    patient_name=serializers.CharField(source='record.appointment.patient.user.get_full_name',read_only=True);doctor_name=serializers.CharField(source='doctor.user.get_full_name',read_only=True);diagnosis=serializers.CharField(source='record.diagnosis',read_only=True);bill_no=serializers.SerializerMethodField();total_amount=serializers.SerializerMethodField();admission_no=serializers.SerializerMethodField()
    class Meta:model=Prescription;fields=('id','prescription_no','record_id','patient_name','doctor_name','diagnosis','status','items','notes','bill_no','total_amount','admission_id','admission_no','dispensed_at','created_at');read_only_fields=('prescription_no','status','bill_no','total_amount','admission_no','dispensed_at','created_at')
    def to_representation(self,instance):
        data=super().to_representation(instance)
        try:data['admission_id']=instance.billing_record.inpatient_admission_id
        except BillingRecord.DoesNotExist:data['admission_id']=None
        return data
    def get_bill_no(self,obj):
        try:return obj.billing_record.bill_no
        except BillingRecord.DoesNotExist:return None
    def get_total_amount(self,obj):return str(sum(prescription_item_unit_price(item)*item.quantity for item in obj.items.all()))
    def get_admission_no(self,obj):
        try:return obj.billing_record.inpatient_admission.admission_no
        except (BillingRecord.DoesNotExist,AttributeError):return None
    def validate_record(self,record):
        user=self.context['request'].user
        if user.role!=User.Role.DOCTOR or record.appointment.doctor.user_id!=user.id:raise serializers.ValidationError('只能为本人确认的病历开具处方。')
        if record.status!=MedicalRecord.Status.CONFIRMED:raise serializers.ValidationError('病历确认后才能开具处方。')
        return record
    @transaction.atomic
    def create(self,data):
        items=data.pop('items');admission_id=data.pop('admission_id',None);doctor=self.context['request'].user.doctor_profile;prescription=Prescription.objects.create(doctor=doctor,**data)
        PrescriptionItem.objects.bulk_create([PrescriptionItem(prescription=prescription,unit_price_snapshot=item['medicine'].price,**item) for item in items])
        total=sum(item['medicine'].price*item['quantity'] for item in items);names='、'.join(item['medicine'].name for item in items)
        patient=prescription.record.appointment.patient
        admission=link_inpatient(patient=patient,admission_id=admission_id,appointment=prescription.record.appointment)
        BillingRecord.objects.create(patient=patient,appointment=prescription.record.appointment,prescription=prescription,inpatient_admission=admission,category=BillingRecord.Category.MEDICINE,description=f'处方 {prescription.prescription_no}：{names}'[:200],amount=total)
        return prescription

class MedicalFileSerializer(serializers.ModelSerializer):
    download_url=serializers.SerializerMethodField()
    class Meta:model=MedicalFile;fields=('id','original_name','file_type','size','uploaded_at','download_url')
    def get_download_url(self,obj):return self.context['request'].build_absolute_uri(f'/api/v1/medical-files/{obj.pk}/download/') if self.context.get('request') else None

class ReportSerializer(serializers.ModelSerializer):
    class Meta:model=ExaminationReport;fields=('id','findings','conclusion','status','published_at','updated_at');read_only_fields=('status','published_at','updated_at')

class ExaminationSerializer(serializers.ModelSerializer):
    record_id=serializers.PrimaryKeyRelatedField(source='record',queryset=MedicalRecord.objects.all(),write_only=True);item_id=serializers.PrimaryKeyRelatedField(source='item',queryset=ExaminationItem.objects.filter(is_active=True),write_only=True,required=False)
    admission_id=serializers.IntegerField(write_only=True,required=False,allow_null=True)
    patient_id=serializers.IntegerField(read_only=True);patient_no=serializers.CharField(source='patient.patient_no',read_only=True);patient_name=serializers.CharField(source='patient.user.get_full_name',read_only=True);doctor_name=serializers.CharField(source='doctor.user.get_full_name',read_only=True);type_display=serializers.CharField(source='get_type_display',read_only=True);status_display=serializers.CharField(source='get_status_display',read_only=True);report=ReportSerializer(read_only=True);files=MedicalFileSerializer(many=True,read_only=True)
    record_no=serializers.CharField(source='record.record_no',read_only=True);record_pk=serializers.IntegerField(source='record_id',read_only=True);record_diagnosis=serializers.CharField(source='record.diagnosis',read_only=True);visit_date=serializers.DateField(source='record.appointment.slot.schedule.date',read_only=True)
    department_id=serializers.SerializerMethodField();department_name=serializers.SerializerMethodField();published_at=serializers.SerializerMethodField()
    admission_no=serializers.SerializerMethodField()
    class Meta:model=ExaminationOrder;fields=('id','order_no','record_id','record_pk','record_no','record_diagnosis','visit_date','item_id','item_name_snapshot','price_snapshot','patient_id','patient_no','patient_name','doctor_name','department_id','department_name','type','type_display','status','status_display','clinical_question','completed_at','published_at','created_at','report','files','admission_id','admission_no');read_only_fields=('order_no','record_pk','item_name_snapshot','price_snapshot','status','completed_at','published_at','created_at','admission_no','patient_id','department_id','department_name')
    def get_department_id(self,obj):
        appointment=obj.record.appointment
        return appointment.department_id or appointment.doctor.department_id
    def get_department_name(self,obj):
        appointment=obj.record.appointment;department=appointment.department or appointment.doctor.department
        return department.name if department else None
    def get_published_at(self,obj):
        report=getattr(obj,'report',None)
        return report.published_at if report is not None else None
    def get_admission_no(self,obj):
        try:return obj.billing_record.inpatient_admission.admission_no
        except (BillingRecord.DoesNotExist,AttributeError):return None
    def validate_record(self,record):
        user=self.context['request'].user
        if user.role!=User.Role.DOCTOR or record.appointment.doctor.user_id!=user.id:raise serializers.ValidationError('只能为本人患者申请检查。')
        if record.status!=MedicalRecord.Status.CONFIRMED:raise serializers.ValidationError('病历确认后才能申请检查。')
        return record
    @transaction.atomic
    def create(self,data):
        record=data.pop('record');admission_id=data.pop('admission_id',None);item=data.get('item');order=ExaminationOrder.objects.create(record=record,patient=record.appointment.patient,doctor=self.context['request'].user.doctor_profile,item_name_snapshot=item.name if item else '',price_snapshot=item.price if item else 0,**data)
        if item:
            admission=link_inpatient(patient=order.patient,admission_id=admission_id,appointment=record.appointment)
            BillingRecord.objects.create(patient=order.patient,appointment=record.appointment,examination=order,inpatient_admission=admission,category=BillingRecord.Category.EXAMINATION,description=f'检查 {order.order_no}：{item.name}',amount=item.price)
        return order

class AuditSerializer(serializers.ModelSerializer):
    user_name=serializers.CharField(source='user.get_full_name',read_only=True);action_display=serializers.CharField(source='action',read_only=True)
    class Meta:model=AuditLog;fields=('id','created_at','user_name','action','action_display','resource','object_id','description')

class AIServiceSerializer(serializers.ModelSerializer):
    class Meta:model=AIService;fields=('id','name','service_type','description','is_enabled','endpoint','updated_at');read_only_fields=('updated_at',)

class AITaskSerializer(serializers.ModelSerializer):
    class Meta:model=AIAnalysisTask;fields=('id','patient','file','service','status','result','error_message','created_at','updated_at');read_only_fields=('patient','status','result','error_message','created_at','updated_at')
