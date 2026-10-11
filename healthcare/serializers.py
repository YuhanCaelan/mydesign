from django.contrib.auth import authenticate,password_validation
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import *
from .services import book_appointment,generate_slots

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
    class Meta:model=PatientProfile;fields=('id','patient_no','full_name','phone','email','gender','gender_display','birth_date','address','blood_group','allergies','medical_history','emergency_contact_name','emergency_contact_phone','created_at');read_only_fields=('patient_no','created_at')

class AdminUserSerializer(serializers.ModelSerializer):
    full_name=serializers.CharField(source='first_name');password=serializers.CharField(write_only=True,min_length=8,required=False)
    department_id=serializers.PrimaryKeyRelatedField(source='department',queryset=Department.objects.filter(status=Department.Status.ACTIVE),write_only=True,required=False)
    title=serializers.CharField(write_only=True,required=False,allow_blank=True);specialty=serializers.CharField(write_only=True,required=False,allow_blank=True)
    role_display=serializers.CharField(source='get_role_display',read_only=True);is_active_display=serializers.SerializerMethodField();doctor_no=serializers.SerializerMethodField();department_name=serializers.SerializerMethodField()
    class Meta:model=User;fields=('id','username','full_name','password','role','role_display','phone','email','is_active','is_active_display','department_id','department_name','doctor_no','title','specialty','created_at');read_only_fields=('created_at',)
    def get_is_active_display(self,obj):return '启用' if obj.is_active else '禁用'
    def get_doctor_no(self,obj):
        try:return obj.doctor_profile.doctor_no
        except DoctorProfile.DoesNotExist:return None
    def get_department_name(self,obj):
        try:return obj.doctor_profile.department.name
        except DoctorProfile.DoesNotExist:return None
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
        user=User.objects.create_user(password=password,**data)
        if user.role==User.Role.DOCTOR:
            doctor=DoctorProfile.objects.create(user=user,department=department,title=title,specialty=specialty);doctor.departments.add(department)
        elif user.role==User.Role.PATIENT:PatientProfile.objects.create(user=user)
        return user
    def update(self,user,data):
        data.pop('department',None);data.pop('title',None);data.pop('specialty',None);password=data.pop('password',None)
        if 'role' in data and data['role']!=user.role:raise serializers.ValidationError({'role':'已有账户不可直接更换角色。'})
        for key,value in data.items():setattr(user,key,value)
        if password:user.set_password(password)
        user.save();return user

class SlotSerializer(serializers.ModelSerializer):
    date=serializers.DateField(source='schedule.date',read_only=True);doctor_id=serializers.IntegerField(source='schedule.doctor_id',read_only=True)
    class Meta:model=AppointmentSlot;fields=('id','doctor_id','date','start_time','end_time','status')

class ScheduleSerializer(serializers.ModelSerializer):
    doctor_name=serializers.CharField(source='doctor.user.get_full_name',read_only=True);time_range=serializers.SerializerMethodField();total_slots=serializers.IntegerField(source='slots.count',read_only=True);available_slots=serializers.SerializerMethodField()
    class Meta:model=DoctorSchedule;fields=('id','doctor','doctor_name','date','start_time','end_time','time_range','slot_minutes','is_active','total_slots','available_slots','created_at');read_only_fields=('created_at',)
    def get_time_range(self,obj):return f'{obj.start_time:%H:%M}–{obj.end_time:%H:%M}'
    def get_available_slots(self,obj):return obj.slots.filter(status=AppointmentSlot.Status.AVAILABLE).count()
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
    patient_name=serializers.CharField(source='patient.user.get_full_name',read_only=True);doctor_name=serializers.CharField(source='doctor.user.get_full_name',read_only=True);department_name=serializers.CharField(source='doctor.department.name',read_only=True);status_display=serializers.CharField(source='get_status_display',read_only=True)
    class Meta:model=Appointment;fields=('id','appointment_no','patient_id','patient_name','doctor_id','doctor_name','department_name','slot','slot_id','status','status_display','reason','created_at');read_only_fields=('appointment_no','status','created_at')
    def create(self,data):
        slot=data.pop('selected_slot');return book_appointment(patient=self.context['request'].user.patient_profile,slot_id=slot.pk,reason=data['reason'])

class CorrectionSerializer(serializers.ModelSerializer):
    author_name=serializers.CharField(source='author.get_full_name',read_only=True)
    class Meta:model=MedicalRecordCorrection;fields=('id','author_name','content','created_at')

class MedicalRecordSerializer(serializers.ModelSerializer):
    appointment_id=serializers.PrimaryKeyRelatedField(source='appointment',queryset=Appointment.objects.all())
    patient_name=serializers.CharField(source='appointment.patient.user.get_full_name',read_only=True);doctor_name=serializers.CharField(source='appointment.doctor.user.get_full_name',read_only=True);visit_at=serializers.DateField(source='appointment.slot.schedule.date',read_only=True);appointment_status=serializers.CharField(source='appointment.status',read_only=True);corrections=CorrectionSerializer(many=True,read_only=True)
    class Meta:model=MedicalRecord;fields=('id','record_no','appointment_id','appointment_status','patient_name','doctor_name','visit_at','chief_complaint','present_illness','past_history','examination','diagnosis','treatment','status','confirmed_at','updated_at','corrections');read_only_fields=('record_no','status','confirmed_at','updated_at')
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
    class Meta:model=WardBed;fields=('id','department','department_name','ward_name','bed_no','display_name','daily_rate','is_active','is_occupied','created_at');read_only_fields=('is_occupied','created_at')
    def get_display_name(self,obj):return str(obj)

