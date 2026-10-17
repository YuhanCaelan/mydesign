"""只归集能通过患者、关联预约和发生时间唯一确定归属的历史账单。

无法唯一确定的记录保留原样（inpatient_admission 为空），不做任何推测，
避免把门诊或会诊费用错误计入某一次住院。
"""

from django.db import migrations,models


def assign_existing_charges(apps,schema_editor):
    BillingRecord=apps.get_model('healthcare','BillingRecord')
    InpatientAdmission=apps.get_model('healthcare','InpatientAdmission')

    # 出院床位费账单本身已经通过 admission 唯一关联，直接补齐所属住院，避免重复展示。
    BillingRecord.objects.filter(admission__isnull=False,inpatient_admission__isnull=True).update(inpatient_admission=models.F('admission'))

    candidates=BillingRecord.objects.filter(inpatient_admission__isnull=True).order_by('pk')
    for bill in candidates.iterator():
        if bill.created_at is None:continue
        matches=[]
        for admission in InpatientAdmission.objects.filter(patient_id=bill.patient_id).order_by('pk'):
            if admission.appointment_id and bill.appointment_id:
                if admission.appointment_id==bill.appointment_id:matches.append(admission)
                continue
            if admission.appointment_id or bill.appointment_id:continue
            if admission.admitted_at is None:continue
            if bill.created_at<admission.admitted_at:continue
            if admission.discharged_at and bill.created_at>admission.discharged_at:continue
            matches.append(admission)
        if len(matches)!=1:continue
        BillingRecord.objects.filter(pk=bill.pk,inpatient_admission__isnull=True).update(inpatient_admission=matches[0])


def unassign_charges(apps,schema_editor):
    BillingRecord=apps.get_model('healthcare','BillingRecord')
    BillingRecord.objects.filter(admission__isnull=True).update(inpatient_admission=None)


class Migration(migrations.Migration):
    dependencies=[('healthcare','0005_billingrecord_inpatient_admission_and_more')]
    operations=[migrations.RunPython(assign_existing_charges,unassign_charges)]
