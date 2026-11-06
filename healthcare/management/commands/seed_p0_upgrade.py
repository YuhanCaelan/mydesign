from django.core.management.base import BaseCommand
from django.db import transaction
from healthcare.models import Department, ProcedureItem, RecordTemplate, User


class Command(BaseCommand):
    help='补充 P0/P1 演示岗位、处置项目与病历模板（可重复执行）。'

    @transaction.atomic
    def handle(self,*args,**options):
        department=Department.objects.filter(status=Department.Status.ACTIVE).order_by('pk').first()
        if department is None:
            department=Department.objects.create(name='全科医学科',description='演示科室')
        stations=[
            ('schedule_staff','排班员','王排班',User.Station.SCHEDULE),
            ('admission_staff','住院处','李住院',User.Station.ADMISSION),
            ('cashier','收费员','赵收费',User.Station.CASHIER),
            ('pharmacy','药房药师','钱药房',User.Station.PHARMACY),
            ('tech','医技执行','孙医技',User.Station.EXECUTION),
        ]
        for username,title,name,station in stations:
            user,created=User.objects.get_or_create(username=username,defaults={'first_name':name,'role':User.Role.STAFF,'station':station,'department':department})
            if not created:
                user.role=User.Role.STAFF;user.station=station;user.department=department;user.first_name=user.first_name or name;user.save()
            user.set_password('Staff123!');user.save(update_fields=['password'])
            self.stdout.write(f'事务员 {username} / Staff123! （{title}）')
        nurse,created=User.objects.get_or_create(username='nurse',defaults={'first_name':'周护士','role':User.Role.NURSE,'department':department,'ward':''})
        nurse.role=User.Role.NURSE;nurse.department=department;nurse.save()
        nurse.set_password('Nurse123!');nurse.save(update_fields=['password'])
        self.stdout.write('护士 nurse / Nurse123!')
        procedures=[
            ('静脉输液','treatment','35.00','静脉给药，观察输液反应'),
            ('皮试','treatment','15.00','皮试后观察 20 分钟'),
            ('清创缝合','minor_surgery','180.00','清创后缝合，注意破伤风'),
            ('打石膏','treatment','260.00','患肢固定，观察末梢循环'),
            ('换药','nursing','30.00','无菌换药，观察创面'),
            ('日间手术-体表肿物切除','day_surgery','680.00','日间手术，术前评估后预约'),
        ]
        for name,category,price,description in procedures:
            ProcedureItem.objects.get_or_create(name=name,defaults={'category':category,'price':price,'execution_department':department,'description':description,'is_active':True})
        templates=[
            ('偏头痛','偏头痛','反复{{side}}侧头痛{{duration}}，呈搏动样，伴恶心。','头痛反复发作，劳累后加重，无发热。','无特殊。','神清，{{side}}侧颞部压痛，神经系统查体未见明显定位体征。','偏头痛（{{severity}}）','{{side}}侧头痛，{{severity}}，建议休息、避免诱因，必要时止痛治疗。'),
            ('上呼吸道感染','上呼吸道感染','{{duration}}前受凉后出现咽痛、流涕。','咽痛、鼻塞，无呼吸困难。','无特殊。','咽部充血，双肺呼吸音清。','上呼吸道感染（{{severity}}）','对症治疗，多饮水，{{severity}}时复诊。'),
            ('急性胃肠炎','急性胃肠炎','{{duration}}前出现腹泻、腹痛。','腹泻数次，无脓血便。','无特殊。','腹软，脐周轻压痛。','急性胃肠炎（{{severity}}）','补液、清淡饮食，观察尿量。'),
            ('高血压复诊','原发性高血压','高血压病史，{{duration}}来{{severity}}。','规律服药，偶有头晕。','高血压病史。','血压升高，心肺未见明显异常。','原发性高血压（{{severity}}）','监测血压，调整用药。'),
            ('膝关节骨关节炎','膝关节骨关节炎','{{side}}膝关节疼痛{{duration}}，上下楼加重。','疼痛逐渐加重，无外伤。','无特殊。','{{side}}膝关节压痛，活动受限。','{{side}}膝关节骨关节炎（{{severity}}）','减少负重，理疗，必要时关节腔注射。'),
            ('腰椎间盘突出','腰椎间盘突出','{{side}}下肢放射痛{{duration}}。','久坐后加重，休息缓解。','无特殊。','{{side}}侧直腿抬高试验阳性。','腰椎间盘突出（{{severity}}）','避免久坐，康复训练。'),
            ('皮肤软组织感染','皮肤软组织感染','{{side}}侧皮肤红肿{{duration}}。','局部红肿热痛，无发热。','无特殊。','{{side}}侧皮肤红肿，皮温升高。','皮肤软组织感染（{{severity}}）','抗感染，局部处理。'),
            ('换药/拆线','术后换药','{{side}}侧切口{{duration}}。','切口无渗液，无发热。','手术史。','切口愈合良好。','术后换药','无菌换药，{{duration}}后拆线。'),
        ]
        for name,diagnosis,chief,present,past,exam,treat in [
            (row[0],row[1],row[2],row[3],row[4],row[5],row[7]) for row in templates
        ]:
            variables={'side':['左侧','右侧','双侧'],'severity':['轻度','中度','重度'],'duration':['1 天','3 天','1 周']}
            RecordTemplate.objects.get_or_create(name=name,defaults={'department':department,'diagnosis':diagnosis,'chief_complaint':chief,'present_illness':present,'past_history':past,'examination':exam,'treatment':treat,'variables':variables,'is_active':True})
        self.stdout.write(self.style.SUCCESS(f'已补充 {len(procedures)} 个处置项目、{len(templates)} 个病历模板；科室：{department.name}'))