class BillingSerializer(serializers.ModelSerializer):
    patient_id=serializers.PrimaryKeyRelatedField(source='patient',queryset=PatientProfile.objects.all());appointment_id=serializers.PrimaryKeyRelatedField(source='appointment',queryset=Appointment.objects.all(),required=False,allow_null=True)
    patient_name=serializers.CharField(source='patient.user.get_full_name',read_only=True);category_display=serializers.CharField(source='get_category_display',read_only=True);status_display=serializers.CharField(source='get_status_display',read_only=True);prescription_no=serializers.CharField(source='prescription.prescription_no',read_only=True)
    examination_no=serializers.CharField(source='examination.order_no',read_only=True);admission_no=serializers.CharField(source='admission.admission_no',read_only=True);source_type=serializers.SerializerMethodField()
    class Meta:model=BillingRecord;fields=('id','bill_no','patient_id','patient_name','appointment_id','prescription_no','examination_no','admission_no','source_type','category','category_display','description','amount','status','status_display','payment_method','paid_at','created_at');read_only_fields=('bill_no','status','payment_method','paid_at','created_at')
    def get_source_type(self,obj):
        if obj.prescription_id:return 'prescription'
        if obj.examination_id:return 'examination'
        if obj.admission_id:return 'admission'
        return 'manual'
    def validate(self,data):
        patient=data.get('patient',getattr(self.instance,'patient',None));appointment=data.get('appointment',getattr(self.instance,'appointment',None))
        if appointment and patient and appointment.patient_id!=patient.id:raise serializers.ValidationError({'appointment_id':'预约与患者不匹配。'})
        return data

class InpatientSerializer(serializers.ModelSerializer):
    patient_id=serializers.PrimaryKeyRelatedField(source='patient',queryset=PatientProfile.objects.all());doctor_id=serializers.PrimaryKeyRelatedField(source='attending_doctor',queryset=DoctorProfile.objects.filter(user__is_active=True));department_id=serializers.PrimaryKeyRelatedField(source='department',queryset=Department.objects.filter(status=Department.Status.ACTIVE));appointment_id=serializers.PrimaryKeyRelatedField(source='appointment',queryset=Appointment.objects.all(),required=False,allow_null=True);bed_id=serializers.PrimaryKeyRelatedField(source='bed',queryset=WardBed.objects.filter(is_active=True),required=False,allow_null=True)
    patient_name=serializers.CharField(source='patient.user.get_full_name',read_only=True);doctor_name=serializers.CharField(source='attending_doctor.user.get_full_name',read_only=True);department_name=serializers.CharField(source='department.name',read_only=True);status_display=serializers.CharField(source='get_status_display',read_only=True);bed_display=serializers.CharField(source='bed.__str__',read_only=True)
    class Meta:model=InpatientAdmission;fields=('id','admission_no','patient_id','patient_name','doctor_id','doctor_name','department_id','department_name','appointment_id','bed_id','bed_display','ward','bed_no','daily_rate_snapshot','admission_diagnosis','discharge_summary','status','status_display','admitted_at','discharged_at','created_at');read_only_fields=('admission_no','status','ward','bed_no','daily_rate_snapshot','admitted_at','discharged_at','created_at')
    def validate(self,data):
        patient=data.get('patient',getattr(self.instance,'patient',None));appointment=data.get('appointment',getattr(self.instance,'appointment',None))
        if appointment and patient and appointment.patient_id!=patient.id:raise serializers.ValidationError({'appointment_id':'预约与患者不匹配。'})
        bed=data.get('bed',getattr(self.instance,'bed',None));department=data.get('department',getattr(self.instance,'department',None))
        if bed and department and bed.department_id!=department.id:raise serializers.ValidationError({'bed_id':'床位与入院科室不匹配。'})
        return data

class PrescriptionItemSerializer(serializers.ModelSerializer):
    medicine_id=serializers.PrimaryKeyRelatedField(source='medicine',queryset=Medicine.objects.filter(is_active=True));medicine_name=serializers.CharField(source='medicine.name',read_only=True);specification=serializers.CharField(source='medicine.specification',read_only=True)
    class Meta:model=PrescriptionItem;fields=('id','medicine_id','medicine_name','specification','dosage','frequency','duration','quantity')

