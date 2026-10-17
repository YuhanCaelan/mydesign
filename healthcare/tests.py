import io
from datetime import date,datetime,time,timedelta
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase
from .models import *
from .services import finish_admission,generate_slots

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

    def test_appointment_date_filter_scopes_history_and_validates_format(self):
        appointment=self.create_appointment();self.auth(self.patient_user);day=str(self.schedule.date)
        response=self.client.get('/api/v1/appointments/',{'date':day})
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['count'],1);self.assertEqual(response.data['results'][0]['id'],appointment.pk)
        other_day=str(date.today()+timedelta(days=3))
        self.assertEqual(self.client.get('/api/v1/appointments/',{'date':other_day}).data['count'],0)
        response=self.client.get('/api/v1/appointments/',{'date':'2026/01/01'})
        self.assertEqual(response.status_code,400);self.assertIn('date',response.data['errors'])

    def test_appointment_state_machine_and_slot_release(self):
        appointment=self.create_appointment();self.auth(self.patient_user)
        response=self.client.post(f'/api/v1/appointments/{appointment.pk}/cancel/');self.assertEqual(response.status_code,200,response.data)
        appointment.refresh_from_db();self.slot.refresh_from_db();self.assertEqual(appointment.status,'cancelled');self.assertEqual(self.slot.status,'available')
        response=self.client.post(f'/api/v1/appointments/{appointment.pk}/cancel/');self.assertEqual(response.status_code,400)

    def test_cancelled_slot_can_be_rebooked_and_outpatient_history_is_accurate(self):
        first=self.create_appointment();self.auth(self.patient_user)
        self.assertEqual(self.client.post(f'/api/v1/appointments/{first.pk}/cancel/').status_code,200)
        self.auth(self.doctor_user);day=str(self.schedule.date)
        available=self.client.get('/api/v1/schedules/outpatient/',{'date':day,'status':'available'})
        slot=next(row for group in available.data['results'] for schedule in group['schedules'] for row in schedule['slots'] if row['id']==self.slot.pk)
        self.assertIsNone(slot['appointment']);self.assertEqual(slot['state'],'available')
        self.auth(self.other_patient_user);response=self.client.post('/api/v1/appointments/',{'slot_id':self.slot.pk,'reason':'取消后重新预约'},format='json')
        self.assertEqual(response.status_code,201,response.data);second=Appointment.objects.get(pk=response.data['id'])
        self.assertEqual(Appointment.objects.filter(slot=self.slot).count(),2)
        self.auth(self.doctor_user);current=self.client.get('/api/v1/schedules/outpatient/',{'date':day})
        slot=next(row for group in current.data['results'] for schedule in group['schedules'] for row in schedule['slots'] if row['id']==self.slot.pk)
        self.assertEqual(slot['appointment']['id'],second.pk);self.assertEqual(slot['appointment']['status'],'pending');self.assertEqual(slot['appointment']['patient']['id'],self.other_patient.pk)
        history=self.client.get('/api/v1/schedules/outpatient/',{'date':day,'status':'cancelled'})
        slot=next(row for group in history.data['results'] for schedule in group['schedules'] for row in schedule['slots'] if row['id']==self.slot.pk)
        self.assertEqual(slot['appointment']['id'],first.pk);self.assertEqual(slot['state'],'cancelled')

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
        self.auth(self.other_doctor_user);self.assertEqual(self.client.get('/api/v1/prescriptions/').data['count'],0);self.assertEqual(self.client.get('/api/v1/examinations/').data['count'],0)
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

    def test_doctor_with_patient_relationship_can_collaborate_on_examination_report(self):
        record=self.confirmed_record();order=ExaminationOrder.objects.create(patient=self.patient,doctor=self.doctor,record=record,type='ct',clinical_question='排除颅内异常')
        schedule=DoctorSchedule.objects.create(doctor=self.other_doctor,date=date.today()+timedelta(days=2),start_time=time(9),end_time=time(10),slot_minutes=60)
        slot=AppointmentSlot.objects.create(schedule=schedule,start_time=time(9),end_time=time(10))
        Appointment.objects.create(patient=self.patient,doctor=self.other_doctor,slot=slot,reason='协作诊疗')
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

    def test_bed_and_examination_catalog_filters(self):
        available=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='100.00')
        occupied=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='02',daily_rate='100.00',is_occupied=True)
        inactive=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='03',daily_rate='100.00',is_active=False)
        lab=ExaminationItem.objects.create(name='血常规',category='lab',price='30.00')
        disabled=ExaminationItem.objects.create(name='停用项目',category='other',price='0.00',is_active=False)
        self.auth(self.admin)
        response=self.client.get('/api/v1/ward-beds/',{'department':self.department.pk,'available':'true'})
        self.assertEqual(response.status_code,200,response.data);self.assertEqual([row['id'] for row in response.data['results']],[available.pk])
        response=self.client.get('/api/v1/ward-beds/',{'active':'false'})
        self.assertEqual([row['id'] for row in response.data['results']],[inactive.pk])
        response=self.client.get('/api/v1/examination-items/',{'active':'true'})
        self.assertEqual([row['id'] for row in response.data['results']],[lab.pk])
        response=self.client.get('/api/v1/examination-items/',{'active':'false'})
        self.assertEqual([row['id'] for row in response.data['results']],[disabled.pk])

    def test_stock_movement_filters_and_billing_source_ids(self):
        medicine=Medicine.objects.create(name='流水查询药',specification='1mg',price='10.00',stock=3)
        receipt=MedicineStockMovement.objects.create(medicine=medicine,movement_type='receipt',quantity=3,balance_after=3,operator=self.admin,note='初始入库')
        adjustment=MedicineStockMovement.objects.create(medicine=medicine,movement_type='adjustment',quantity=2,balance_after=5,operator=self.admin,note='补货')
        self.auth(self.admin)
        response=self.client.get('/api/v1/medicine-stock-movements/',{'movement_type':'receipt','date_from':str(date.today())})
        self.assertEqual(response.status_code,200,response.data);self.assertEqual([row['id'] for row in response.data['results']],[receipt.pk])
        record=self.confirmed_record();item=ExaminationItem.objects.create(name='检查计费来源',category='lab',price='45.00')
        self.auth(self.doctor_user);created=self.client.post('/api/v1/examinations/',{'record_id':record.pk,'item_id':item.pk,'type':'lab','clinical_question':'演示'},format='json')
        self.assertEqual(created.status_code,201,created.data)
        bill=BillingRecord.objects.get(examination_id=created.data['id'])
        self.auth(self.admin);bill_response=self.client.get(f'/api/v1/billing-records/{bill.pk}/')
        self.assertEqual(bill_response.status_code,200,bill_response.data);self.assertEqual(bill_response.data['source_type'],'examination');self.assertEqual(bill_response.data['examination_id'],created.data['id'])

    # ------------------------------------------------------------------
    # 病床看板与住院详情
    # ------------------------------------------------------------------
    def admit_via_api(self,bed,patient=None,doctor=None,diagnosis='偏头痛待查'):
        payload={'patient_id':(patient or self.patient).pk,'doctor_id':(doctor or self.doctor).pk,'department_id':bed.department_id,'bed_id':bed.pk,'admission_diagnosis':diagnosis}
        self.auth(self.admin);response=self.client.post('/api/v1/inpatients/',payload,format='json')
        self.assertEqual(response.status_code,201,response.data);admission_id=response.data['id']
        self.assertEqual(self.client.post(f'/api/v1/inpatients/{admission_id}/admit/').status_code,200,response.data)
        bed.refresh_from_db();self.assertTrue(bed.is_occupied)
        return InpatientAdmission.objects.get(pk=admission_id)

    def test_bed_board_exposes_current_patient_and_doctor_can_read_occupancy(self):
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        admission=self.admit_via_api(bed)
        InpatientAdmission.objects.filter(pk=admission.pk).update(admitted_at=timezone.now()-timedelta(days=2))
        self.auth(self.doctor_user)
        response=self.client.get('/api/v1/ward-beds/')
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['count'],1)
        occupancy=response.data['results'][0]['occupancy']
        self.assertIsNotNone(occupancy);self.assertEqual(occupancy['admission_no'],admission.admission_no)
        self.assertEqual(occupancy['patient_name'],'测试患者');self.assertEqual(occupancy['patient_no'],self.patient.patient_no)
        self.assertEqual(occupancy['doctor_name'],'张医师');self.assertEqual(occupancy['daily_rate_snapshot'],'120.00');self.assertEqual(occupancy['days_admitted'],3)
        response=self.client.get('/api/v1/ward-beds/',{'occupancy':'occupied'})
        self.assertEqual([row['id'] for row in response.data['results']],[bed.pk])
        response=self.client.get('/api/v1/ward-beds/',{'occupancy':'available','ward':'A 病区','department':self.department.pk})
        self.assertEqual(response.data['count'],0)
        detail=self.client.get(f'/api/v1/ward-beds/{bed.pk}/occupancy/')
        self.assertEqual(detail.status_code,200,detail.data);self.assertTrue(detail.data['occupied'])
        self.assertEqual(detail.data['admission']['admission_no'],admission.admission_no);self.assertEqual(detail.data['admission']['patient_name'],'测试患者')
        self.assertTrue(AuditLog.objects.filter(action='read',resource='ward_bed',object_id=str(bed.pk)).exists())

    def test_patient_cannot_read_ward_bed_board_or_other_admissions(self):
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        admission=self.admit_via_api(bed)
        self.auth(self.patient_user)
        self.assertEqual(self.client.get('/api/v1/ward-beds/').status_code,403)
        self.assertEqual(self.client.get(f'/api/v1/ward-beds/{bed.pk}/occupancy/').status_code,403)
        response=self.client.get('/api/v1/inpatients/')
        self.assertEqual(response.status_code,200,response.data);self.assertEqual([row['id'] for row in response.data['results']],[admission.pk])
        self.auth(self.other_patient_user)
        self.assertEqual(self.client.get('/api/v1/inpatients/').data['count'],0)
        self.assertEqual(self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/').status_code,404)

    def test_occupied_bed_cannot_change_department_ward_number_or_be_disabled(self):
        other=Department.objects.create(name='骨科演示')
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        self.admit_via_api(bed)
        self.auth(self.admin)
        for payload in ({'ward_name':'B 病区'},{'bed_no':'99'},{'is_active':False},{'department':other.pk}):
            response=self.client.patch(f'/api/v1/ward-beds/{bed.pk}/',payload,format='json')
            self.assertEqual(response.status_code,400,payload)
        bed.refresh_from_db();self.assertEqual(bed.ward_name,'A 病区');self.assertEqual(bed.bed_no,'01');self.assertTrue(bed.is_active);self.assertEqual(bed.department,self.department)
        response=self.client.patch(f'/api/v1/ward-beds/{bed.pk}/',{'daily_rate':'150.00'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        admission=InpatientAdmission.objects.get(bed=bed);self.assertEqual(admission.daily_rate_snapshot,Decimal('120.00'))
        self.assertTrue(AuditLog.objects.filter(action='update',resource='ward_bed',object_id=str(bed.pk)).exists())

    def test_doctor_patient_scope_is_limited_to_appointment_relationship(self):
        self.auth(self.doctor_user);self.assertEqual(self.client.get('/api/v1/patients/').data['count'],0)
        appointment=self.create_appointment()
        self.auth(self.doctor_user);response=self.client.get('/api/v1/patients/')
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['count'],1);self.assertEqual(response.data['results'][0]['id'],appointment.patient_id)
        self.auth(self.patient_user);self.assertEqual(self.client.post(f'/api/v1/appointments/{appointment.pk}/cancel/').status_code,200)
        self.auth(self.doctor_user);self.assertEqual(self.client.get('/api/v1/patients/').data['count'],0)
        self.auth(self.admin);self.assertEqual(self.client.get('/api/v1/patients/').data['count'],2)

    # ------------------------------------------------------------------
    # 费用归集与住院费用清单
    # ------------------------------------------------------------------
    def test_prescription_item_keeps_unit_price_snapshot(self):
        record=self.confirmed_record();medicine=Medicine.objects.create(name='快照药品',specification='1mg',price='20.00',stock=10)
        self.auth(self.doctor_user)
        response=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'','items':[{'medicine_id':medicine.pk,'dosage':'1mg','frequency':'每日一次','duration':'2天','quantity':2}]},format='json')
        self.assertEqual(response.status_code,201,response.data);prescription=Prescription.objects.get(pk=response.data['id'])
        bill=prescription.billing_record;self.assertEqual(bill.amount,Decimal('40.00'))
        item=prescription.items.get();self.assertEqual(item.unit_price_snapshot,Decimal('20.00'));self.assertEqual(response.data['total_amount'],'40.00')
        medicine.price=Decimal('35.00');medicine.save(update_fields=['price','updated_at'])
        prescription.refresh_from_db();response=self.client.get(f'/api/v1/prescriptions/{prescription.pk}/')
        self.assertEqual(response.data['items'][0]['unit_price'],'20.00');self.assertEqual(response.data['total_amount'],'40.00');self.assertEqual(response.data['items'][0]['medicine_name'],'快照药品')
        second=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'','items':[{'medicine_id':medicine.pk,'dosage':'1mg','frequency':'每日一次','duration':'2天','quantity':1}]},format='json')
        self.assertEqual(second.status_code,201,second.data);self.assertEqual(second.data['total_amount'],'35.00')

    def test_history_without_price_snapshot_falls_back_to_original_bill_total(self):
        record=self.confirmed_record();medicine=Medicine.objects.create(name='历史药品',specification='1mg',price='20.00',stock=5)
        prescription=Prescription.objects.create(record=record,doctor=self.doctor)
        PrescriptionItem.objects.create(prescription=prescription,medicine=medicine,dosage='1mg',frequency='每日一次',duration='2天',quantity=2)
        BillingRecord.objects.create(patient=self.patient,prescription=prescription,category=BillingRecord.Category.MEDICINE,description='历史药品账单',amount='40.00')
        self.auth(self.doctor_user);response=self.client.get(f'/api/v1/prescriptions/{prescription.pk}/')
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['total_amount'],'40.00');self.assertEqual(response.data['items'][0]['unit_price'],'20.00')

    def test_new_charges_join_admission_with_patient_and_status_validation(self):
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        admission=self.admit_via_api(bed)
        record=self.confirmed_record();medicine=Medicine.objects.create(name='归集药品',specification='1mg',price='20.00',stock=10)
        self.auth(self.doctor_user)
        response=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'','admission_id':admission.pk,'items':[{'medicine_id':medicine.pk,'dosage':'1mg','frequency':'每日一次','duration':'2天','quantity':1}]},format='json')
        self.assertEqual(response.status_code,201,response.data);self.assertEqual(response.data['admission_id'],admission.pk);self.assertEqual(response.data['admission_no'],admission.admission_no)
        bill=Prescription.objects.get(pk=response.data['id']).billing_record;self.assertEqual(bill.inpatient_admission,admission)
        item=ExaminationItem.objects.create(name='住院检查',category='lab',price='45.00')
        response=self.client.post('/api/v1/examinations/',{'record_id':record.pk,'item_id':item.pk,'type':'lab','clinical_question':'住院期间检查','admission_id':admission.pk},format='json')
        self.assertEqual(response.status_code,201,response.data);order=ExaminationOrder.objects.get(pk=response.data['id']);self.assertEqual(order.billing_record.inpatient_admission,admission);self.assertEqual(response.data['admission_no'],admission.admission_no)
        other_admission=self.admit_via_api(WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='02',daily_rate='130.00'),patient=self.other_patient)
        self.auth(self.doctor_user)
        response=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'','admission_id':other_admission.pk,'items':[{'medicine_id':medicine.pk,'dosage':'1mg','frequency':'每日一次','duration':'2天','quantity':1}]},format='json')
        self.assertEqual(response.status_code,400,response.data)
        finish_admission(admission=admission,summary='病情好转')
        response=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'','admission_id':admission.pk,'items':[{'medicine_id':medicine.pk,'dosage':'1mg','frequency':'每日一次','duration':'2天','quantity':1}]},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.auth(self.admin);response=self.client.post('/api/v1/billing-records/',{'patient_id':self.patient.pk,'admission_id':other_admission.pk,'category':'other','description':'归集校验','amount':'10.00'},format='json')
        self.assertEqual(response.status_code,400,response.data)

    def test_admission_charge_breakdown_estimates_bed_fee_and_freezes_on_discharge(self):
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        admission=self.admit_via_api(bed)
        InpatientAdmission.objects.filter(pk=admission.pk).update(admitted_at=timezone.now()-timedelta(days=2))
        record=self.confirmed_record();medicine=Medicine.objects.create(name='费用清单药',specification='1mg',price='20.00',stock=10)
        self.auth(self.doctor_user)
        created=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'','admission_id':admission.pk,'items':[{'medicine_id':medicine.pk,'dosage':'1mg','frequency':'每日一次','duration':'2天','quantity':1}]},format='json')
        self.assertEqual(created.status_code,201,created.data);medicine_bill=Prescription.objects.get(pk=created.data['id']).billing_record
        item=ExaminationItem.objects.create(name='费用清单检查',category='lab',price='45.00')
        created=self.client.post('/api/v1/examinations/',{'record_id':record.pk,'item_id':item.pk,'type':'lab','clinical_question':'清单检查','admission_id':admission.pk},format='json')
        self.assertEqual(created.status_code,201,created.data);exam_bill=ExaminationOrder.objects.get(pk=created.data['id']).billing_record
        bed.daily_rate=Decimal('200.00');bed.save(update_fields=['daily_rate','updated_at'])
        self.auth(self.admin);manual=self.client.post('/api/v1/billing-records/',{'patient_id':self.patient.pk,'admission_id':admission.pk,'category':'other','description':'住院陪护费','amount':'30.00'},format='json')
        self.assertEqual(manual.status_code,201,manual.data);manual_bill=BillingRecord.objects.get(pk=manual.data['id'])
        self.assertEqual(manual_bill.inpatient_admission,admission)
        self.auth(self.doctor_user);response=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        self.assertEqual(response.status_code,200,response.data)
        summary=response.data['summary'];self.assertEqual(summary['billed_amount'],'95.00');self.assertEqual(summary['paid_amount'],'0.00');self.assertEqual(summary['unpaid_amount'],'95.00')
        self.assertEqual(summary['projected_bed_fee'],'360.00');self.assertEqual(summary['estimated_total'],'455.00')
        self.assertEqual(summary['bed_daily_rate'],'120.00');self.assertEqual(summary['days_admitted'],3);self.assertEqual(summary['billable_days'],3);self.assertFalse(summary['bed_bill_generated'])
        self.assertEqual({row['category'] for row in summary['categories']},{'medicine','examination','other'})
        self.assertEqual(response.data['admission']['days_admitted'],3);self.assertEqual(response.data['admission']['projected_bed_fee'],'360.00')
        self.assertEqual(response.data['items'][0]['charge_date'],str(timezone.localdate()))
        self.assertEqual({row['category'] for row in response.data['items']},{'medicine','examination','other'})
        filtered=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/',{'date_from':str(timezone.localdate()+timedelta(days=3))})
        self.assertEqual(filtered.status_code,200,filtered.data);self.assertEqual(filtered.data['items'],[]);self.assertEqual(filtered.data['summary']['billed_amount'],'0.00')
        self.assertEqual(filtered.data['summary']['projected_bed_fee'],'360.00')
        self.assertEqual(self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/',{'date_from':'2026/01/01'}).status_code,400)
        self.auth(self.other_patient_user);self.assertEqual(self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/').status_code,404)
        self.auth(self.doctor_user);self.assertEqual(self.client.post(f'/api/v1/billing-records/{manual_bill.pk}/cancel/').status_code,403)
        self.auth(self.admin);self.assertEqual(self.client.post(f'/api/v1/billing-records/{manual_bill.pk}/cancel/').status_code,200)
        response=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        summary=response.data['summary'];self.assertEqual(summary['billed_amount'],'65.00');self.assertEqual(summary['cancelled_amount'],'30.00');self.assertEqual(summary['cancelled_count'],1);self.assertEqual(summary['estimated_total'],'425.00')
        self.assertEqual([row['status'] for row in response.data['items']].count('cancelled'),1)
        self.auth(self.patient_user);self.assertEqual(self.client.post(f'/api/v1/billing-records/{medicine_bill.pk}/pay/',{'payment_method':'演示支付'},format='json').status_code,200)
        self.assertEqual(self.client.post(f'/api/v1/billing-records/{exam_bill.pk}/pay/',{'payment_method':'演示支付'},format='json').status_code,200)
        self.auth(self.doctor_user);response=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        summary=response.data['summary'];self.assertEqual(summary['paid_amount'],'65.00');self.assertEqual(summary['unpaid_amount'],'0.00')
        self.auth(self.doctor_user);discharge=self.client.post(f'/api/v1/inpatients/{admission.pk}/discharge/',{'discharge_summary':'症状缓解，予以出院。'},format='json')
        self.assertEqual(discharge.status_code,200,discharge.data)
        admission.refresh_from_db();bed.refresh_from_db();self.assertFalse(bed.is_occupied);self.assertEqual(admission.status,InpatientAdmission.Status.DISCHARGED)
        self.assertEqual(BillingRecord.objects.filter(admission=admission).count(),1)
        bed_bill=BillingRecord.objects.get(admission=admission)
        self.assertEqual(bed_bill.category,BillingRecord.Category.INPATIENT);self.assertEqual(bed_bill.amount,Decimal('360.00'));self.assertEqual(bed_bill.patient,self.patient)
        for _ in range(2):
            self.assertEqual(self.client.post(f'/api/v1/inpatients/{admission.pk}/discharge/',{'discharge_summary':'重复出院'},format='json').status_code,400)
        self.assertEqual(BillingRecord.objects.filter(admission=admission).count(),1)
        self.assertEqual(BillingRecord.objects.get(pk=bed_bill.pk).amount,Decimal('360.00'))
        response=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        summary=response.data['summary'];self.assertEqual(summary['projected_bed_fee'],'0.00');self.assertEqual(summary['billed_amount'],'425.00');self.assertEqual(summary['unpaid_amount'],'360.00');self.assertTrue(summary['bed_bill_generated'])
        self.auth(self.patient_user);response=self.client.get('/api/v1/inpatients/')
        row=next(entry for entry in response.data['results'] if entry['id']==admission.pk)
        self.assertEqual(row['status'],InpatientAdmission.Status.DISCHARGED);self.assertEqual(row['days_admitted'],0)
        self.assertEqual(row['charge_summary']['billed_amount'],'425.00');self.assertEqual(row['charge_summary']['unpaid_amount'],'360.00')
        self.assertEqual(row['charge_summary']['projected_bed_fee'],'0.00')
        self.assertEqual([event['key'] for event in row['timeline']],['created','admitted','discharged'])
        self.assertTrue(AuditLog.objects.filter(action='read',resource='inpatient_charges',object_id=str(admission.pk)).exists())

    def test_bed_fee_has_minimum_one_day_and_rejects_occupied_bed_reuse(self):
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='100.00')
        admission=self.admit_via_api(bed)
        self.auth(self.doctor_user)
        response=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        self.assertEqual(response.data['summary']['days_admitted'],1);self.assertEqual(response.data['summary']['projected_bed_fee'],'100.00')
        self.assertEqual(self.client.post(f'/api/v1/inpatients/{admission.pk}/discharge/',{'discharge_summary':'当天出院。'},format='json').status_code==200,True)
        bed_bill=BillingRecord.objects.get(admission=admission)
        self.assertEqual(bed_bill.amount,Decimal('100.00'));self.assertIn('住院 1 天',bed_bill.description)
        admission.refresh_from_db();blocked=self.client.patch(f'/api/v1/inpatients/{admission.pk}/',{'bed_id':bed.pk},format='json')
        self.assertEqual(blocked.status_code,400,blocked.data)
        bed.daily_rate=Decimal('300.00');bed.save(update_fields=['daily_rate','updated_at'])
        self.assertEqual(BillingRecord.objects.get(pk=bed_bill.pk).amount,Decimal('100.00'))
        self.assertEqual(admission.daily_rate_snapshot,Decimal('100.00'))

    # ------------------------------------------------------------------
    # 看板聚合接口与费用明细校准
    # ------------------------------------------------------------------
    def test_bed_board_groups_returns_every_bed_complete_options_and_accurate_stats(self):
        beds=[]
        for index in range(1,31):beds.append(WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no=f'{index:02d}',daily_rate='120.00'))
        other_department=Department.objects.create(name='呼吸内科演示')
        beds.append(WardBed.objects.create(department=other_department,ward_name='B 病区',bed_no='01',daily_rate='150.00'))
        beds.append(WardBed.objects.create(department=other_department,ward_name='B 病区',bed_no='02',daily_rate='150.00',is_active=False))
        admission=self.admit_via_api(beds[0])
        InpatientAdmission.objects.filter(pk=admission.pk).update(admitted_at=timezone.now()-timedelta(days=1))
        self.auth(self.doctor_user);response=self.client.get('/api/v1/ward-beds/board/')
        self.assertEqual(response.status_code,200,response.data);data=response.data
        self.assertEqual(data['total'],WardBed.objects.count());self.assertEqual(len(data['beds']),WardBed.objects.count())
        self.assertEqual(len(data['groups']),2)
        self.assertEqual({group['ward_name'] for group in data['groups']},{'A 病区','B 病区'})
        self.assertEqual(len(data['departments']),2)
        self.assertEqual({item['department_name'] for item in data['departments']},{self.department.name,other_department.name})
        self.assertEqual(sum(item['stats']['total'] for item in data['departments']),data['total'])
        self.assertEqual(next(item for item in data['departments'] if item['department_id']==other_department.pk)['stats'],{'total':2,'available':1,'occupied':0,'inactive':1})
        self.assertEqual([ward['ward_name'] for item in data['departments'] for ward in item['wards']],['B 病区','A 病区'])
        self.assertEqual([item['department_name'] for item in data['departments']],[other_department.name,self.department.name])
        self.assertEqual(sum(group['stats']['total'] for group in data['groups']),data['stats']['total'])
        self.assertEqual(sum(len(group['beds']) for group in data['groups']),data['total'])
        self.assertEqual(data['stats'],{'total':32,'available':30,'occupied':1,'inactive':1})
        self.assertEqual(data['global_stats'],data['stats'])
        self.assertEqual({option['name'] for option in data['options']['departments']},{self.department.name,other_department.name})
        self.assertEqual(len(data['options']['wards']),2)
        department_option=next(option for option in data['options']['departments'] if option['id']==self.department.pk)
        self.assertEqual(department_option['bed_count'],30)
        occupied=[bed for bed in data['beds'] if bed['status']=='occupied']
        self.assertEqual(len(occupied),1);card=occupied[0]
        self.assertEqual(card['status_label'],'住院中');self.assertEqual(card['bed_no'],'01');self.assertEqual(card['ward_name'],'A 病区')
        self.assertEqual(card['occupancy']['admission_no'],admission.admission_no);self.assertEqual(card['occupancy']['patient_name'],'测试患者');self.assertEqual(card['occupancy']['patient_no'],self.patient.patient_no)
        self.assertEqual(card['occupancy']['doctor_name'],'张医师');self.assertIsNotNone(card['occupancy']['admitted_at']);self.assertEqual(card['occupancy']['days_admitted'],2)
        self.assertEqual(card['daily_rate'],'120.00')
        self.assertEqual({bed['status_label'] for bed in data['beds'] if not bed['is_active']},{'停用'})
        self.assertTrue(all(bed['daily_rate'] for bed in data['beds']))
        filtered=self.client.get('/api/v1/ward-beds/board/',{'occupancy':'occupied'})
        self.assertEqual(filtered.data['total'],1);self.assertEqual(filtered.data['stats'],{'total':1,'available':0,'occupied':1,'inactive':0})
        self.assertEqual(len(filtered.data['options']['wards']),2)
        ward_filtered=self.client.get('/api/v1/ward-beds/board/',{'ward':'B 病区'})
        self.assertEqual(ward_filtered.data['total'],2);self.assertEqual({group['ward_name'] for group in ward_filtered.data['groups']},{'B 病区'})
        paginated=self.client.get('/api/v1/ward-beds/')
        self.assertEqual(paginated.data['count'],data['total'])
        self.assertLess(len(paginated.data['results']),data['total'])
        self.auth(self.admin);self.assertEqual(self.client.get('/api/v1/ward-beds/board/').status_code,200)
        self.auth(self.patient_user);self.assertEqual(self.client.get('/api/v1/ward-beds/board/').status_code,403)
        self.auth(self.other_patient_user);self.assertEqual(self.client.get('/api/v1/ward-beds/board/').status_code,403)

    def test_charge_details_split_multi_medicine_prescription_and_keep_totals_consistent(self):
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        admission=self.admit_via_api(bed)
        record=self.confirmed_record()
        first=Medicine.objects.create(name='明细药甲',specification='1mg',price='12.34',stock=20)
        second=Medicine.objects.create(name='明细药乙',specification='2mg',price='7.89',stock=20)
        self.auth(self.doctor_user)
        response=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'','admission_id':admission.pk,'items':[{'medicine_id':first.pk,'dosage':'1mg','frequency':'每日一次','duration':'3天','quantity':2},{'medicine_id':second.pk,'dosage':'2mg','frequency':'每日两次','duration':'3天','quantity':3}]},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['total_amount'],'48.35')
        charge=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        row=next(item for item in charge.data['items'] if item['category']=='medicine')
        self.assertEqual(row['charge_kind'],'prescription');self.assertEqual(row['details_consistent'],True);self.assertEqual(row['details_total'],'48.35')
        self.assertEqual(len(row['charge_details']),2)
        self.assertEqual({line['medicine_name'] for line in row['charge_details']},{'明细药甲','明细药乙'})
        first_line=next(line for line in row['charge_details'] if line['medicine_name']=='明细药甲')
        second_line=next(line for line in row['charge_details'] if line['medicine_name']=='明细药乙')
        self.assertEqual(first_line['unit_price'],'12.34');self.assertEqual(first_line['quantity'],2);self.assertEqual(first_line['amount'],'24.68');self.assertTrue(first_line['price_snapshot'])
        self.assertEqual(second_line['unit_price'],'7.89');self.assertEqual(second_line['quantity'],3);self.assertEqual(second_line['amount'],'23.67')
        line_total=sum(Decimal(line['amount']) for line in row['charge_details'])
        self.assertEqual(line_total,Decimal(row['amount']))
        self.assertEqual(Decimal(charge.data['summary']['detail_line_count'])>0,True)
        detailed_charges=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        self.assertEqual(Decimal(row['amount']),Decimal(detailed_charges.data['items'][0]['amount']))
        first.price=Decimal('99.00');first.save(update_fields=['price','updated_at'])
        refreshed=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        refreshed_row=next(item for item in refreshed.data['items'] if item['category']=='medicine')
        self.assertEqual(next(line for line in refreshed_row['charge_details'] if line['medicine_name']=='明细药甲')['unit_price'],'12.34')
        self.assertEqual(refreshed_row['amount'],'48.35')

    def test_historical_prescription_without_snapshot_uses_summary_line(self):
        record=self.confirmed_record();medicine=Medicine.objects.create(name='历史明细药',specification='1mg',price='20.00',stock=5)
        prescription=Prescription.objects.create(record=record,doctor=self.doctor)
        PrescriptionItem.objects.create(prescription=prescription,medicine=medicine,dosage='1mg',frequency='每日一次',duration='2天',quantity=2)
        bill=BillingRecord.objects.create(patient=self.patient,prescription=prescription,category=BillingRecord.Category.MEDICINE,description='历史药品账单',amount='40.00',inpatient_admission=self.admit_via_api(WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='09',daily_rate='120.00')))
        self.auth(self.doctor_user);response=self.client.get(f'/api/v1/inpatients/{bill.inpatient_admission_id}/charges/')
        row=next(item for item in response.data['items'] if item['id']==bill.pk)
        self.assertEqual(row['charge_kind'],'prescription_legacy');self.assertEqual(len(row['charge_details']),1)
        self.assertEqual(row['charge_details'][0]['medicine_name'],'历史明细药');self.assertEqual(row['charge_details'][0]['amount'],'40.00');self.assertIsNone(row['charge_details'][0]['unit_price'])
        self.assertEqual(row['details_total'],'40.00');self.assertEqual(row['details_consistent'],True)

    def test_payment_keeps_charge_date_and_reports_payment_date_separately(self):
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        admission=self.admit_via_api(bed)
        record=self.confirmed_record();medicine=Medicine.objects.create(name='日期校验药',specification='1mg',price='30.00',stock=5)
        self.auth(self.doctor_user)
        created=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'','admission_id':admission.pk,'items':[{'medicine_id':medicine.pk,'dosage':'1mg','frequency':'每日一次','duration':'1天','quantity':1}]},format='json')
        bill=BillingRecord.objects.get(prescription_id=created.data['id'])
        self.assertEqual(bill.created_at.date(),timezone.localdate())
        before=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        before_row=next(item for item in before.data['items'] if item['id']==bill.pk)
        self.assertEqual(before_row['charge_date'],str(timezone.localdate()));self.assertIsNone(before_row['payment_date'])
        BillingRecord.objects.filter(pk=bill.pk).update(created_at=timezone.now()-timedelta(days=4))
        self.auth(self.doctor_user);stale=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        stale_row=next(item for item in stale.data['items'] if item['id']==bill.pk)
        self.assertEqual(stale_row['charge_date'],str((timezone.now()-timedelta(days=4)).date()))
        self.auth(self.patient_user);paid=self.client.post(f'/api/v1/billing-records/{bill.pk}/pay/',{'payment_method':'演示支付'},format='json')
        self.assertEqual(paid.status_code,200,paid.data)
        self.assertEqual(paid.data['charge_date'],stale_row['charge_date'])
        self.assertIsNotNone(paid.data['payment_date']);self.assertEqual(paid.data['payment_date'][:10],str(timezone.localdate()))
        self.auth(self.doctor_user);after=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/')
        after_row=next(item for item in after.data['items'] if item['id']==bill.pk)
        self.assertEqual(after_row['charge_date'],stale_row['charge_date']);self.assertEqual(after_row['status'],BillingRecord.Status.PAID)
        self.assertIsNotNone(after_row['payment_date'])
        filtered=self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/',{'date_to':str((timezone.now()-timedelta(days=2)).date())})
        self.assertEqual([row['id'] for row in filtered.data['items']],[bill.pk])

    def test_inpatient_status_changes_are_limited_to_admin_and_attending_doctor(self):
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        admission=self.admit_via_api(bed)
        self.auth(self.other_doctor_user)
        self.assertEqual(self.client.post(f'/api/v1/inpatients/{admission.pk}/discharge/',{'discharge_summary':'非主治医师出院'},format='json').status_code,403)
        self.assertEqual(self.client.post(f'/api/v1/inpatients/{admission.pk}/cancel/').status_code,403)
        self.assertEqual(self.client.get(f'/api/v1/inpatients/{admission.pk}/charges/').status_code,200)
        admission.refresh_from_db();self.assertEqual(admission.status,InpatientAdmission.Status.ADMITTED)
        self.auth(self.doctor_user);self.assertEqual(self.client.post(f'/api/v1/inpatients/{admission.pk}/discharge/',{'discharge_summary':'主治医师出院。'},format='json').status_code,200)
        second=self.admit_via_api(WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='02',daily_rate='120.00'))
        self.auth(self.admin);self.assertEqual(self.client.post(f'/api/v1/inpatients/{second.pk}/discharge/',{'discharge_summary':'管理员出院。'},format='json').status_code,200)
        self.auth(self.patient_user);self.assertEqual(self.client.post(f'/api/v1/inpatients/{second.pk}/discharge/',{'discharge_summary':'患者越权'},format='json').status_code,403)

    def test_charge_association_migration_clears_bills_outside_admission_window(self):
        import importlib
        from django.apps import apps as django_apps
        migration=importlib.import_module('healthcare.migrations.0007_clear_misassociated_charges')
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        admission=self.admit_via_api(bed)
        inside=BillingRecord.objects.create(patient=self.patient,inpatient_admission=admission,category=BillingRecord.Category.OTHER,description='住院期间护理费',amount='20.00')
        before_admission=BillingRecord.objects.create(patient=self.patient,inpatient_admission=admission,category=BillingRecord.Category.OTHER,description='入院前误关联',amount='20.00')
        after_discharge=BillingRecord.objects.create(patient=self.patient,inpatient_admission=admission,category=BillingRecord.Category.OTHER,description='出院后误关联',amount='20.00')
        BillingRecord.objects.filter(pk=before_admission.pk).update(created_at=admission.admitted_at-timedelta(days=3))
        BillingRecord.objects.filter(pk=after_discharge.pk).update(created_at=timezone.now()+timedelta(days=2))
        InpatientAdmission.objects.filter(pk=admission.pk).update(status=InpatientAdmission.Status.DISCHARGED,discharged_at=timezone.now())
        cleared=migration.clear_misassociated_charges(django_apps,None)
        self.assertEqual(cleared,2)
        self.assertEqual(BillingRecord.objects.get(pk=inside.pk).inpatient_admission_id,admission.pk)
        self.assertIsNone(BillingRecord.objects.get(pk=before_admission.pk).inpatient_admission_id)
        self.assertIsNone(BillingRecord.objects.get(pk=after_discharge.pk).inpatient_admission_id)

    def test_bed_board_marks_bed_occupied_without_admission_as_data_warning(self):
        bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00',is_occupied=True)
        self.auth(self.admin);response=self.client.get('/api/v1/ward-beds/board/')
        card=next(item for item in response.data['beds'] if item['id']==bed.pk)
        self.assertEqual(card['status'],'occupied');self.assertEqual(card['status_label'],'住院中')
        self.assertIsNone(card['occupancy']);self.assertTrue(card['data_warning'])
        self.assertEqual(response.data['stats']['total'],1)

    # ------------------------------------------------------------------
    # 升级计划：账户分栏、科室可视化、门诊视图、检查费用、纵向病历、房间视图
    # ------------------------------------------------------------------
    def make_appointment(self,patient,doctor,day,hour=9,state=Appointment.Status.PENDING,reason='测试就诊'):
        schedule=DoctorSchedule.objects.create(doctor=doctor,date=day,start_time=time(hour),end_time=time(hour+2),slot_minutes=60)
        slot=AppointmentSlot.objects.create(schedule=schedule,start_time=time(hour),end_time=time(hour+1),status=AppointmentSlot.Status.BOOKED)
        AppointmentSlot.objects.create(schedule=schedule,start_time=time(hour+1),end_time=time(hour+2))
        return Appointment.objects.create(patient=patient,doctor=doctor,slot=slot,status=state,reason=reason)

    def test_admin_user_lists_are_split_by_role_and_filtered_server_side(self):
        self.auth(self.admin)
        response=self.client.get('/api/v1/users/',{'role':'doctor','page_size':1})
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['count'],2);self.assertEqual(len(response.data['results']),1)
        self.assertEqual(response.data['results'][0]['role'],'doctor');self.assertIn('doctor_no',response.data['results'][0]);self.assertIn('department_name',response.data['results'][0])
        response=self.client.get('/api/v1/users/',{'role':'patient','page_size':1})
        self.assertEqual(response.data['count'],2);self.assertEqual(response.data['results'][0]['role'],'patient');self.assertIn('patient_no',response.data['results'][0])
        self.other_doctor_user.is_active=False;self.other_doctor_user.save(update_fields=['is_active'])
        response=self.client.get('/api/v1/users/',{'role':'doctor','is_active':'false'})
        self.assertEqual(response.data['count'],1);self.assertEqual(response.data['results'][0]['id'],self.other_doctor_user.pk)
        self.assertEqual(self.client.get('/api/v1/users/',{'role':'admin'}).status_code,400)
        created=self.client.post('/api/v1/users/',{'username':'newpatient','full_name':'新患者','password':'SafePass123!','role':'patient','gender':'female','birth_date':'1990-01-01','address':'演示地址'},format='json')
        self.assertEqual(created.status_code,201,created.data);self.assertEqual(created.data['role'],'patient');self.assertTrue(created.data['patient_no'])
        profile=PatientProfile.objects.get(user__username='newpatient');self.assertEqual(profile.gender,'female');self.assertEqual(str(profile.birth_date),'1990-01-01');self.assertEqual(profile.address,'演示地址')

    def test_department_overview_uses_appointment_snapshot_and_role_scoped_visits(self):
        day=date.today()+timedelta(days=2)
        appointment=self.make_appointment(self.patient,self.doctor,day,state=Appointment.Status.IN_PROGRESS)
        self.assertEqual(appointment.department,self.department)
        self.auth(self.admin);response=self.client.get('/api/v1/departments/overview/',{'date':day})
        self.assertEqual(response.status_code,200,response.data);row=next(item for item in response.data['results'] if item['id']==self.department.pk)
        self.assertEqual(row['stats']['total'],1);self.assertEqual(row['stats']['in_progress'],1);self.assertEqual(row['stats']['active_doctors'],1);self.assertEqual(row['stats']['history_patients'],1)
        moved=Department.objects.create(name='调整后科室')
        self.doctor.department=moved;self.doctor.save(update_fields=['department','updated_at'])
        response=self.client.get('/api/v1/departments/overview/',{'date':day})
        original=next(item for item in response.data['results'] if item['id']==self.department.pk)
        moved_row=next(item for item in response.data['results'] if item['id']==moved.pk)
        self.assertEqual(original['stats']['total'],1);self.assertEqual(moved_row['stats']['total'],0)
        other_appointment=self.make_appointment(self.other_patient,self.other_doctor,day,hour=10)
        self.auth(self.doctor_user);response=self.client.get(f'/api/v1/departments/{self.department.pk}/visits/',{'date':day})
        self.assertEqual(response.status_code,200,response.data);self.assertEqual([item['id'] for item in response.data['results']],[appointment.pk])
        self.assertNotEqual(other_appointment.pk,appointment.pk)
        self.auth(self.patient_user);self.assertEqual(self.client.get('/api/v1/departments/overview/').status_code,403);self.assertEqual(self.client.get(f'/api/v1/departments/{self.department.pk}/visits/').status_code,403)
        self.auth(self.admin);response=self.client.get(f'/api/v1/departments/{self.department.pk}/history-patients/')
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['count'],0)
        self.make_appointment(self.other_patient,self.other_doctor,date.today()-timedelta(days=3),hour=11)
        response=self.client.get(f'/api/v1/departments/{self.department.pk}/history-patients/')
        self.assertEqual(response.data['count'],1);self.assertEqual(response.data['results'][0]['patient_id'],self.other_patient.pk);self.assertEqual(response.data['results'][0]['last_visit'],str(date.today()-timedelta(days=3)))
        doctors=self.client.get(f'/api/v1/departments/{moved.pk}/doctors/',{'date':day})
        self.assertEqual(doctors.status_code,200,doctors.data);self.assertTrue(any(item['id']==self.doctor.pk and item['schedule_count']>=1 for item in doctors.data['results']))

    def test_outpatient_view_hierarchy_filters_and_doctor_scope(self):
        day=date.today()+timedelta(days=2)
        appointment=self.make_appointment(self.patient,self.doctor,day,reason='头痛复诊')
        self.auth(self.admin);response=self.client.get('/api/v1/schedules/outpatient/',{'date':day})
        self.assertEqual(response.status_code,200,response.data);group=next(item for item in response.data['results'] if item['doctor']['id']==self.doctor.pk)
        self.assertIn('title',group['doctor']);self.assertIn('specialty',group['doctor']);self.assertIn('introduction',group['doctor'])
        slot=next(item for item in group['schedules'][0]['slots'] if item['appointment'])
        self.assertEqual(slot['appointment']['id'],appointment.pk);self.assertEqual(slot['appointment']['patient']['patient_no'],self.patient.patient_no);self.assertEqual(slot['appointment']['reason'],'头痛复诊')
        filtered=self.client.get('/api/v1/schedules/outpatient/',{'date':day,'status':'pending'})
        pending_slots=[row for group in filtered.data['results'] for schedule in group['schedules'] for row in schedule['slots']]
        self.assertTrue(pending_slots);self.assertTrue(all(row['appointment'] and row['appointment']['status']=='pending' for row in pending_slots))
        available=self.client.get('/api/v1/schedules/outpatient/',{'date':day,'status':'available'})
        available_slots=[row for group in available.data['results'] for schedule in group['schedules'] for row in schedule['slots']]
        self.assertTrue(available_slots);self.assertTrue(all(row['appointment'] is None for row in available_slots))
        self.auth(self.doctor_user);self.assertEqual(self.client.get('/api/v1/schedules/outpatient/',{'date':day}).status_code,200)
        self.auth(self.other_doctor_user);self.assertEqual(self.client.get('/api/v1/schedules/outpatient/',{'date':day}).data['results'],[])
        self.auth(self.patient_user);self.assertEqual(self.client.get('/api/v1/schedules/outpatient/').status_code,403)

    def test_patient_examination_costs_use_charge_dates_and_object_permissions(self):
        today=timezone.localdate();record=self.confirmed_record();item=ExaminationItem.objects.create(name='周期检查',category='lab',price='100.00')
        def exam_bill(day,amount,state):
            order=ExaminationOrder.objects.create(patient=self.patient,doctor=self.doctor,record=record,item=item,item_name_snapshot=item.name,price_snapshot=Decimal(amount),type='lab',status=ExaminationOrder.Status.PUBLISHED,clinical_question='周期统计')
            bill=BillingRecord.objects.create(patient=self.patient,examination=order,category=BillingRecord.Category.EXAMINATION,description='检查费用',amount=Decimal(amount),status=state,paid_at=timezone.now() if state==BillingRecord.Status.PAID else None)
            BillingRecord.objects.filter(pk=bill.pk).update(created_at=timezone.make_aware(datetime.combine(day,time(10))))
            return bill
        start=today-timedelta(days=6);end=today
        exam_bill(start,'10.00',BillingRecord.Status.UNPAID);exam_bill(today-timedelta(days=3),'20.50',BillingRecord.Status.PAID);exam_bill(end,'30.00',BillingRecord.Status.CANCELLED);exam_bill(today-timedelta(days=10),'99.00',BillingRecord.Status.PAID)
        other=exam_bill(today-timedelta(days=2),'5.00',BillingRecord.Status.PAID)
        # 另一位患者的账单不应进入统计
        BillingRecord.objects.filter(pk=other.pk).update(patient=self.other_patient)
        self.auth(self.patient_user);response=self.client.get('/api/v1/billing-records/examination-costs/',{'date_from':str(start),'date_to':str(end)})
        self.assertEqual(response.status_code,200,response.data);summary=response.data['summary']
        self.assertEqual(summary['total_amount'],'30.50');self.assertEqual(summary['paid_amount'],'20.50');self.assertEqual(summary['unpaid_amount'],'10.00');self.assertEqual(summary['cancelled_amount'],'30.00');self.assertEqual(summary['bill_count'],2);self.assertEqual(summary['cancelled_count'],1)
        self.assertEqual(len(response.data['trend']),7);self.assertEqual(response.data['trend'][0]['total'],'10.00');self.assertEqual(response.data['trend'][-1]['total'],'0.00')
        self.assertEqual(response.data['by_item'][0]['item_name'],'周期检查');self.assertEqual(response.data['by_item'][0]['total_amount'],'30.50');self.assertEqual(response.data['count'],3)
        admin=self.client.get('/api/v1/billing-records/examination-costs/',{'patient':self.other_patient.pk,'date_from':str(start),'date_to':str(end)})
        self.assertEqual(admin.status_code,403)  # 患者身份不能携带他人患者参数越权
        self.assertEqual(self.client.get('/api/v1/billing-records/examination-costs/',{'patient':self.patient.pk,'date_from':str(start),'date_to':str(end)}).status_code,200)
        self.auth(self.admin);self.assertEqual(self.client.get('/api/v1/billing-records/examination-costs/',{'date_from':str(start),'date_to':str(end)}).status_code,400)
        response=self.client.get('/api/v1/billing-records/examination-costs/',{'patient':self.patient.pk,'date_from':str(start),'date_to':str(end)})
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['summary']['total_amount'],'30.50')
        self.auth(self.doctor_user);self.assertEqual(self.client.get('/api/v1/billing-records/examination-costs/',{'patient':self.patient.pk}).status_code,403)
        self.auth(self.patient_user);self.assertEqual(self.client.get('/api/v1/billing-records/examination-costs/',{'date_from':str(end),'date_to':str(start)}).status_code,400)
        self.assertEqual(self.client.get('/api/v1/billing-records/examination-costs/',{'date_from':str(today-timedelta(days=400)),'date_to':str(today)}).status_code,400)
        self.auth(self.other_patient_user);self.assertEqual(self.client.get('/api/v1/billing-records/examination-costs/').data['summary']['total_amount'],'5.00')

    def test_medicine_costs_cover_prescriptions_manual_bills_and_historical_snapshots(self):
        today=timezone.localdate();record=self.confirmed_record();medicine_a=Medicine.objects.create(name='费用药A',specification='1mg',price='10.00',stock=20);medicine_b=Medicine.objects.create(name='费用药B',specification='2mg',price='20.00',stock=20)
        self.auth(self.doctor_user);response=self.client.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'费用统计','items':[{'medicine_id':medicine_a.pk,'dosage':'1mg','frequency':'每日一次','duration':'3天','quantity':1},{'medicine_id':medicine_b.pk,'dosage':'2mg','frequency':'每日两次','duration':'3天','quantity':2}]},format='json')
        self.assertEqual(response.status_code,201,response.data);prescription_bill=BillingRecord.objects.get(prescription_id=response.data['id'])
        start=today-timedelta(days=5);middle=today-timedelta(days=2)
        BillingRecord.objects.filter(pk=prescription_bill.pk).update(created_at=timezone.make_aware(datetime.combine(start,time(10))))
        historical=Prescription.objects.create(record=record,doctor=self.doctor,status=Prescription.Status.ISSUED)
        PrescriptionItem.objects.create(prescription=historical,medicine=medicine_a,dosage='1mg',frequency='每日一次',duration='2天',quantity=2,unit_price_snapshot=None)
        historical_bill=BillingRecord.objects.create(patient=self.patient,appointment=record.appointment,prescription=historical,category=BillingRecord.Category.MEDICINE,description='历史处方费用',amount=Decimal('15.00'),status=BillingRecord.Status.PAID,paid_at=timezone.now())
        BillingRecord.objects.filter(pk=historical_bill.pk).update(created_at=timezone.make_aware(datetime.combine(middle,time(10))))
        manual_bill=BillingRecord.objects.create(patient=self.patient,category=BillingRecord.Category.MEDICINE,description='手工药品费用：外购药',amount=Decimal('25.00'),status=BillingRecord.Status.UNPAID)
        BillingRecord.objects.filter(pk=manual_bill.pk).update(created_at=timezone.make_aware(datetime.combine(today,time(10))))
        cancelled_bill=BillingRecord.objects.create(patient=self.patient,category=BillingRecord.Category.MEDICINE,description='已取消药品费用',amount=Decimal('99.00'),status=BillingRecord.Status.CANCELLED)
        BillingRecord.objects.filter(pk=cancelled_bill.pk).update(created_at=timezone.make_aware(datetime.combine(today-timedelta(days=1),time(10))))
        outside=BillingRecord.objects.create(patient=self.patient,category=BillingRecord.Category.MEDICINE,description='区间外药品费用',amount=Decimal('77.00'),status=BillingRecord.Status.PAID)
        BillingRecord.objects.filter(pk=outside.pk).update(created_at=timezone.make_aware(datetime.combine(start-timedelta(days=2),time(10))))
        other=BillingRecord.objects.create(patient=self.other_patient,category=BillingRecord.Category.MEDICINE,description='其他患者药品费用',amount=Decimal('55.00'),status=BillingRecord.Status.PAID)
        BillingRecord.objects.filter(pk=other.pk).update(created_at=timezone.make_aware(datetime.combine(middle,time(11))))
        self.auth(self.patient_user);response=self.client.get('/api/v1/billing-records/medicine-costs/',{'date_from':str(start),'date_to':str(today),'page_size':2})
        self.assertEqual(response.status_code,200,response.data);summary=response.data['summary']
        self.assertEqual(summary['total_amount'],'90.00');self.assertEqual(summary['paid_amount'],'15.00');self.assertEqual(summary['unpaid_amount'],'75.00');self.assertEqual(summary['cancelled_amount'],'99.00');self.assertEqual(summary['bill_count'],3);self.assertEqual(summary['cancelled_count'],1)
        self.assertEqual(len(response.data['trend']),6);self.assertEqual(response.data['trend'][0]['total'],'50.00');self.assertEqual(response.data['trend'][3]['total'],'15.00');self.assertEqual(response.data['trend'][-1]['total'],'25.00')
        self.assertEqual(response.data['count'],4);self.assertEqual(len(response.data['results']),2);self.assertEqual(response.data['by_medicine'][0]['medicine_name'],'费用药B');self.assertEqual(response.data['by_medicine'][0]['total_amount'],'40.00');self.assertEqual(response.data['by_medicine'][0]['quantity'],2)
        labels={row['medicine_name']:row for row in response.data['by_medicine']};self.assertEqual(labels['费用药A']['total_amount'],'10.00');self.assertEqual(labels['手工药品费用']['total_amount'],'25.00');self.assertEqual(labels['历史处方明细']['total_amount'],'15.00')
        second=self.client.get('/api/v1/billing-records/medicine-costs/',{'date_from':str(start),'date_to':str(today),'page':2,'page_size':2});self.assertEqual(len(second.data['results']),2)
        all_rows=response.data['results']+second.data['results'];self.assertEqual(sum(Decimal(row['amount']) for row in all_rows if row['status']!=BillingRecord.Status.CANCELLED),Decimal('90.00'));self.assertEqual(sum(Decimal(row['amount']) for row in all_rows if row['status']==BillingRecord.Status.CANCELLED),Decimal('99.00'))
        prescription_row=next(row for row in response.data['results']+second.data['results'] if row['prescription_id']==prescription_bill.prescription_id)
        self.assertEqual(len(prescription_row['charge_details']),2);self.assertEqual({line['medicine_name'] for line in prescription_row['charge_details']},{'费用药A','费用药B'})
        historical_row=next(row for row in response.data['results']+second.data['results'] if row['prescription_id']==historical.pk)
        self.assertFalse(historical_row['charge_details'][0]['price_snapshot']);self.assertEqual(historical_row['charge_details'][0]['amount'],'15.00')
        manual_row=next(row for row in response.data['results']+second.data['results'] if row['id']==manual_bill.pk)
        self.assertEqual(manual_row['charge_details'],[]);self.assertIn('外购药',manual_row['description'])
        self.auth(self.other_patient_user);self.assertEqual(self.client.get('/api/v1/billing-records/medicine-costs/',{'patient':self.patient.pk}).status_code,403)
        self.auth(self.doctor_user);self.assertEqual(self.client.get('/api/v1/billing-records/medicine-costs/',{'patient':self.patient.pk}).status_code,403)
        self.auth(self.admin);self.assertEqual(self.client.get('/api/v1/billing-records/medicine-costs/').status_code,400)
        admin_response=self.client.get('/api/v1/billing-records/medicine-costs/',{'patient':self.patient.pk,'date_from':str(start),'date_to':str(today)});self.assertEqual(admin_response.status_code,200);self.assertEqual(admin_response.data['summary']['total_amount'],'90.00')
        self.auth(self.patient_user);self.assertEqual(self.client.get('/api/v1/billing-records/medicine-costs/',{'date_from':str(today),'date_to':str(start)}).status_code,400)
        self.assertEqual(self.client.get('/api/v1/billing-records/medicine-costs/',{'date_from':str(today-timedelta(days=400)),'date_to':str(today)}).status_code,400)

    def test_patient_clinical_history_is_paginated_authorized_and_audited(self):
        appointments=[]
        for index in range(12):
            day=date.today()-timedelta(days=index+1)
            appointment=self.make_appointment(self.patient,self.doctor,day,hour=8+(index%8),state=Appointment.Status.COMPLETED)
            record=MedicalRecord.objects.create(appointment=appointment,chief_complaint=f'主诉{index}',diagnosis='偏头痛' if index%2==0 else '高血压',treatment='对症治疗',status=MedicalRecord.Status.CONFIRMED,confirmed_at=timezone.now()-timedelta(days=index))
            if index==0:
                item=ExaminationItem.objects.create(name='历史检查',category='imaging',price='120.00')
                order=ExaminationOrder.objects.create(patient=self.patient,doctor=self.doctor,record=record,item=item,item_name_snapshot=item.name,price_snapshot=item.price,type='ct',status=ExaminationOrder.Status.PUBLISHED,clinical_question='历史检查',completed_at=timezone.now())
                ExaminationReport.objects.create(order=order,findings='未见异常',conclusion='历史结论',status=ExaminationReport.Status.PUBLISHED,published_by=self.admin,published_at=timezone.now())
                MedicalFile.objects.create(order=order,original_name='history.pdf',file_type='pdf',size=10,uploaded_by=self.admin,file=SimpleUploadedFile('history.pdf',b'%PDF-1.4 history'))
                ExaminationOrder.objects.create(patient=self.patient,doctor=self.doctor,record=record,item=item,item_name_snapshot='未发布检查',price_snapshot=item.price,type='ct',status=ExaminationOrder.Status.REQUESTED,clinical_question='未发布报告不应向患者展示')
            appointments.append(appointment)
        draft_appointment=self.make_appointment(self.other_patient,self.other_doctor,date.today(),hour=15,state=Appointment.Status.IN_PROGRESS)
        MedicalRecord.objects.create(appointment=draft_appointment,chief_complaint='草稿',diagnosis='草稿诊断',status=MedicalRecord.Status.DRAFT)
        self.auth(self.doctor_user);response=self.client.get(f'/api/v1/patients/{self.patient.pk}/clinical-history/',{'page_size':5})
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['count'],12);self.assertEqual(len(response.data['results']),5);self.assertEqual(response.data['permission_basis'],'doctor_relationship')
        self.assertTrue(all(row['status']==MedicalRecord.Status.CONFIRMED for row in response.data['results']))
        first=next(row for row in response.data['results'] if row['examinations']);published=next(exam for exam in first['examinations'] if exam['status']==ExaminationOrder.Status.PUBLISHED)
        self.assertEqual(published['report']['conclusion'],'历史结论');self.assertEqual(published['files'][0]['original_name'],'history.pdf');self.assertEqual(len(first['examinations']),2)
        second=self.client.get(f'/api/v1/patients/{self.patient.pk}/clinical-history/',{'page':2,'page_size':5})
        self.assertEqual(second.data['page'],2);self.assertEqual(len(second.data['results']),5)
        filtered=self.client.get(f'/api/v1/patients/{self.patient.pk}/clinical-history/',{'diagnosis':'高血压'})
        self.assertEqual(filtered.data['count'],6)
        department_filter=self.client.get(f'/api/v1/patients/{self.patient.pk}/clinical-history/',{'department':self.department.pk})
        self.assertEqual(department_filter.data['count'],12)
        self.assertTrue(AuditLog.objects.filter(action='read',resource='patient_clinical_history',object_id=str(self.patient.pk)).exists())
        self.auth(self.other_doctor_user);self.assertEqual(self.client.get(f'/api/v1/patients/{self.patient.pk}/clinical-history/').status_code,404)
        self.auth(self.patient_user);response=self.client.get(f'/api/v1/patients/{self.patient.pk}/clinical-history/');self.assertEqual(response.status_code,200);self.assertEqual(response.data['count'],12);self.assertEqual(response.data['permission_basis'],'self')
        patient_first=next(row for row in response.data['results'] if row['examinations'])
        self.assertEqual(len(patient_first['examinations']),1);self.assertEqual(patient_first['examinations'][0]['status'],ExaminationOrder.Status.PUBLISHED)
        patient_exams=self.client.get('/api/v1/examinations/');self.assertEqual(patient_exams.data['count'],1);self.assertEqual(patient_exams.data['results'][0]['status'],ExaminationOrder.Status.PUBLISHED)
        self.auth(self.other_patient_user);self.assertEqual(self.client.get(f'/api/v1/patients/{self.patient.pk}/clinical-history/').status_code,404)

    def test_doctor_record_list_exposes_only_authorized_confirmed_history(self):
        appointment=self.make_appointment(self.patient,self.doctor,date.today()-timedelta(days=1),state=Appointment.Status.COMPLETED)
        confirmed=MedicalRecord.objects.create(appointment=appointment,chief_complaint='头痛',diagnosis='偏头痛',status=MedicalRecord.Status.CONFIRMED,confirmed_at=timezone.now())
        other_appointment=self.make_appointment(self.other_patient,self.other_doctor,date.today()-timedelta(days=2),state=Appointment.Status.IN_PROGRESS)
        other_draft=MedicalRecord.objects.create(appointment=other_appointment,chief_complaint='草稿',diagnosis='其他诊断',status=MedicalRecord.Status.DRAFT)
        self.auth(self.doctor_user);response=self.client.get('/api/v1/medical-records/',{'patient':self.patient.pk})
        self.assertEqual([row['id'] for row in response.data['results']],[confirmed.pk]);self.assertEqual(self.client.get(f'/api/v1/medical-records/{other_draft.pk}/').status_code,404)
        self.auth(self.other_doctor_user);self.assertEqual(self.client.get('/api/v1/medical-records/',{'patient':self.patient.pk}).data['count'],0)

    def test_bed_board_room_view_and_admin_only_writes(self):
        first=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        second=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='02',daily_rate='120.00',is_active=False)
        third=WardBed.objects.create(department=self.department,ward_name='B 病区',bed_no='01',daily_rate='150.00')
        admission=self.admit_via_api(first)
        self.auth(self.doctor_user);response=self.client.get('/api/v1/ward-beds/board/')
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(len(response.data['rooms']),2)
        room=next(item for item in response.data['rooms'] if item['ward_name']=='A 病区')
        self.assertEqual(room['stats'],{'total':2,'available':0,'occupied':1,'inactive':1});self.assertEqual(len(room['beds']),2);self.assertEqual(room['department_ids'],[self.department.pk])
        self.assertEqual(response.data['total'],3);self.assertEqual(sum(item['stats']['total'] for item in response.data['rooms']),3)
        self.assertEqual(self.client.post('/api/v1/ward-beds/',{'department':self.department.pk,'ward_name':'C 病区','bed_no':'01','daily_rate':'100.00'},format='json').status_code,403)
        self.auth(self.patient_user);self.assertEqual(self.client.get('/api/v1/ward-beds/board/').status_code,403)
        self.auth(self.admin);created=self.client.post('/api/v1/ward-beds/',{'department':self.department.pk,'ward_name':'C 病区','bed_no':'01','daily_rate':'100.00'},format='json')
        self.assertEqual(created.status_code,201,created.data);self.assertFalse(created.data['is_occupied'])

    def test_archive_filters_reports_by_patient_type_and_report_state(self):
        record=self.confirmed_record()
        order=ExaminationOrder.objects.create(record=record,patient=self.patient,doctor=self.doctor,item_name_snapshot='颅脑 MRI',type=ExaminationOrder.Type.MRI,clinical_question='排除颅内病变')
        self.auth(self.doctor_user)
        response=self.client.get('/api/v1/examinations/',{'patient':self.patient.pk,'type':'mri','report_status':'none','ordering':'-report__published_at'})
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['count'],1,response.data)
        self.assertEqual(self.client.get('/api/v1/examinations/',{'patient':self.patient.pk,'type':'ct'}).data['count'],0)
        queue=self.client.get('/api/v1/statistics/dashboard/').data['examination_queue']
        self.assertTrue(any(item['patient_id']==self.patient.pk for item in queue),queue)
        response=self.client.post(f'/api/v1/examinations/{order.pk}/report/',{'findings':'未见明显异常','conclusion':'颅脑 MRI 未见明显异常'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        response=self.client.get('/api/v1/examinations/',{'patient':self.patient.pk,'report_status':'draft','ordering':'-report__published_at'})
        self.assertEqual(response.data['count'],1,response.data)
        self.assertEqual(self.client.post(f'/api/v1/examinations/{order.pk}/publish/').status_code,200)
        response=self.client.get('/api/v1/examinations/',{'patient':self.patient.pk,'report_status':'published','ordering':'-report__published_at'})
        self.assertEqual(response.data['count'],1,response.data)
        self.auth(self.patient_user)
        response=self.client.get('/api/v1/examinations/',{'patient':self.patient.pk,'report_status':'published'})
        self.assertEqual(response.data['count'],1,response.data);self.assertEqual(response.data['results'][0]['report']['conclusion'],'颅脑 MRI 未见明显异常')

class DemoFlowCommandTests(APITestCase):
    """演示验收脚本默认事务回滚：运行前后演示数据完全一致。"""

    def setUp(self):
        self.admin=User.objects.create_superuser('admin','admin@example.com','AdminPass123!',first_name='系统管理员')
        self.department=Department.objects.create(name='神经内科')
        self.doctor_user=User.objects.create_user('doctor',password='DoctorPass123!',first_name='张医师',role=User.Role.DOCTOR)
        self.doctor=DoctorProfile.objects.create(user=self.doctor_user,department=self.department)
        self.patient_user=User.objects.create_user('patient',password='PatientPass123!',first_name='测试患者',role=User.Role.PATIENT)
        self.patient=PatientProfile.objects.create(user=self.patient_user)
        self.bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='01',daily_rate='120.00')
        Medicine.objects.create(name='演示药品',specification='1mg',price='20.00',stock=50)
        ExaminationItem.objects.create(name='演示检查',category='lab',price='45.00')
        schedule=DoctorSchedule.objects.create(doctor=self.doctor,date=date.today(),start_time=time(8),end_time=time(9),slot_minutes=60)
        slot=AppointmentSlot.objects.create(schedule=schedule,start_time=time(8),end_time=time(9))
        appointment=Appointment.objects.create(patient=self.patient,doctor=self.doctor,slot=slot,status=Appointment.Status.COMPLETED,reason='演示就诊')
        self.record=MedicalRecord.objects.create(appointment=appointment,chief_complaint='演示主诉',diagnosis='演示诊断',status=MedicalRecord.Status.CONFIRMED,confirmed_at=timezone.now())
        self.occupied_bed=WardBed.objects.create(department=self.department,ward_name='A 病区',bed_no='02',daily_rate='120.00',is_occupied=True)
        admission=InpatientAdmission.objects.create(patient=self.patient,attending_doctor=self.doctor,department=self.department,appointment=appointment,bed=self.occupied_bed,ward='A 病区',bed_no='02',daily_rate_snapshot=Decimal('120.00'),admission_diagnosis='演示住院',status=InpatientAdmission.Status.ADMITTED,admitted_at=timezone.now()-timedelta(days=1))
        BillingRecord.objects.create(patient=self.patient,appointment=appointment,inpatient_admission=admission,category=BillingRecord.Category.OTHER,description='演示住院费用',amount='30.00')

    def snapshot(self):
        return {'admissions':InpatientAdmission.objects.count(),'occupied':WardBed.objects.filter(is_occupied=True).count(),
                'bills':BillingRecord.objects.count(),'prescriptions':Prescription.objects.count(),
                'examinations':ExaminationOrder.objects.count(),'records':MedicalRecord.objects.count(),
                'stock':list(Medicine.objects.values_list('name','stock'))}

    def run_command(self,suffix=''):
        from django.core.management import call_command
        output=io.StringIO()
        call_command('verify_demo_flow',admin_username='admin',admin_password='AdminPass123!',doctor_username='doctor',doctor_password='DoctorPass123!',patient_username='patient',patient_password='PatientPass123!',**({'keep_creates':True} if suffix else {}),stdout=output)
        return output.getvalue()

    def test_demo_flow_command_rolls_back_by_default(self):
        before=self.snapshot()
        output=self.run_command()
        self.assertIn('验收通过',output)
        self.assertIn('已回滚',output)
        self.assertEqual(before,self.snapshot())

    def test_demo_flow_command_can_keep_creates_for_manual_review(self):
        before=self.snapshot()
        output=self.run_command('keep')
        self.assertIn('已提交',output)
        after=self.snapshot()
        self.assertGreaterEqual(after['admissions'],before['admissions']+1)
        self.assertEqual(after['occupied'],before['occupied'])
        self.assertGreaterEqual(after['bills'],before['bills']+3)
        self.assertTrue(InpatientAdmission.objects.filter(status=InpatientAdmission.Status.DISCHARGED).exists())
