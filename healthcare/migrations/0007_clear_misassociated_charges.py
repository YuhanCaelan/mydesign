"""修正历史账单归集的住院时间校验，并清理可确定的误关联。

`inpatient_admission` 关联的费用必须发生在该次住院的时间窗内（入院时间之后、出院时间之前）。
出院床位费账单通过 `admission` 一对一关联，即使创建于出院当时也不属于误关联，予以保留。
无法确定的记录保持原样，不做任何推测。
"""

from django.db import migrations

def clear_misassociated_charges(apps,schema_editor):
    BillingRecord=apps.get_model('healthcare','BillingRecord')
    InpatientAdmission=apps.get_model('healthcare','InpatientAdmission')
    cleared=0;kept=0
    rows=BillingRecord.objects.filter(inpatient_admission__isnull=False).select_related('inpatient_admission').order_by('pk')
    for bill in rows.iterator():
        admission=bill.inpatient_admission
        if admission is None:continue
        if bill.admission_id==admission.pk:kept+=1;continue
        if bill.created_at is None or admission.admitted_at is None:kept+=1;continue
        outside=bill.created_at<admission.admitted_at or (admission.discharged_at is not None and bill.created_at>admission.discharged_at)
        if outside:
            BillingRecord.objects.filter(pk=bill.pk).update(inpatient_admission=None);cleared+=1
        else:kept+=1
    return cleared


def noop(apps,schema_editor):
    """误关联的原始归属无法从当前数据还原，回滚时不做任何修改。"""


class Migration(migrations.Migration):
    dependencies=[('healthcare','0006_assign_historical_charges_to_admissions')]
    operations=[migrations.RunPython(clear_misassociated_charges,noop)]
