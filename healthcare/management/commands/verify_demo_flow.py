"""三类演示账号端到端验收：床位看板（卡片/分组/统计）→ 住院详情与费用清单 → 出院结算。

默认在单个事务中执行全部写入，结束后回滚，因此运行前后的演示数据完全一致；
只有显式传入 --keep-creates 时才会保留验收过程中创建的数据。
"""

from datetime import time,timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient
from django.db.models import Sum
from healthcare.models import (Appointment,BillingRecord,DoctorProfile,ExaminationItem,ExaminationOrder,
                               InpatientAdmission,MedicalRecord,Medicine,PatientProfile,User,WardBed)

class Command(BaseCommand):
    help='使用管理员、医师、患者三类演示账号走通床位看板与住院费用清单验收流程（默认事务回滚，演示数据不变）。'

    def add_arguments(self,parser):
        parser.add_argument('--keep-creates',action='store_true',help='保留验收过程中创建的数据（默认事务回滚）。')
        parser.add_argument('--admin-username',default='admin');parser.add_argument('--admin-password',default='Admin123!')
        parser.add_argument('--doctor-username',default='doctor');parser.add_argument('--doctor-password',default='Doctor123!')
        parser.add_argument('--patient-username',default='patient');parser.add_argument('--patient-password',default='Patient123!')

    def handle(self,*args,**options):
        self.prepare_connection()
        self.checks=[]
        self.clients={}
        accounts=(('admin',options['admin_username'],options['admin_password'],'管理员'),
                  ('doctor',options['doctor_username'],options['doctor_password'],'医师'),
                  ('patient',options['patient_username'],options['patient_password'],'患者'))
        for key,username,password,label in accounts:
            if not User.objects.filter(username=username).exists():
                raise CommandError(f'缺少{label}账号 {username}，请先执行 python manage.py seed_smartmedical --reset')
            client,user=self.login(username,password,label)
            self.clients[key]=(client,user)
        self.verify_bed_board(readonly=True)
        self.verify_upgrade_modules(readonly=True)
        self.verify_roles(readonly=True)
        before=self.snapshot()
        self.stdout.write('住院业务链路（单事务执行，默认回滚）')
        self.created={}
        with transaction.atomic():
            self.verify_admission_flow()
            self.verify_bed_board()
            self.verify_upgrade_modules()
            self.verify_roles()
            if options['keep_creates']:
                kept='（已提交新建数据）'
            else:
                transaction.set_rollback(True);kept='（已回滚，演示数据不变）'
        if not options['keep_creates']:
            after=self.snapshot()
            if after!=before:raise CommandError(f'回滚校验失败：验收前后数据不一致 {before} → {after}')
        self.stdout.write(self.style.SUCCESS(f'验收通过 {len(self.checks)} 项（含回滚前后两次看板/权限校验） {kept}'))

    def prepare_connection(self):
        """SQLite 在大事务中需要临时存储；放到内存可避免长事务写入时报找不到数据库文件。"""
        from django.db import OperationalError,connection
        if connection.vendor!='sqlite' or not connection.get_autocommit():return
        try:
            with connection.cursor() as cursor:cursor.execute('PRAGMA temp_store=MEMORY')
        except OperationalError:pass

    def snapshot(self):
        return {'admissions':InpatientAdmission.objects.count(),'occupied_beds':WardBed.objects.filter(is_occupied=True).count(),
                'bills':BillingRecord.objects.count(),'prescriptions':BillingRecord.objects.filter(prescription__isnull=False).count()}

    def client(self,key):return self.clients[key][0]
    def session_user(self,key):return self.clients[key][1]

    def verify(self,label,condition,detail=''):
        self.checks.append((label,bool(condition)))
        self.stdout.write(('  [通过] ' if condition else '  [失败] ')+label+(f' —— {detail}' if detail else ''))
        if not condition:raise CommandError(f'验收失败：{label}')

    def login(self,username,password,label):
        client=APIClient()
        response=client.post('/api/v1/auth/login/',{'username':username,'password':password},format='json')
        if response.status_code!=200:raise CommandError(f'{label}账号 {username} 登录失败：{response.status_code} {response.data}')
        user=response.data['user'];client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.verify(f'{label}账号登录',user['role']==('admin' if label=='管理员' else 'doctor' if label=='医师' else 'patient'),f"{user['full_name']} · {user['role']}")
        return client,user

    def verify_bed_board(self,readonly=False):
        self.stdout.write('管理员：床位卡片看板与住院费用清单' if readonly else '再次校验：入院后看板卡片与住院清单')
        client=self.client('admin')
        board=client.get('/api/v1/ward-beds/board/')
        self.verify('看板接口返回全部床位',board.status_code==200 and board.data['total']==WardBed.objects.count(),f"{board.data['total']} 张（分页列表仅 {client.get('/api/v1/ward-beds/').data['count']} 条）")
        data=board.data
        self.verify('每张床恰好一张卡片',len(data['beds'])==data['total'] and sum(len(group['beds']) for group in data['groups'])==data['total'])
        self.verify('统计与实际卡片数量一致',sum(data['stats'][key] for key in ('available','occupied','inactive'))==data['total']==sum(group['stats']['total'] for group in data['groups']),str(data['stats']))
        self.verify('按科室与病区分组',len(data['groups'])>0 and all(group['ward_name'] and group['department_name'] for group in data['groups']),f"{len(data['groups'])} 个病区")
        self.verify('状态同时有颜色键与文字标签',{bed['status'] for bed in data['beds']}<= {'available','occupied','inactive'} and all(bed['status_label'] for bed in data['beds']))
        self.verify('空床卡片展示位置与日费',all(bed['department_name'] and bed['ward_name'] and bed['bed_no'] and Decimal(bed['daily_rate'])>=0 for bed in data['beds'] if bed['status']=='available'))
        cards=[bed for bed in data['beds'] if bed['status']=='occupied' and bed['occupancy']]
        if not cards:
            self.stdout.write('  [跳过] 当前演示数据没有可下钻的住院卡片，先执行入院链路')
            return
        complete=all(bed['occupancy']['patient_name'] and bed['occupancy']['patient_no'] and bed['occupancy']['admission_no'] and bed['occupancy']['doctor_name'] and bed['occupancy']['admitted_at'] and bed['occupancy']['days_admitted']>=1 for bed in cards)
        self.verify('住院卡片展示患者与住院信息',bool(complete),f"{len(cards)} 张住院床")
        dangling=[bed for bed in data['beds'] if bed['status']=='occupied' and not bed['occupancy']]
        if dangling:self.verify('缺少住院记录的占用床位标记为数据异常',all(bed['data_warning'] and bed['status_label']=='住院中' for bed in dangling),f"{len(dangling)} 张")
        first=cards[0]
        detail=client.get(f"/api/v1/ward-beds/{first['id']}/occupancy/")
        self.verify('卡片可打开床位详情抽屉',detail.status_code==200 and detail.data['occupied'] and detail.data['admission']['admission_no']==first['occupancy']['admission_no'])
        self.charged_admission_id=InpatientAdmission.objects.get(admission_no=first['occupancy']['admission_no']).pk
        found=None
        for card in cards:
            candidate=InpatientAdmission.objects.get(admission_no=card['occupancy']['admission_no'])
            charges=client.get(f'/api/v1/inpatients/{candidate.pk}/charges/')
            lines=sum(len(row['charge_details']) for row in charges.data['items'])
            if lines:
                found=(candidate,charges,lines)
                if not readonly:break
        if found is None:
            self.stdout.write('  [跳过] 当前演示数据没有带处方明细的住院清单，先执行开药链路')
            return
        admission,charges,detail_lines=found
        self.charged_admission_id=admission.pk;summary=charges.data['summary']
        self.verify('住院清单返回真实费用明细行',charges.status_code==200 and detail_lines>=1,f"{detail_lines} 条明细行 / {summary['bill_count']} 张有效账单")
        self.verify('明细总额与有效账单总额一致',all(Decimal(row['details_total'])==Decimal(row['amount']) for row in charges.data['items'] if row['charge_details']),f"合计 {summary['billed_amount']}")
        self.verify('费用清单展示合计/已付/待付',all(key in summary for key in ('billed_amount','paid_amount','unpaid_amount')),f"合计 {summary['billed_amount']}，待付 {summary['unpaid_amount']}")
        self.verify('费用发生日期为创建日期',all(row['charge_date'] and row['charge_date']==row['created_at'][:10] for row in charges.data['items']))
        self.verify('取消的账单不计入合计',all(row['status']!='cancelled' for row in charges.data['items']),f"清单内无已取消账单，合计 {summary['billed_amount']}")
        bed_listing=client.get('/api/v1/inpatients/')
        row=bed_listing.data['results'][0]
        self.verify('住院列表标注已出账/待付/预计床位费',all(key in row['charge_summary'] for key in ('billed_amount','unpaid_amount','projected_bed_fee')),str(row['charge_summary']))

    def verify_upgrade_modules(self,readonly=False):
        self.stdout.write('升级模块：账户分栏、科室概览、门诊视图、检查费用、纵向病历、房间看板')
        admin,doctor,patient=self.client('admin'),self.client('doctor'),self.client('patient')
        doctors=admin.get('/api/v1/users/',{'role':'doctor','page_size':5});patients=admin.get('/api/v1/users/',{'role':'patient','page_size':5})
        self.verify('账户按医师/患者分栏查询',doctors.status_code==200 and patients.status_code==200 and all(row['role']=='doctor' for row in doctors.data['results']) and all(row['role']=='patient' for row in patients.data['results']),f"医师 {doctors.data['count']} / 患者 {patients.data['count']}")
        self.verify('账户列表返回对应档案编号',all(row.get('doctor_no') for row in doctors.data['results']) and all(row.get('patient_no') for row in patients.data['results']))
        overview=admin.get('/api/v1/departments/overview/')
        self.verify('科室概览返回逐科统计',overview.status_code==200 and len(overview.data['results'])>0 and all('stats' in row for row in overview.data['results']))
        target=next((row for row in overview.data['results'] if row['stats']['total']>0),overview.data['results'][0])
        visits=admin.get(f"/api/v1/departments/{target['id']}/visits/")
        self.verify('科室卡片数字与当日明细一致',visits.status_code==200 and visits.data['count']==target['stats']['total'],f"{target['name']} {visits.data['count']} 条")
        self.verify('患者不能读取科室患者清单',patient.get('/api/v1/departments/overview/').status_code==403 and patient.get(f"/api/v1/departments/{target['id']}/visits/").status_code==403)
        outpatient=admin.get('/api/v1/schedules/outpatient/')
        groups=outpatient.data.get('results',[]) if outpatient.status_code==200 else []
        self.verify('门诊视图按医师→排班→号源→患者展示',outpatient.status_code==200 and all({'doctor','schedules'}<=set(group) for group in groups) and any(slot.get('appointment') for group in groups for schedule in group['schedules'] for slot in schedule['slots']))
        doctor_user=User.objects.get(username=self.clients['doctor'][1]['username'])
        doctor_view=doctor.get('/api/v1/schedules/outpatient/')
        self.verify('医师门诊视图仅本人排班',doctor_view.status_code==200 and all(group['doctor']['id']==doctor_user.doctor_profile.pk for group in doctor_view.data['results']),f"{len(doctor_view.data['results'])} 位医师")
        self.verify('患者不能访问门诊就诊视图',patient.get('/api/v1/schedules/outpatient/').status_code==403)
        today=timezone.localdate();start=today-timedelta(days=90)
        patient_user=User.objects.get(username=self.clients['patient'][1]['username']);profile=patient_user.patient_profile
        costs=patient.get('/api/v1/billing-records/examination-costs/',{'date_from':str(start),'date_to':str(today)})
        expected=BillingRecord.objects.filter(patient=profile,category=BillingRecord.Category.EXAMINATION,examination__isnull=False,created_at__date__range=(start,today)).exclude(status__in=[BillingRecord.Status.CANCELLED,BillingRecord.Status.REFUNDED]).aggregate(value=Sum('amount'))['value'] or Decimal('0')
        self.verify('检查费用周期统计与账单一致',costs.status_code==200 and Decimal(costs.data['summary']['total_amount'])==expected and len(costs.data['trend'])==91,f"合计 {costs.data.get('summary',{}).get('total_amount')} / 趋势 {len(costs.data.get('trend',[]))} 天")
        if costs.data['by_item']:
            self.verify('检查费用返回项目汇总与分页明细',all('item_name' in row and 'total_amount' in row for row in costs.data['by_item']) and 'results' in costs.data and 'count' in costs.data)
        else:self.stdout.write('  [跳过] 当前演示数据在该周期内没有检查费用账单')
        other_patient=PatientProfile.objects.exclude(pk=profile.pk).first()
        if other_patient is not None:self.verify('患者不能越权查询他人检查费用',patient.get('/api/v1/billing-records/examination-costs/',{'patient':other_patient.pk}).status_code==403)
        self.verify('医师不使用患者检查费用页面',doctor.get('/api/v1/billing-records/examination-costs/',{'patient':profile.pk}).status_code==403)
        history=patient.get(f'/api/v1/patients/{profile.pk}/clinical-history/',{'page_size':5})
        confirmed=MedicalRecord.objects.filter(appointment__patient=profile,status=MedicalRecord.Status.CONFIRMED).count()
        self.verify('患者纵向病历分页返回全部已确认病历',history.status_code==200 and history.data['count']==confirmed and len(history.data['results'])<=5,f"{history.data.get('count')} 份")
        valid_states=[Appointment.Status.PENDING,Appointment.Status.IN_PROGRESS,Appointment.Status.COMPLETED]
        related=PatientProfile.objects.filter(appointments__doctor__user=doctor_user,appointments__status__in=valid_states,appointments__medical_record__status=MedicalRecord.Status.CONFIRMED).distinct().first()
        if related is not None:
            doctor_history=doctor.get(f'/api/v1/patients/{related.pk}/clinical-history/')
            self.verify('医师可查阅关联患者已确认病历',doctor_history.status_code==200 and doctor_history.data['count']>0 and all(row['status']=='confirmed' for row in doctor_history.data['results']),f"{doctor_history.data.get('count')} 份")
        unrelated=PatientProfile.objects.exclude(appointments__doctor__user=doctor_user,appointments__status__in=valid_states).first()
        if unrelated is not None:
            self.verify('无诊疗关系医师不能读取纵向病历',doctor.get(f'/api/v1/patients/{unrelated.pk}/clinical-history/').status_code==404)
        if other_patient is not None:self.verify('患者不能读取他人纵向病历',patient.get(f'/api/v1/patients/{other_patient.pk}/clinical-history/').status_code==404)
        board=admin.get('/api/v1/ward-beds/board/')
        rooms=board.data.get('rooms',[])
        self.verify('床位看板提供房间优先分组',board.status_code==200 and len(rooms)>0 and sum(room['stats']['total'] for room in rooms)==board.data['total'],f"{len(rooms)} 个房间")
        self.verify('每个房间床位与占用统计一致',all(room['stats']['total']==len(room['beds']) and room['stats']['total']==room['stats']['available']+room['stats']['occupied']+room['stats']['inactive'] for room in rooms))

    def verify_roles(self,readonly=False):
        self.stdout.write('权限：医师可读全院看板，患者仅可读本人数据')
        admin=self.client('admin')
        board=admin.get('/api/v1/ward-beds/board/').data
        occupied=next((bed for bed in board['beds'] if bed['status']=='occupied'),board['beds'][0])
        doctor_board=self.client('doctor').get('/api/v1/ward-beds/board/')
        self.verify('医师可查看全院床位看板',doctor_board.status_code==200 and doctor_board.data['total']==WardBed.objects.count())
        if getattr(self,'charged_admission_id',None):self.verify('医师可读住院费用清单',self.client('doctor').get(f'/api/v1/inpatients/{self.charged_admission_id}/charges/').status_code==200)
        doctor_user=User.objects.get(username=self.clients['doctor'][1]['username'])
        related_patients=PatientProfile.objects.filter(appointments__doctor__user=doctor_user,appointments__status__in=[Appointment.Status.PENDING,Appointment.Status.IN_PROGRESS,Appointment.Status.COMPLETED]).distinct().count()
        self.verify('医师只读取有预约关系的患者',self.client('doctor').get('/api/v1/patients/').data['count']==related_patients,f'{related_patients} 位关联患者')
        patient=self.client('patient')
        self.verify('患者不能获取全院看板数据',patient.get('/api/v1/ward-beds/board/').status_code==403 and patient.get('/api/v1/ward-beds/').status_code==403 and patient.get(f"/api/v1/ward-beds/{occupied['id']}/occupancy/").status_code==403)
        mine=patient.get('/api/v1/inpatients/')
        self.verify('患者只看到本人住院记录',mine.status_code==200 and all(row['patient_name']==self.session_user('patient')['full_name'] for row in mine.data['results']),f"{mine.data['count']} 条")
        own=next((row for row in mine.data['results'] if row.get('charge_summary')),None)
        self.verify('患者可查看本人住院记录与费用',own is not None and patient.get(f"/api/v1/inpatients/{own['id']}/charges/").status_code==200,f"{mine.data['count']} 条本人住院记录")
        other=InpatientAdmission.objects.exclude(patient__user__username=self.clients['patient'][1]['username']).first()
        if other is not None:self.verify('患者不能查看他人住院与费用',patient.get(f'/api/v1/inpatients/{other.pk}/charges/').status_code==404)
        bills=patient.get('/api/v1/billing-records/')
        self.verify('患者只读取本人账单',bills.status_code==200 and all(row['patient_name']==self.session_user('patient')['full_name'] for row in bills.data['results']))

    def spare_patient(self):
        """演示库只有一个患者时，临时构造第二患者用于重复占用与患者一致性校验。"""
        index=1
        while User.objects.filter(username=f'verify-spare-{index}').exists():index+=1
        user=User.objects.create_user(f'verify-spare-{index}',password='VerifySpare123!',first_name=f'验收备用患者{index}',role=User.Role.PATIENT)
        patient=PatientProfile.objects.create(user=user)
        self.created['spare_patient']=patient.pk
        return patient

    def confirmed_record(self,patient,doctor):
        """住院期间开药与检查仍需一张已确认病历，这里直接构造最小可用的就诊记录。"""
        from healthcare.models import Appointment,AppointmentSlot,DoctorSchedule
        hour=next(candidate for candidate in range(6,22) if not DoctorSchedule.objects.filter(doctor=doctor,date=timezone.localdate(),start_time=time(candidate)).exists())
        schedule=DoctorSchedule.objects.create(doctor=doctor,date=timezone.localdate(),start_time=time(hour),end_time=time(hour+1),slot_minutes=60)
        slot=AppointmentSlot.objects.create(schedule=schedule,start_time=time(hour),end_time=time(hour+1))
        appointment=Appointment.objects.create(patient=patient,doctor=doctor,slot=slot,status=Appointment.Status.IN_PROGRESS,reason='验收演示：住院期间诊疗')
        record=MedicalRecord.objects.create(appointment=appointment,chief_complaint='验收演示',diagnosis='偏头痛',status=MedicalRecord.Status.CONFIRMED,confirmed_at=timezone.now())
        self.created.update({'schedule':schedule.pk,'slot':slot.pk,'appointment':appointment.pk,'record':record.pk})
        return record

    def verify_admission_flow(self):
        admin,doctor,patient=self.client('admin'),self.client('doctor'),self.client('patient')
        free_bed=WardBed.objects.filter(is_occupied=False,is_active=True).select_related('department').order_by('department__name','ward_name','bed_no').first()
        if free_bed is None:raise CommandError('没有可用空床，无法执行入院验收流程。')
        department=free_bed.department
        target=PatientProfile.objects.filter(user__username=self.clients['patient'][1]['username']).first() or PatientProfile.objects.first()
        other=PatientProfile.objects.exclude(pk=target.pk).first() or self.spare_patient()
        attending=DoctorProfile.objects.get(user__username=self.clients['doctor'][1]['username'])
        medicine=Medicine.objects.filter(is_active=True,stock__gt=0).first()
        exam_item=ExaminationItem.objects.filter(is_active=True).first()
        created=admin.post('/api/v1/inpatients/',{'patient_id':target.pk,'doctor_id':attending.pk,'department_id':department.pk,'bed_id':free_bed.pk,'admission_diagnosis':'验收演示：偏头痛待查'},format='json')
        self.verify('创建住院申请',created.status_code==201,str(created.data.get('admission_no')))
        admission_id=created.data['id'];self.created['admission']=admission_id
        self.verify('办理入院',admin.post(f'/api/v1/inpatients/{admission_id}/admit/').status_code==200)
        free_bed.refresh_from_db();self.verify('床位被标记为占用',free_bed.is_occupied)
        second=admin.post('/api/v1/inpatients/',{'patient_id':other.pk,'doctor_id':attending.pk,'department_id':department.pk,'bed_id':free_bed.pk,'admission_diagnosis':'重复占用校验'},format='json')
        self.created['duplicate']=second.data['id']
        self.verify('同一床位重复占用被拒绝',admin.post(f"/api/v1/inpatients/{second.data['id']}/admit/").status_code==400)
        self.verify('占用中的床位不可改病区/床号或停用',admin.patch(f'/api/v1/ward-beds/{free_bed.pk}/',{'ward_name':'占用中不可改病区'},format='json').status_code==400)
        board=admin.get('/api/v1/ward-beds/board/',{'occupancy':'occupied'})
        card=next(bed for bed in board.data['beds'] if bed['id']==free_bed.pk)
        self.verify('占用后看板卡片切换为住院状态',card['status']=='occupied' and card['occupancy']['admission_no']==created.data['admission_no'])
        admission=InpatientAdmission.objects.get(pk=admission_id)
        InpatientAdmission.objects.filter(pk=admission.pk).update(admitted_at=timezone.now()-timedelta(days=1))
        admission.refresh_from_db()
        record=self.confirmed_record(target,attending)
        first_medicine=Medicine.objects.filter(is_active=True,stock__gt=3).exclude(pk=medicine.pk).first() or medicine
        prescription=doctor.post('/api/v1/prescriptions/',{'record_id':record.pk,'notes':'验收演示','admission_id':admission.pk,'items':[{'medicine_id':medicine.pk,'dosage':'每次 1 片','frequency':'每日两次','duration':'3 天','quantity':1},{'medicine_id':first_medicine.pk,'dosage':'每次 1 片','frequency':'每日一次','duration':'3 天','quantity':2}]},format='json')
        self.verify('住院期间处方归集到本次住院',prescription.status_code==201 and prescription.data['admission_id']==admission.pk,str(prescription.data.get('admission_no')))
        medicine_bill=BillingRecord.objects.get(prescription_id=prescription.data['id'])
        self.verify('处方明细保留开具时单价快照',str(medicine_bill.amount)==str(prescription.data['total_amount']),f"账单 {medicine_bill.amount} / 展示 {prescription.data['total_amount']}")
        charge=admin.get(f'/api/v1/inpatients/{admission_id}/charges/')
        medicine_row=next(item for item in charge.data['items'] if item['prescription_id']==prescription.data['id'])
        self.verify('多药品处方按药品分别展示明细行',len(medicine_row['charge_details'])==2 and all(line['unit_price'] and line['quantity']>=1 and line['amount'] for line in medicine_row['charge_details']))
        self.verify('明细行金额之和等于账单金额',Decimal(medicine_row['details_total'])==Decimal(medicine_row['amount']),f"{medicine_row['details_total']} = {medicine_row['amount']}")
        examination=doctor.post('/api/v1/examinations/',{'record_id':record.pk,'item_id':exam_item.pk,'type':'lab','clinical_question':'验收演示','admission_id':admission.pk},format='json')
        self.verify('住院期间检查归集到本次住院',examination.status_code==201 and examination.data['admission_no']==admission.admission_no)
        manual=admin.post('/api/v1/billing-records/',{'patient_id':target.pk,'admission_id':admission.pk,'category':'other','description':'验收演示：住院陪护费','amount':'30.00'},format='json')
        self.verify('管理员录入的其他费用归集到住院',manual.status_code==201 and BillingRecord.objects.get(pk=manual.data['id']).inpatient_admission_id==admission.pk)
        wrong=admin.post('/api/v1/billing-records/',{'patient_id':other.pk,'admission_id':admission.pk,'category':'other','description':'患者不一致校验','amount':'10.00'},format='json')
        self.verify('归集时校验患者一致与住院状态',wrong.status_code==400)
        overview=admin.get(f'/api/v1/inpatients/{admission_id}/charges/')
        billed=Decimal(overview.data['summary']['billed_amount']);projected=Decimal(overview.data['summary']['projected_bed_fee'])
        self.verify('住院中展示逐项费用与预计床位费',billed>0 and projected>0,f"合计 {billed}，预计床位费 {projected}")
        medicine_bill.refresh_from_db();charge_date=admin.get(f'/api/v1/billing-records/{medicine_bill.pk}/').data['charge_date']
        paid=patient.post(f'/api/v1/billing-records/{medicine_bill.pk}/pay/',{'payment_method':'演示支付'},format='json')
        self.verify('药品账单支付后自动发药',paid.status_code==200)
        self.verify('支付不改变费用发生日期',paid.data['charge_date']==charge_date and bool(paid.data['payment_date']),f"发生 {paid.data['charge_date']} / 支付 {paid.data['payment_date']}")
        self.verify('同一药品账单不可重复支付',patient.post(f'/api/v1/billing-records/{medicine_bill.pk}/pay/',{'payment_method':'重复支付'},format='json').status_code==400)
        exam_bill=BillingRecord.objects.get(examination_id=examination.data['id'])
        self.verify('检查账单可单独支付',patient.post(f'/api/v1/billing-records/{exam_bill.pk}/pay/',{'payment_method':'演示支付'},format='json').status_code==200)
        before=admin.get(f'/api/v1/inpatients/{admission_id}/charges/').data['summary']
        self.verify('多张账单分别支付后已付待付正确',Decimal(before['paid_amount'])>0 and Decimal(before['paid_amount'])+Decimal(before['unpaid_amount'])==Decimal(before['billed_amount']),f"已付 {before['paid_amount']}，待付 {before['unpaid_amount']}")
        discharge=doctor.post(f'/api/v1/inpatients/{admission_id}/discharge/',{'discharge_summary':'验收演示：症状缓解，予以出院。'},format='json')
        self.verify('主治医师办理出院',discharge.status_code==200)
        free_bed.refresh_from_db();self.verify('出院释放床位',not free_bed.is_occupied)
        board=admin.get('/api/v1/ward-beds/board/')
        card=next(bed for bed in board.data['beds'] if bed['id']==free_bed.pk)
        self.verify('出院后卡片回到空闲状态',card['status']=='available' and card['occupancy'] is None)
        bed_bills=BillingRecord.objects.filter(admission_id=admission_id)
        self.verify('出院只生成一张床位费账单',bed_bills.count()==1,str(bed_bills.first().amount))
        frozen=bed_bills.first().amount
        repeated=doctor.post(f'/api/v1/inpatients/{admission_id}/discharge/',{'discharge_summary':'重复出院'},format='json')
        self.verify('重复出院被拒绝且床位费金额固定',repeated.status_code==400 and BillingRecord.objects.get(pk=bed_bills.first().pk).amount==frozen)
        final=admin.get(f'/api/v1/inpatients/{admission_id}/charges/').data['summary']
        self.verify('出院后金额固定且不再预估床位费',Decimal(final['projected_bed_fee'])==0 and Decimal(final['billed_amount'])==Decimal(before['billed_amount'])+Decimal(frozen),f"出院合计 {final['billed_amount']}")
        self.verify('出院账单明细与总额一致',all(Decimal(row['details_total'])==Decimal(row['amount']) for row in admin.get(f'/api/v1/inpatients/{admission_id}/charges/').data['items'] if row['charge_details']))