class PrescriptionSerializer(serializers.ModelSerializer):
    record_id=serializers.PrimaryKeyRelatedField(source='record',queryset=MedicalRecord.objects.all());items=PrescriptionItemSerializer(many=True)
    patient_name=serializers.CharField(source='record.appointment.patient.user.get_full_name',read_only=True);doctor_name=serializers.CharField(source='doctor.user.get_full_name',read_only=True);diagnosis=serializers.CharField(source='record.diagnosis',read_only=True);bill_no=serializers.SerializerMethodField();total_amount=serializers.SerializerMethodField()
    class Meta:model=Prescription;fields=('id','prescription_no','record_id','patient_name','doctor_name','diagnosis','status','items','notes','bill_no','total_amount','dispensed_at','created_at');read_only_fields=('prescription_no','status','bill_no','total_amount','dispensed_at','created_at')
    def get_bill_no(self,obj):
        try:return obj.billing_record.bill_no
        except BillingRecord.DoesNotExist:return None
    def get_total_amount(self,obj):return sum(item.medicine.price*item.quantity for item in obj.items.all())
    def validate_record(self,record):
        user=self.context['request'].user
        if user.role!=User.Role.DOCTOR or record.appointment.doctor.user_id!=user.id:raise serializers.ValidationError('只能为本人确认的病历开具处方。')
        if record.status!=MedicalRecord.Status.CONFIRMED:raise serializers.ValidationError('病历确认后才能开具处方。')
        return record
    @transaction.atomic
    def create(self,data):
        items=data.pop('items');doctor=self.context['request'].user.doctor_profile;prescription=Prescription.objects.create(doctor=doctor,**data)
        PrescriptionItem.objects.bulk_create([PrescriptionItem(prescription=prescription,**item) for item in items])
        total=sum(item['medicine'].price*item['quantity'] for item in items);names='、'.join(item['medicine'].name for item in items)
        BillingRecord.objects.create(patient=prescription.record.appointment.patient,appointment=prescription.record.appointment,prescription=prescription,category=BillingRecord.Category.MEDICINE,description=f'处方 {prescription.prescription_no}：{names}'[:200],amount=total)
        return prescription

class MedicalFileSerializer(serializers.ModelSerializer):
    download_url=serializers.SerializerMethodField()
    class Meta:model=MedicalFile;fields=('id','original_name','file_type','size','uploaded_at','download_url')
    def get_download_url(self,obj):return self.context['request'].build_absolute_uri(f'/api/v1/medical-files/{obj.pk}/download/') if self.context.get('request') else None

class ReportSerializer(serializers.ModelSerializer):
    class Meta:model=ExaminationReport;fields=('id','findings','conclusion','status','published_at','updated_at');read_only_fields=('status','published_at','updated_at')

class ExaminationSerializer(serializers.ModelSerializer):
    record_id=serializers.PrimaryKeyRelatedField(source='record',queryset=MedicalRecord.objects.all(),write_only=True);item_id=serializers.PrimaryKeyRelatedField(source='item',queryset=ExaminationItem.objects.filter(is_active=True),write_only=True,required=False)
    patient_name=serializers.CharField(source='patient.user.get_full_name',read_only=True);doctor_name=serializers.CharField(source='doctor.user.get_full_name',read_only=True);type_display=serializers.CharField(source='get_type_display',read_only=True);status_display=serializers.CharField(source='get_status_display',read_only=True);report=ReportSerializer(read_only=True);files=MedicalFileSerializer(many=True,read_only=True)
    class Meta:model=ExaminationOrder;fields=('id','order_no','record_id','item_id','item_name_snapshot','price_snapshot','patient_name','doctor_name','type','type_display','status','status_display','clinical_question','completed_at','created_at','report','files');read_only_fields=('order_no','item_name_snapshot','price_snapshot','status','completed_at','created_at')
    def validate_record(self,record):
        user=self.context['request'].user
        if user.role!=User.Role.DOCTOR or record.appointment.doctor.user_id!=user.id:raise serializers.ValidationError('只能为本人患者申请检查。')
        if record.status!=MedicalRecord.Status.CONFIRMED:raise serializers.ValidationError('病历确认后才能申请检查。')
        return record
    @transaction.atomic
    def create(self,data):
        record=data.pop('record');item=data.get('item');order=ExaminationOrder.objects.create(record=record,patient=record.appointment.patient,doctor=self.context['request'].user.doctor_profile,item_name_snapshot=item.name if item else '',price_snapshot=item.price if item else 0,**data)
        if item:BillingRecord.objects.create(patient=order.patient,appointment=record.appointment,examination=order,category=BillingRecord.Category.EXAMINATION,description=f'检查 {order.order_no}：{item.name}',amount=item.price)
        return order

class AuditSerializer(serializers.ModelSerializer):
    user_name=serializers.CharField(source='user.get_full_name',read_only=True);action_display=serializers.CharField(source='action',read_only=True)
    class Meta:model=AuditLog;fields=('id','created_at','user_name','action','action_display','resource','object_id','description')

class AIServiceSerializer(serializers.ModelSerializer):
    class Meta:model=AIService;fields=('id','name','service_type','description','is_enabled','endpoint','updated_at');read_only_fields=('updated_at',)

class AITaskSerializer(serializers.ModelSerializer):
    class Meta:model=AIAnalysisTask;fields=('id','patient','file','service','status','result','error_message','created_at','updated_at');read_only_fields=('patient','status','result','error_message','created_at','updated_at')
