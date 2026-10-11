from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

@admin.register(User)
class SmartUserAdmin(UserAdmin):
    fieldsets=UserAdmin.fieldsets+(('智慧医疗身份',{'fields':('role','phone','avatar')}),)
    add_fieldsets=UserAdmin.add_fieldsets+(('智慧医疗身份',{'fields':('role','phone')}),)
    list_display=('username','first_name','role','is_active','is_staff')
    list_filter=('role','is_active','is_staff')

for model in (Department,DoctorProfile,PatientProfile,DoctorSchedule,AppointmentSlot,Appointment,MedicalRecord,MedicalRecordCorrection,Medicine,Prescription,PrescriptionItem,ExaminationOrder,ExaminationReport,MedicalFile,BillingRecord,InpatientAdmission,AIService,AIAnalysisTask,AuditLog):
    admin.site.register(model)
