import random
import shutil
from datetime import datetime,time,timedelta
from decimal import Decimal
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from healthcare.models import *
from healthcare.services import generate_slots

class Command(BaseCommand):
    help='生成固定、可重复的智慧医疗答辩演示数据'
    def add_arguments(self,parser):parser.add_argument('--reset',action='store_true',help='清空新系统数据后重建')
    def handle(self,*args,**options):
        if options['reset']:
            call_command('flush',interactive=False,verbosity=0)
            media_root=settings.MEDIA_ROOT.resolve()
            if media_root.name=='smartmedical_media' and media_root.exists():shutil.rmtree(media_root)
            media_root.mkdir(parents=True,exist_ok=True)
        elif User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING('演示数据已存在；如需固定重建请使用 --reset。'));return
        with transaction.atomic():self.seed()

    def seed(self):
        rng=random.Random(20261011);today=timezone.localdate();now=timezone.now()
        admin=User.objects.create_superuser('admin','admin@demo.local','Admin123!',first_name='系统管理员',role=User.Role.ADMIN)
        department_specs=[('神经内科','脑血管疾病、头痛及神经系统疾病'),('心血管内科','高血压、冠心病及慢病管理'),('呼吸与危重症医学科','呼吸系统疾病与危重症诊疗'),('消化内科','消化系统疾病与随访'),('普通外科','常见外科疾病评估与术后管理'),('骨科','骨与关节疾病、创伤及康复'),('妇产科','妇科疾病与孕产期保健'),('儿科','儿童常见病与发育评估'),('医学影像科','CT、MRI 与 X-Ray 影像诊断'),('检验科','血液、生化与常规检验')]
        departments=[Department.objects.create(name=n,description=d) for n,d in department_specs]
        doctor_specs=[('doctor','张伟',0,'主任医师','神经系统慢病与综合诊疗'),('doctor2','李静',1,'副主任医师','高血压与冠心病'),('doctor3','王强',2,'主治医师','呼吸系统感染'),('doctor4','刘敏',3,'主治医师','消化道慢性疾病'),('doctor5','陈杰',4,'副主任医师','普通外科与围术期管理'),('doctor6','赵芳',5,'主治医师','骨关节疾病与康复')]
        doctors=[]
        for i,(username,name,dep,title,specialty) in enumerate(doctor_specs):
            user=User.objects.create_user(username,password='Doctor123!',first_name=name,phone=f'136000000{i:02d}',role=User.Role.DOCTOR)
            profile=DoctorProfile.objects.create(user=user,department=departments[dep],title=title,specialty=specialty,introduction='本资料仅用于系统演示。',is_super_doctor=i==0);profile.departments.set(departments if i==0 else [departments[dep]]);doctors.append(profile)
        patient_names=['张三','李四','王芳','赵磊','刘洋','陈静','杨勇','黄敏','周涛','吴丽','徐杰','孙娜'];patients=[]
        for i,name in enumerate(patient_names):
            username='patient' if i==0 else f'patient{i+1}';user=User.objects.create_user(username,password='Patient123!',first_name=name,phone=f'138000000{i:02d}',email=f'{username}@demo.local',role=User.Role.PATIENT)
            patients.append(PatientProfile.objects.create(user=user,gender=PatientProfile.Gender.MALE if i%2==0 else PatientProfile.Gender.FEMALE,birth_date=today-timedelta(days=(24+i*3)*365),address='演示市健康路 '+str(i+1)+' 号',blood_group=['A','B','O','AB'][i%4],allergies='青霉素过敏' if i==0 else '无已知过敏',medical_history='偏头痛史 3 年（虚构演示资料）' if i==0 else '无特殊'))
        schedules=[]
        for offset in range(-90,15):
            for doctor in doctors:
                schedule=DoctorSchedule.objects.create(doctor=doctor,date=today+timedelta(days=offset),start_time=time(8),end_time=time(12),slot_minutes=30,is_active=offset>=0)
                generate_slots(schedule);schedules.append(schedule)
        all_slots=list(AppointmentSlot.objects.select_related('schedule').order_by('schedule__date','schedule__doctor_id','start_time'))
        past=[s for s in all_slots if s.schedule.date<today];current=[s for s in all_slots if s.schedule.date==today];future=[s for s in all_slots if s.schedule.date>today]
        past_chosen=[past[int(i*(len(past)-1)/75)] for i in range(76)]
        future_chosen=[future[int(i*(len(future)-1)/15)] for i in range(16)]
        chosen=past_chosen[:62]+current[:4]+future_chosen+past_chosen[62:];appointments=[]
        status_cycle=[Appointment.Status.COMPLETED]*62+[Appointment.Status.IN_PROGRESS]*4+[Appointment.Status.PENDING]*16+[Appointment.Status.CANCELLED]*8+[Appointment.Status.NO_SHOW]*6
        reasons=['反复头痛','胸闷心悸','咳嗽发热','腹痛腹胀','术后复查','膝关节疼痛']
        for i,(slot,state) in enumerate(zip(chosen,status_cycle)):
            patient=patients[0] if i<18 else patients[i%len(patients)];appointment=Appointment.objects.create(patient=patient,doctor=slot.schedule.doctor,slot=slot,status=state,reason=reasons[i%len(reasons)])
            if state!=Appointment.Status.CANCELLED:slot.status=AppointmentSlot.Status.BOOKED;slot.save(update_fields=['status','updated_at'])
            if state==Appointment.Status.CANCELLED:appointment.cancelled_at=now-timedelta(days=max(0,-(slot.schedule.date-today).days));appointment.save(update_fields=['cancelled_at'])
            if state==Appointment.Status.COMPLETED:appointment.completed_at=timezone.make_aware(datetime.combine(slot.schedule.date,slot.end_time));appointment.save(update_fields=['completed_at'])
            appointments.append(appointment)
        records=[]
        for i,appointment in enumerate(appointments[:66]):
            confirmed=i<62;record=MedicalRecord.objects.create(appointment=appointment,chief_complaint=reasons[i%6],present_illness='症状持续数日，无明显诱因。',past_history=appointment.patient.medical_history,examination='生命体征平稳，一般情况良好。',diagnosis=['偏头痛','原发性高血压','上呼吸道感染','慢性胃炎','术后恢复期','膝骨关节炎'][i%6],treatment='对症治疗，规律作息，不适随诊。',status=MedicalRecord.Status.CONFIRMED if confirmed else MedicalRecord.Status.DRAFT,confirmed_at=now-timedelta(days=i%30) if confirmed else None);records.append(record)
        medicine_specs=[('布洛芬缓释胶囊','0.3g×20粒','18.50',120),('对乙酰氨基酚片','0.5g×12片','9.80',8),('阿莫西林胶囊','0.25g×24粒','19.50',80),('奥美拉唑肠溶胶囊','20mg×14粒','28.00',60),('苯磺酸氨氯地平片','5mg×28片','32.60',6),('缬沙坦胶囊','80mg×7粒','25.40',45),('阿司匹林肠溶片','100mg×30片','16.80',90),('瑞舒伐他汀钙片','10mg×7片','38.00',35),('盐酸二甲双胍片','0.5g×20片','12.50',70),('磷酸奥司他韦胶囊','75mg×10粒','168.00',4),('蓝芩口服液','10ml×6支','24.00',55),('蒙脱石散','3g×10袋','15.20',40),('双氯芬酸钠凝胶','20g','22.00',30),('钙尔奇D片','30片','42.00',25),('甲钴胺片','0.5mg×20片','18.00',3),('氯雷他定片','10mg×6片','8.50',50),('葡萄糖氯化钠注射液','500ml','6.80',100),('停用演示药品','10mg×10片','10.00',20)]
        medicines=[]
        for i,(name,spec,price,stock) in enumerate(medicine_specs):
            med=Medicine.objects.create(name=name,specification=spec,price=price,stock=stock,is_active=i!=17);med.stock_movements.create(movement_type=MedicineStockMovement.Type.RECEIPT,quantity=stock,balance_after=stock,operator=admin,note='演示数据初始入库');medicines.append(med)
        exam_specs=[('血常规','lab','35'),('肝肾功能','lab','128'),('心脏彩超','function','220'),('心电图','function','45'),('胸部 X-Ray','imaging','88'),('头颅 CT 平扫','imaging','360'),('头颅 MRI 平扫','imaging','720'),('腹部彩超','function','180')]
        exam_items=[ExaminationItem.objects.create(name=n,category=c,price=p,description='虚构演示检查项目') for n,c,p in exam_specs]
        beds=[]
        for dep in departments[:6]:
            for number in range(1,5):beds.append(WardBed.objects.create(department=dep,ward_name=f'{dep.name}一病区',bed_no=f'{number:02d}',daily_rate=Decimal('120.00')+number*10))
        prescriptions=[]
        for i in range(38):
            record=records[i%62];state=Prescription.Status.DISPENSED if i<27 else Prescription.Status.ISSUED if i<34 else Prescription.Status.CANCELLED;rx=Prescription.objects.create(record=record,doctor=record.appointment.doctor,status=state,notes='饭后服用，遵医嘱。',dispensed_at=now-timedelta(days=i%25) if state==Prescription.Status.DISPENSED else None)
            med=medicines[i%16];PrescriptionItem.objects.create(prescription=rx,medicine=med,dosage='每次 1 片',frequency='每日两次',duration='3 天',quantity=1)
            if state==Prescription.Status.DISPENSED:
                med.stock-=1;med.save(update_fields=['stock','updated_at']);med.stock_movements.create(movement_type=MedicineStockMovement.Type.DISPENSE,quantity=-1,balance_after=med.stock,prescription=rx,operator=admin,note='演示处方发药')
            bill=BillingRecord.objects.create(patient=record.appointment.patient,appointment=record.appointment,prescription=rx,category=BillingRecord.Category.MEDICINE,description=f'处方 {rx.prescription_no}：{med.name}',amount=med.price,status=BillingRecord.Status.PAID if state==Prescription.Status.DISPENSED else BillingRecord.Status.CANCELLED if state==Prescription.Status.CANCELLED else BillingRecord.Status.UNPAID,payment_method='演示支付' if state==Prescription.Status.DISPENSED else '',paid_at=now-timedelta(days=i%25) if state==Prescription.Status.DISPENSED else None);prescriptions.append(rx)
        examinations=[]
        exam_states=[ExaminationOrder.Status.PUBLISHED]*18+[ExaminationOrder.Status.COMPLETED]*5+[ExaminationOrder.Status.IN_PROGRESS]*5+[ExaminationOrder.Status.REQUESTED]*4
        type_map={'lab':'lab','function':'other','imaging':'ct'}
        for i,state in enumerate(exam_states):
            record=records[i%62];item=exam_items[i%len(exam_items)];order=ExaminationOrder.objects.create(patient=record.appointment.patient,doctor=record.appointment.doctor,record=record,item=item,item_name_snapshot=item.name,price_snapshot=item.price,type=type_map[item.category],status=state,clinical_question='辅助明确诊断（虚构演示）',completed_at=now-timedelta(days=i%20) if state in {ExaminationOrder.Status.PUBLISHED,ExaminationOrder.Status.COMPLETED} else None)
            BillingRecord.objects.create(patient=order.patient,appointment=record.appointment,examination=order,category=BillingRecord.Category.EXAMINATION,description=f'检查 {order.order_no}：{item.name}',amount=item.price,status=BillingRecord.Status.PAID if i<20 else BillingRecord.Status.UNPAID,payment_method='演示支付' if i<20 else '',paid_at=now-timedelta(days=i%20) if i<20 else None)
            if state in {ExaminationOrder.Status.PUBLISHED,ExaminationOrder.Status.COMPLETED}:ExaminationReport.objects.create(order=order,findings='未见明显异常，该结果为虚构演示资料。',conclusion='建议结合临床随诊。',status=ExaminationReport.Status.PUBLISHED if state==ExaminationOrder.Status.PUBLISHED else ExaminationReport.Status.DRAFT,published_by=admin if state==ExaminationOrder.Status.PUBLISHED else None,published_at=now-timedelta(days=i%20) if state==ExaminationOrder.Status.PUBLISHED else None)
            examinations.append(order)
        attachments=[('demo-report-1.pdf',b'%PDF-1.4\n% Fictional demo medical report\n%%EOF','pdf'),('demo-image-1.png',b'\x89PNG\r\n\x1a\nDEMO-FICTIONAL','png'),('demo-image-2.png',b'\x89PNG\r\n\x1a\nDEMO-FICTIONAL','png')]
        for order,(name,content,kind) in zip(examinations[:3],attachments):
            file=MedicalFile(order=order,original_name='虚构演示资料-'+name,file_type=kind,size=len(content),uploaded_by=admin);file.file.save(name,ContentFile(content),save=True)
        for i in range(8):
            record=records[i];bed=beds[i];admitted=now-timedelta(days=2+i);state=InpatientAdmission.Status.ADMITTED if i<4 else InpatientAdmission.Status.DISCHARGED;admission=InpatientAdmission.objects.create(patient=record.appointment.patient,attending_doctor=record.appointment.doctor,department=bed.department,appointment=record.appointment,bed=bed,ward=bed.ward_name,bed_no=bed.bed_no,daily_rate_snapshot=bed.daily_rate,admission_diagnosis=record.diagnosis,status=state,admitted_at=admitted,discharged_at=now-timedelta(days=i-3) if state==InpatientAdmission.Status.DISCHARGED else None,discharge_summary='病情好转，遵医嘱出院。' if state==InpatientAdmission.Status.DISCHARGED else '')
            if state==InpatientAdmission.Status.ADMITTED:bed.is_occupied=True;bed.save(update_fields=['is_occupied','updated_at'])
            else:BillingRecord.objects.create(patient=admission.patient,appointment=admission.appointment,admission=admission,category=BillingRecord.Category.INPATIENT,description=f'{bed} 住院费',amount=bed.daily_rate*(i-1),status=BillingRecord.Status.PAID if i<6 else BillingRecord.Status.UNPAID,payment_method='演示支付' if i<6 else '',paid_at=now-timedelta(days=i-3) if i<6 else None)
        for i in range(4):BillingRecord.objects.create(patient=patients[i],appointment=appointments[i],category=BillingRecord.Category.REGISTRATION,description='普通门诊挂号费',amount='20.00',status=BillingRecord.Status.PAID,payment_method='演示支付',paid_at=now-timedelta(days=i))
        actions=['login','read','create','update','confirm','pay','publish','admit']
        for i in range(40):AuditLog.objects.create(user=[admin,doctors[0].user,patients[0].user][i%3],action=actions[i%len(actions)],resource=['auth','patient','medical_record','billing','examination','inpatient'][i%6],object_id=str(i+1),description=f'演示操作记录 {i+1}')
        AIService.objects.create(name='医学影像智能分析',service_type='medical_imaging_analysis',description='仅保留接口，未配置真实模型。',is_enabled=False)
        self.stdout.write(self.style.SUCCESS(f'演示数据已重建：10 科室 / 6 医师 / 12 患者 / {len(appointments)} 预约 / {len(records)} 病历 / {len(prescriptions)} 处方 / {len(examinations)} 检查。'))
