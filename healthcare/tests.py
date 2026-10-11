from datetime import date,time,timedelta
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase
from .models import *
from .services import generate_slots

@override_settings(MEDIA_ROOT='/tmp/smartmedical-test-media')
class SmartMedicalApiTests(APITestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('admin','admin@example.com','AdminPass123!',first_name='系统管理员')
        self.department=Department.objects.create(name='神经内科',description='神经系统疾病诊疗')
        self.doctor_user=User.objects.create_user('doctor',password='DoctorPass123!',first_name='张医师',role=User.Role.DOCTOR)
        self.doctor=DoctorProfile.objects.create(user=self.doctor_user,department=self.department,title='主治医师',specialty='神经影像')
        self.other_doctor_user=User.objects.create_user('doctor2',password='DoctorPass123!',first_name='李医师',role=User.Role.DOCTOR)
        self.other_doctor=DoctorProfile.objects.create(user=self.other_doctor_user,department=self.department)
        self.patient_user=User.objects.create_user('patient',password='PatientPass123!',first_name='测试患者',phone='13800000000',role=User.Role.PATIENT)
        self.patient=PatientProfile.objects.create(user=self.patient_user)
        self.other_patient_user=User.objects.create_user('patient2',password='PatientPass123!',first_name='其他患者',phone='13900000000',role=User.Role.PATIENT)
        self.other_patient=PatientProfile.objects.create(user=self.other_patient_user)
        self.schedule=DoctorSchedule.objects.create(doctor=self.doctor,date=date.today()+timedelta(days=1),start_time=time(9),end_time=time(10),slot_minutes=30)
        generate_slots(self.schedule);self.slot=self.schedule.slots.first()

    def auth(self,user):self.client.force_authenticate(user)

    def create_appointment(self):
        self.auth(self.patient_user);response=self.client.post('/api/v1/appointments/',{'slot_id':self.slot.pk,'reason':'头痛三天'},format='json')
        self.assertEqual(response.status_code,201,response.data);return Appointment.objects.get(pk=response.data['id'])

    def test_patient_registration_and_jwt_login(self):
        self.client.force_authenticate(None)
        response=self.client.post('/api/v1/auth/register/',{'username':'newpatient','password':'SafePass123!','password_confirm':'SafePass123!','full_name':'新患者','phone':'13700000000'},format='json')
        self.assertEqual(response.status_code,201,response.data);self.assertEqual(response.data['role'],'patient');self.assertTrue(PatientProfile.objects.filter(user__username='newpatient').exists())
        response=self.client.post('/api/v1/auth/login/',{'username':'newpatient','password':'SafePass123!'},format='json')
        self.assertEqual(response.status_code,200,response.data);self.assertIn('access',response.data);self.assertIn('refresh',response.data)

    def test_slot_is_unique_and_appointment_scopes_are_isolated(self):
        appointment=self.create_appointment();self.assertEqual(appointment.slot.status,AppointmentSlot.Status.BOOKED)
        self.auth(self.other_patient_user);response=self.client.post('/api/v1/appointments/',{'slot_id':self.slot.pk,'reason':'重复预约'},format='json')
        self.assertEqual(response.status_code,400);self.assertEqual(self.client.get('/api/v1/appointments/').data['count'],0)
        self.auth(self.doctor_user);self.assertEqual(self.client.get('/api/v1/appointments/').data['count'],1)
        self.auth(self.other_doctor_user);self.assertEqual(self.client.get('/api/v1/appointments/').data['count'],0)

    def test_appointment_state_machine_and_slot_release(self):
        appointment=self.create_appointment();self.auth(self.patient_user)
        response=self.client.post(f'/api/v1/appointments/{appointment.pk}/cancel/');self.assertEqual(response.status_code,200,response.data)
        appointment.refresh_from_db();self.slot.refresh_from_db();self.assertEqual(appointment.status,'cancelled');self.assertEqual(self.slot.status,'available')
        response=self.client.post(f'/api/v1/appointments/{appointment.pk}/cancel/');self.assertEqual(response.status_code,400)

    def test_doctor_record_confirmation_and_patient_visibility(self):
        appointment=self.create_appointment();self.auth(self.doctor_user)
        self.assertEqual(self.client.post(f'/api/v1/appointments/{appointment.pk}/start/').status_code,200)
        response=self.client.post('/api/v1/medical-records/',{'appointment_id':appointment.pk,'chief_complaint':'头痛','present_illness':'三天','past_history':'无','examination':'生命体征平稳','diagnosis':'偏头痛','treatment':'休息并观察'},format='json')
        self.assertEqual(response.status_code,201,response.data);record_id=response.data['id']
        self.auth(self.patient_user);self.assertEqual(self.client.get('/api/v1/medical-records/').data['count'],0)
        self.auth(self.doctor_user);self.assertEqual(self.client.post(f'/api/v1/medical-records/{record_id}/confirm/').status_code,200)
        response=self.client.patch(f'/api/v1/medical-records/{record_id}/',{'diagnosis':'覆盖诊断'},format='json');self.assertEqual(response.status_code,403)
        response=self.client.post(f'/api/v1/medical-records/{record_id}/corrections/',{'content':'补充说明：建议复诊'},format='json');self.assertEqual(response.status_code,201,response.data)
        self.auth(self.patient_user);response=self.client.get('/api/v1/medical-records/');self.assertEqual(response.data['count'],1);self.assertEqual(response.data['results'][0]['corrections'][0]['content'],'补充说明：建议复诊')

    def confirmed_record(self):
        appointment=self.create_appointment();appointment.status=Appointment.Status.IN_PROGRESS;appointment.save(update_fields=['status','updated_at'])
        record=MedicalRecord.objects.create(appointment=appointment,chief_complaint='头痛',diagnosis='偏头痛',status=MedicalRecord.Status.CONFIRMED,confirmed_at=timezone.now())
        return record

    def test_prescription_and_examination_follow_clinical_relationship(self):
        record=self.confirmed_record();medicine=Medicine.objects.create(name='布洛芬',specification='0.2g',unit='盒',stock=20)
        self.auth(self.doctor_user);response=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'饭后服用','items':[{'medicine_id':medicine.pk,'dosage':'0.2g','frequency':'每日两次','duration':'3天','quantity':1}]},format='json')
        self.assertEqual(response.status_code,201,response.data)
        response=self.client.post('/api/v1/examinations/',{'record_id':record.pk,'type':'mri','clinical_question':'排除颅内器质性病变'},format='json');self.assertEqual(response.status_code,201,response.data);order_id=response.data['id']
        self.auth(self.other_doctor_user);self.assertEqual(self.client.get('/api/v1/prescriptions/').data['count'],0);self.assertEqual(self.client.get('/api/v1/examinations/').data['count'],1)
        self.auth(self.patient_user);self.assertEqual(self.client.get('/api/v1/prescriptions/').data['count'],1);self.assertEqual(self.client.get('/api/v1/examinations/').data['count'],0)
        self.auth(self.admin);response=self.client.post(f'/api/v1/examinations/{order_id}/report/',{'findings':'未见明显异常','conclusion':'颅脑 MRI 平扫未见明显异常'},format='json');self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.post(f'/api/v1/examinations/{order_id}/publish/').status_code,200)
        self.auth(self.patient_user);self.assertEqual(self.client.get('/api/v1/examinations/').data['count'],1)

    def test_prescription_payment_dispenses_medicine_deducts_stock_and_records_income(self):
        record=self.confirmed_record();medicine=Medicine.objects.create(name='阿莫西林胶囊',specification='0.25g×24粒',unit='盒',price='19.50',stock=10)
        self.auth(self.doctor_user);response=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'遵医嘱服用','items':[{'medicine_id':medicine.pk,'dosage':'0.5g','frequency':'每日两次','duration':'3天','quantity':2}]},format='json')
        self.assertEqual(response.status_code,201,response.data);prescription=Prescription.objects.get(pk=response.data['id']);bill=prescription.billing_record
        self.assertEqual(bill.status,BillingRecord.Status.UNPAID);self.assertEqual(str(bill.amount),'39.00');self.assertEqual(bill.category,BillingRecord.Category.MEDICINE);medicine.refresh_from_db();self.assertEqual(medicine.stock,10)
        self.auth(self.patient_user);response=self.client.post(f'/api/v1/billing-records/{bill.pk}/pay/',{'payment_method':'演示支付'},format='json');self.assertEqual(response.status_code,200,response.data)
        medicine.refresh_from_db();prescription.refresh_from_db();bill.refresh_from_db();self.assertEqual(medicine.stock,8);self.assertEqual(prescription.status,Prescription.Status.DISPENSED);self.assertIsNotNone(prescription.dispensed_at);self.assertEqual(bill.status,BillingRecord.Status.PAID)
        response=self.client.post(f'/api/v1/billing-records/{bill.pk}/pay/',{'payment_method':'重复支付'},format='json');self.assertEqual(response.status_code,400);medicine.refresh_from_db();self.assertEqual(medicine.stock,8)
        self.auth(self.admin);response=self.client.get('/api/v1/statistics/overview/');self.assertEqual(response.status_code,200);self.assertIn(['累计结算','¥39.00'],response.data['cards'])

    def test_prescription_payment_rolls_back_when_stock_is_insufficient(self):
        record=self.confirmed_record();medicine=Medicine.objects.create(name='稀缺药品',specification='1mg',unit='盒',price='12.00',stock=1)
        self.auth(self.doctor_user);response=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'库存测试','items':[{'medicine_id':medicine.pk,'dosage':'1mg','frequency':'每日一次','duration':'2天','quantity':2}]},format='json');self.assertEqual(response.status_code,201,response.data)
        prescription=Prescription.objects.get(pk=response.data['id']);bill=prescription.billing_record;self.auth(self.patient_user);response=self.client.post(f'/api/v1/billing-records/{bill.pk}/pay/',format='json');self.assertEqual(response.status_code,400,response.data)
        medicine.refresh_from_db();prescription.refresh_from_db();bill.refresh_from_db();self.assertEqual(medicine.stock,1);self.assertEqual(prescription.status,Prescription.Status.ISSUED);self.assertEqual(bill.status,BillingRecord.Status.UNPAID)

    def test_examination_item_creates_unique_bill_and_cancel_syncs_it(self):
        record=self.confirmed_record();item=ExaminationItem.objects.create(name='CT 平扫',category='imaging',price='360.00')
        self.auth(self.doctor_user);response=self.client.post('/api/v1/examinations/',{'record_id':record.pk,'item_id':item.pk,'type':'ct','clinical_question':'排除异常'},format='json')
        self.assertEqual(response.status_code,201,response.data);order=ExaminationOrder.objects.get(pk=response.data['id']);self.assertEqual(order.billing_record.amount,Decimal('360.00'))
        self.assertEqual(BillingRecord.objects.filter(examination=order).count(),1)
        response=self.client.post(f'/api/v1/examinations/{order.pk}/cancel/');self.assertEqual(response.status_code,200,response.data);order.billing_record.refresh_from_db();self.assertEqual(order.billing_record.status,BillingRecord.Status.CANCELLED)

    def test_bed_cannot_be_double_occupied_and_is_released_with_discharge_bill(self):
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        first=InpatientAdmission.objects.create(patient=self.patient,attending_doctor=self.doctor,department=self.department,bed=bed,ward='',bed_no='',admission_diagnosis='偏头痛')
        second=InpatientAdmission.objects.create(patient=self.other_patient,attending_doctor=self.doctor,department=self.department,bed=bed,ward='',bed_no='',admission_diagnosis='观察')
        self.auth(self.doctor_user);self.assertEqual(self.client.post(f'/api/v1/inpatients/{first.pk}/admit/').status_code,200);bed.refresh_from_db();self.assertTrue(bed.is_occupied)
        response=self.client.post(f'/api/v1/inpatients/{second.pk}/admit/');self.assertEqual(response.status_code,400,response.data)
        response=self.client.post(f'/api/v1/inpatients/{first.pk}/discharge/',{'discharge_summary':'病情好转'},format='json');self.assertEqual(response.status_code,200,response.data);bed.refresh_from_db();self.assertFalse(bed.is_occupied);self.assertEqual(BillingRecord.objects.filter(admission=first).count(),1)

    def test_dispensing_creates_stock_movement(self):
        record=self.confirmed_record();medicine=Medicine.objects.create(name='流水测试药',specification='1mg',price='10',stock=3)
        self.auth(self.doctor_user);response=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'','items':[{'medicine_id':medicine.pk,'dosage':'1mg','frequency':'每日一次','duration':'1天','quantity':1}]},format='json');bill=Prescription.objects.get(pk=response.data['id']).billing_record
        self.auth(self.patient_user);self.assertEqual(self.client.post(f'/api/v1/billing-records/{bill.pk}/pay/').status_code,200)
        movement=MedicineStockMovement.objects.get(medicine=medicine);self.assertEqual(movement.quantity,-1);self.assertEqual(movement.balance_after,2)

    def test_doctor_workspace_is_scoped_and_password_can_change(self):
        appointment=self.create_appointment();self.auth(self.doctor_user);response=self.client.get(f'/api/v1/appointments/{appointment.pk}/workspace/');self.assertEqual(response.status_code,200,response.data);self.assertIn('history',response.data)
        self.auth(self.other_doctor_user);self.assertEqual(self.client.get(f'/api/v1/appointments/{appointment.pk}/workspace/').status_code,404)
        self.auth(self.patient_user);response=self.client.post('/api/v1/auth/change-password/',{'current_password':'PatientPass123!','new_password':'NewPatientPass123!','new_password_confirm':'NewPatientPass123!'},format='json');self.assertEqual(response.status_code,200,response.data);self.patient_user.refresh_from_db();self.assertTrue(self.patient_user.check_password('NewPatientPass123!'))

    def test_any_doctor_can_collaborate_on_examination_report(self):
        record=self.confirmed_record();order=ExaminationOrder.objects.create(patient=self.patient,doctor=self.doctor,record=record,type='ct',clinical_question='排除颅内异常')
        self.auth(self.other_doctor_user);response=self.client.post(f'/api/v1/examinations/{order.pk}/start/');self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['status'],ExaminationOrder.Status.IN_PROGRESS)
        response=self.client.post(f'/api/v1/examinations/{order.pk}/report/',{'findings':'未见明显异常','conclusion':'CT 平扫未见明显异常'},format='json');self.assertEqual(response.status_code,200,response.data)
        order.refresh_from_db();self.assertEqual(order.status,ExaminationOrder.Status.COMPLETED);self.assertEqual(order.report.status,ExaminationReport.Status.DRAFT)
        response=self.client.post(f'/api/v1/examinations/{order.pk}/publish/');self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['status'],ExaminationOrder.Status.PUBLISHED)
        order.report.refresh_from_db();self.assertEqual(order.report.published_by,self.other_doctor_user)
        self.auth(self.doctor_user)
        response=self.client.post(f'/api/v1/examinations/{order.pk}/report/',{'findings':'覆盖','conclusion':'覆盖'},format='json');self.assertEqual(response.status_code,400)
        self.auth(self.patient_user);response=self.client.get('/api/v1/examinations/');self.assertEqual(response.status_code,200);self.assertEqual(response.data['count'],1);self.assertEqual(response.data['results'][0]['report']['conclusion'],'CT 平扫未见明显异常')

    def test_medical_file_download_is_object_scoped(self):
        record=self.confirmed_record();order=ExaminationOrder.objects.create(patient=self.patient,doctor=self.doctor,record=record,type='xray',clinical_question='检查',status=ExaminationOrder.Status.PUBLISHED)
        item=MedicalFile.objects.create(order=order,file=SimpleUploadedFile('report.pdf',b'%PDF-test',content_type='application/pdf'),original_name='report.pdf',file_type='pdf',size=9,uploaded_by=self.admin)
        self.auth(self.other_patient_user);self.assertEqual(self.client.get(f'/api/v1/medical-files/{item.pk}/download/').status_code,403)
        self.auth(self.patient_user);response=self.client.get(f'/api/v1/medical-files/{item.pk}/download/');self.assertEqual(response.status_code,200)

    def test_ai_service_is_disabled_by_default(self):
        record=self.confirmed_record();order=ExaminationOrder.objects.create(patient=self.patient,doctor=self.doctor,record=record,type='mri',clinical_question='检查',status=ExaminationOrder.Status.PUBLISHED)
        item=MedicalFile.objects.create(order=order,file=SimpleUploadedFile('image.png',b'png',content_type='image/png'),original_name='image.png',file_type='png',size=3,uploaded_by=self.admin)
        service=AIService.objects.create(name='MRI 辅助分析',service_type='mri_analysis',is_enabled=False)
        self.auth(self.doctor_user);response=self.client.post('/api/v1/ai/tasks/',{'patient':self.patient.pk,'file':item.pk,'service':service.pk},format='json');self.assertEqual(response.status_code,400)

    def test_role_specific_statistics(self):
        for user in (self.admin,self.doctor_user,self.patient_user):
            self.auth(user);response=self.client.get('/api/v1/statistics/overview/');self.assertEqual(response.status_code,200);self.assertEqual(len(response.data['cards']),4 if user.role==User.Role.PATIENT else 6)

    def test_role_specific_command_dashboard(self):
        appointment=self.create_appointment()
        self.auth(self.admin);response=self.client.get('/api/v1/statistics/dashboard/?range=30d')
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['meta']['role'],User.Role.ADMIN);self.assertEqual(len(response.data['kpis']),6)
        for key in ('timeseries','department_workload','doctor_workload','billing_categories','workflow','alerts'):self.assertIn(key,response.data)
        self.assertEqual(len(response.data['timeseries']),30)
        self.assertEqual(self.client.get('/api/v1/statistics/dashboard/?range=year').status_code,400)
        self.auth(self.doctor_user);response=self.client.get('/api/v1/statistics/dashboard/?range=7d')
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['meta']['role'],User.Role.DOCTOR);self.assertIn('today_schedule',response.data);self.assertIn('examination_queue',response.data);self.assertNotIn('billing_categories',response.data)
        self.auth(self.patient_user);response=self.client.get('/api/v1/statistics/dashboard/?range=7d')
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['meta']['role'],User.Role.PATIENT);self.assertEqual(response.data['next_appointment']['id'],appointment.id);self.assertNotIn('doctor_workload',response.data)

    def test_admin_can_create_doctor_and_generate_slots(self):
        self.auth(self.admin);response=self.client.post('/api/v1/users/',{'username':'newdoctor','full_name':'王医师','password':'StrongPass123!','role':'doctor','phone':'13500000000','department_id':self.department.pk,'title':'住院医师','specialty':'神经内科'},format='json')
        self.assertEqual(response.status_code,201,response.data);doctor=DoctorProfile.objects.get(user__username='newdoctor');self.assertEqual(doctor.department,self.department);self.assertEqual(response.data['doctor_no'],doctor.doctor_no);self.assertEqual(response.data['department_name'],self.department.name)
        response=self.client.post('/api/v1/schedules/',{'doctor':doctor.pk,'date':str(date.today()+timedelta(days=2)),'start_time':'14:00:00','end_time':'16:00:00','slot_minutes':30},format='json')
        self.assertEqual(response.status_code,201,response.data);self.assertEqual(response.data['total_slots'],4);self.assertEqual(response.data['available_slots'],4)

    def test_admin_doctor_creation_requires_password_and_active_department(self):
        self.auth(self.admin);payload={'username':'incomplete-doctor','full_name':'未完成医师','role':'doctor','department_id':self.department.pk}
        response=self.client.post('/api/v1/users/',payload,format='json');self.assertEqual(response.status_code,400,response.data);self.assertFalse(User.objects.filter(username='incomplete-doctor').exists())
        self.department.status=Department.Status.INACTIVE;self.department.save(update_fields=['status','updated_at']);payload['password']='StrongPass123!'
        response=self.client.post('/api/v1/users/',payload,format='json');self.assertEqual(response.status_code,400,response.data);self.assertFalse(User.objects.filter(username='incomplete-doctor').exists())

    def test_overlapping_schedule_is_rejected(self):
        self.auth(self.admin);response=self.client.post('/api/v1/schedules/',{'doctor':self.doctor.pk,'date':str(self.schedule.date),'start_time':'09:30:00','end_time':'10:30:00','slot_minutes':30},format='json')
        self.assertEqual(response.status_code,400,response.data)

    def test_role_profiles_are_self_service_and_isolated(self):
        self.auth(self.patient_user);response=self.client.patch('/api/v1/patients/me/',{'gender':'female','blood_group':'A+','allergies':'青霉素'},format='json')
        self.assertEqual(response.status_code,200,response.data);self.patient.refresh_from_db();self.assertEqual(self.patient.allergies,'青霉素')
        response=self.client.patch(f'/api/v1/patients/{self.other_patient.pk}/',{'blood_group':'B+'},format='json');self.assertEqual(response.status_code,404)
        self.auth(self.doctor_user);response=self.client.patch('/api/v1/doctors/me/',{'specialty':'头痛与脑血管病','is_available':False},format='json')
        self.assertEqual(response.status_code,200,response.data);self.doctor.refresh_from_db();self.assertFalse(self.doctor.is_available)

    def test_doctor_can_finish_visit_from_confirmed_record(self):
        record=self.confirmed_record();self.auth(self.doctor_user);response=self.client.post(f'/api/v1/medical-records/{record.pk}/complete-visit/')
        self.assertEqual(response.status_code,200,response.data);record.appointment.refresh_from_db();self.assertEqual(record.appointment.status,Appointment.Status.COMPLETED);self.assertIsNotNone(record.appointment.completed_at)

    def test_inpatient_billing_and_medicine_workflows(self):
        bed=WardBed.objects.create(department=self.department,ward_name='神经内科病区',bed_no='A-01',daily_rate='120.00')
        self.auth(self.admin);response=self.client.post('/api/v1/inpatients/',{'patient_id':self.patient.pk,'doctor_id':self.doctor.pk,'department_id':self.department.pk,'bed_id':bed.pk,'admission_diagnosis':'偏头痛待查'},format='json')
        self.assertEqual(response.status_code,201,response.data);admission_id=response.data['id'];self.assertEqual(self.client.post(f'/api/v1/inpatients/{admission_id}/admit/').status_code,200)
        self.auth(self.doctor_user);response=self.client.post(f'/api/v1/inpatients/{admission_id}/discharge/',{'discharge_summary':'症状缓解，按时复诊。'},format='json');self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['status'],InpatientAdmission.Status.DISCHARGED)
        self.auth(self.admin);response=self.client.post('/api/v1/billing-records/',{'patient_id':self.patient.pk,'category':'inpatient','description':'住院综合费用','amount':'680.00'},format='json');self.assertEqual(response.status_code,201,response.data);bill_id=response.data['id']
        self.auth(self.patient_user);response=self.client.post(f'/api/v1/billing-records/{bill_id}/pay/',{'payment_method':'演示支付'},format='json');self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['status'],BillingRecord.Status.PAID)
        self.auth(self.admin);medicine=Medicine.objects.create(name='测试药品',specification='10mg',unit='盒',stock=5);response=self.client.post(f'/api/v1/medicines/{medicine.pk}/adjust-stock/',{'delta':8},format='json');self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['stock'],13)
