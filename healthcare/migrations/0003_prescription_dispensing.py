from django.db import migrations,models
import django.db.models.deletion


def backfill_prescription_bills(apps,schema_editor):
    Prescription=apps.get_model('healthcare','Prescription');BillingRecord=apps.get_model('healthcare','BillingRecord')
    for prescription in Prescription.objects.filter(status='issued').select_related('record__appointment__patient'):
        if BillingRecord.objects.filter(prescription_id=prescription.pk).exists():continue
        items=list(prescription.items.select_related('medicine'))
        amount=sum(item.medicine.price*item.quantity for item in items);names='、'.join(item.medicine.name for item in items)
        BillingRecord.objects.create(bill_no=f'BL-MED-{prescription.pk:08d}',patient_id=prescription.record.appointment.patient_id,appointment_id=prescription.record.appointment_id,prescription_id=prescription.pk,category='medicine',description=f'处方 {prescription.prescription_no}：{names}'[:200],amount=amount,status='unpaid')


class Migration(migrations.Migration):
    dependencies=[('healthcare','0002_core_operations')]
    operations=[
        migrations.AddField(model_name='prescription',name='dispensed_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AlterField(model_name='prescription',name='status',field=models.CharField(choices=[('issued','待缴费取药'),('dispensed','已取药'),('cancelled','已作废')],db_index=True,default='issued',max_length=12)),
        migrations.AddField(model_name='billingrecord',name='prescription',field=models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='billing_record',to='healthcare.prescription')),
        migrations.RunPython(backfill_prescription_bills,migrations.RunPython.noop),
    ]
