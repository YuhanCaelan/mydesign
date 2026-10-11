from django.db import migrations,models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies=[('healthcare','0001_initial')]
    operations=[
        migrations.AddField(
            model_name='doctorprofile',name='departments',
            field=models.ManyToManyField(blank=True,related_name='member_doctors',to='healthcare.department'),
        ),
        migrations.AddField(
            model_name='doctorprofile',name='is_super_doctor',
            field=models.BooleanField(default=False,help_text='演示用全科医师，可参与全部科室业务。'),
        ),
        migrations.AddField(model_name='billingrecord',name='bill_no',field=models.CharField(blank=True,max_length=24,unique=True)),
        migrations.AddField(
            model_name='billingrecord',name='category',
            field=models.CharField(choices=[('registration','挂号费'),('examination','检查费'),('medicine','药品费'),('inpatient','住院费'),('other','其他')],default='other',max_length=20),
        ),
        migrations.AddField(model_name='billingrecord',name='paid_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='billingrecord',name='payment_method',field=models.CharField(blank=True,max_length=30)),
        migrations.AlterModelOptions(name='billingrecord',options={'ordering':['-created_at']}),
        migrations.CreateModel(
            name='InpatientAdmission',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
                ('admission_no',models.CharField(blank=True,max_length=24,unique=True)),
                ('ward',models.CharField(max_length=80)),('bed_no',models.CharField(max_length=30)),
                ('admission_diagnosis',models.TextField()),('discharge_summary',models.TextField(blank=True)),
                ('status',models.CharField(choices=[('pending','待入院'),('admitted','住院中'),('discharged','已出院'),('cancelled','已取消')],db_index=True,default='pending',max_length=12)),
                ('admitted_at',models.DateTimeField(blank=True,null=True)),('discharged_at',models.DateTimeField(blank=True,null=True)),
                ('appointment',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='admissions',to='healthcare.appointment')),
                ('attending_doctor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='admissions',to='healthcare.doctorprofile')),
                ('department',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='admissions',to='healthcare.department')),
                ('patient',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='admissions',to='healthcare.patientprofile')),
            ],
            options={'ordering':['-created_at']},
        ),
    ]
