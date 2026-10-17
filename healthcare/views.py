import mimetypes
from datetime import date as date_cls,timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Count,F,Max,Q,Sum
from django.http import FileResponse,Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins,status,viewsets
from rest_framework.decorators import action,api_view,permission_classes
from rest_framework.exceptions import PermissionDenied,ValidationError as APIValidationError
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from .models import *
from .permissions import IsAdmin,IsAdminOrReadOnly,IsAdminWriteOrClinicalRead
from .serializers import *
from .services import VALID_RELATIONSHIP_STATUSES,admit_patient,audit,bed_status_key,board_bed_payload,department_scope,ensure_admission_operator,finish_admission,has_doctor_patient_relationship,link_inpatient,record_stock_movement,transition_appointment


def parse_date_query(value,name='date',default=None):
    """统一解析 YYYY-MM-DD 查询参数，返回 date；空值使用默认值。"""
    if value in (None,''):
        return default
    try:return date_cls.fromisoformat(str(value))
    except (TypeError,ValueError):raise APIValidationError({name:'日期格式应为 YYYY-MM-DD。'})

def money(value):
    return str(Decimal(value or 0).quantize(Decimal('0.01')))

def int_query(value,name,default=None,minimum=0,maximum=None):
    if value in (None,''):return default
    try:number=int(value)
    except (TypeError,ValueError):raise APIValidationError({name:'参数必须为整数。'})
    if number<minimum:raise APIValidationError({name:f'参数不能小于 {minimum}。'})
    if maximum is not None and number>maximum:number=maximum
    return number

def page_slice(queryset,page,page_size):
    total=queryset.count()
    offset=(page-1)*page_size
    return total,list(queryset[offset:offset+page_size])

def page_meta(request,default_size=20,maximum=100):
    page=int_query(request.query_params.get('page'),'page',1,1)
    size=int_query(request.query_params.get('page_size'),'page_size',default_size,1,maximum)
    return page,size

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer=LoginSerializer(data=request.data,context={'request':request});serializer.is_valid(raise_exception=True)
    user=User.objects.get(pk=serializer.validated_data['user']['id']);audit(request,'login','auth',user,'用户登录')
    return Response(serializer.validated_data)

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer=RegisterSerializer(data=request.data);serializer.is_valid(raise_exception=True);user=serializer.save()
    return Response(SessionUserSerializer(user,context={'request':request}).data,status=status.HTTP_201_CREATED)

@api_view(['GET','PATCH'])
@permission_classes([IsAuthenticated])
def me(request):
    user=request.user
    if request.method=='PATCH':
        allowed={'full_name','phone','email'};data={k:v for k,v in request.data.items() if k in allowed}
        if 'full_name' in data:user.first_name=str(data.pop('full_name')).strip();user.last_name=''
        for key,value in data.items():setattr(user,key,value)
        user.save();audit(request,'update','profile',user,'更新个人资料')
    return Response(SessionUserSerializer(user,context={'request':request}).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer=ChangePasswordSerializer(data=request.data,context={'request':request});serializer.is_valid(raise_exception=True)
    request.user.set_password(serializer.validated_data['new_password']);request.user.save(update_fields=['password']);audit(request,'change_password','profile',request.user,'修改账户密码')
    return Response({'detail':'密码修改成功，请重新登录。'})

class UserViewSet(viewsets.ModelViewSet):
    permission_classes=[IsAdmin];serializer_class=AdminUserSerializer;http_method_names=['get','post','patch','head','options']
    def get_queryset(self):
        """业务账户列表只返回医师与患者，管理员账号不混入；角色与启用状态均支持服务端筛选。"""
        qs=User.objects.select_related('doctor_profile__department','patient_profile').exclude(is_superuser=True).exclude(role=User.Role.ADMIN).order_by('-created_at')
        role=self.request.query_params.get('role','').strip();state=self.request.query_params.get('is_active','').strip();search=self.request.query_params.get('search','').strip()
        if role:
            if role not in {User.Role.DOCTOR,User.Role.PATIENT}:raise APIValidationError({'role':'仅支持 doctor 或 patient。'})
            qs=qs.filter(role=role)
        if state in {'true','false'}:qs=qs.filter(is_active=state=='true')
        if search:qs=qs.filter(Q(username__icontains=search)|Q(first_name__icontains=search)|Q(phone__icontains=search)|Q(doctor_profile__doctor_no__icontains=search)|Q(patient_profile__patient_no__icontains=search)|Q(doctor_profile__title__icontains=search)|Q(doctor_profile__specialty__icontains=search))
        return qs
    def perform_create(self,serializer):obj=serializer.save();audit(self.request,'create','user',obj,'创建业务账户')
    def perform_update(self,serializer):obj=serializer.save();audit(self.request,'update','user',obj,'更新业务账户')

class DepartmentViewSet(viewsets.ModelViewSet):
    permission_classes=[IsAdminOrReadOnly];serializer_class=DepartmentSerializer;queryset=Department.objects.all();http_method_names=['get','post','patch','head','options']
    search_fields=('name','description');ordering_fields=('name','created_at')
    def get_queryset(self):
        qs=super().get_queryset();state=self.request.query_params.get('status')
        if state:qs=qs.filter(status=state)
        return qs
    def perform_create(self,serializer):obj=serializer.save();audit(self.request,'create','department',obj)
    def perform_update(self,serializer):obj=serializer.save();audit(self.request,'update','department',obj)

    def _require_staff(self):
        if self.request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('科室就诊信息仅对管理员和医师开放。')

    def _stats(self,department,day):
        """科室某日统计：预约状态、当班医师与历史患者，全部来自业务记录。"""
        base=Appointment.objects.filter(department_scope(department),slot__schedule__date=day)
        counts=base.aggregate(total=Count('id'),pending=Count('id',filter=Q(status=Appointment.Status.PENDING)),in_progress=Count('id',filter=Q(status=Appointment.Status.IN_PROGRESS)),completed=Count('id',filter=Q(status=Appointment.Status.COMPLETED)),cancelled=Count('id',filter=Q(status=Appointment.Status.CANCELLED)),no_show=Count('id',filter=Q(status=Appointment.Status.NO_SHOW)))
        active_doctors=DoctorProfile.objects.filter(Q(department=department)|Q(departments=department),user__is_active=True,schedules__date=day,schedules__is_active=True).distinct().count()
        history_patients=Appointment.objects.filter(department_scope(department),slot__schedule__date__lte=day).exclude(status=Appointment.Status.CANCELLED).values('patient_id').distinct().count()
        return {**counts,'active_doctors':active_doctors,'history_patients':history_patients}

    @action(detail=False,methods=['get'])
    def overview(self,request):
        """科室卡片统计：按日期返回每个科室的预约状态、当班医师与历史患者数。"""
        self._require_staff()
        day=parse_date_query(request.query_params.get('date'),default=timezone.localdate())
        results=[]
        for department in self.get_queryset():
            results.append({**DepartmentSerializer(department).data,'stats':self._stats(department,day)})
        audit(request,'read','department_overview',None,f'查看科室概览 {day}')
        return Response({'date':str(day),'count':len(results),'results':results,'notes':{'department_basis':'科室归属以预约时的医师所属科室快照为准；历史预约缺少快照时按医师当前主科室回填。','history_patients':'该科室曾有有效预约（未取消）的去重患者数。','active_doctors':'该日期存在开放排班的去重医师数。'}})

    @action(detail=True,methods=['get'])
    def visits(self,request,pk=None):
        """当日就诊明细；医师只能查看本人负责的预约，管理员可查看全科室。"""
        self._require_staff();department=self.get_object();day=parse_date_query(request.query_params.get('date'),default=timezone.localdate())
        qs=Appointment.objects.select_related('patient__user','doctor__user','doctor__department','department','slot__schedule','medical_record').filter(department_scope(department),slot__schedule__date=day)
        if request.user.role==User.Role.DOCTOR:qs=qs.filter(doctor__user=request.user)
        state=request.query_params.get('status')
        if state in Appointment.Status.values:qs=qs.filter(status=state)
        qs=qs.order_by('slot__start_time','pk')
        page,size=page_meta(request);total,rows=page_slice(qs,page,size)
        audit(request,'read','department_visits',department,f'查看科室当日就诊 {day}')
        return Response({'date':str(day),'department_id':department.pk,'department_name':department.name,'count':total,'page':page,'page_size':size,'results':AppointmentSerializer(rows,many=True,context={'request':request}).data})

    @action(detail=True,methods=['get'])
    def doctors(self,request,pk=None):
        """科室当班医师及排班号源统计。"""
        self._require_staff();department=self.get_object();day=parse_date_query(request.query_params.get('date'),default=timezone.localdate())
        doctors=DoctorProfile.objects.filter(Q(department=department)|Q(departments=department),user__is_active=True,schedules__date=day,schedules__is_active=True).select_related('user','department').prefetch_related('departments','schedules__slots').distinct().order_by('doctor_no')
        results=[]
        for doctor in doctors:
            schedules=[]
            for schedule in doctor.schedules.all():
                if schedule.date!=day or not schedule.is_active:continue
                slots=list(schedule.slots.all());appointments=Appointment.objects.filter(slot__in=slots).values_list('slot_id',flat=True)
                schedules.append({'id':schedule.pk,'time_range':f'{schedule.start_time:%H:%M}–{schedule.end_time:%H:%M}','slot_minutes':schedule.slot_minutes,'total_slots':len(slots),'available_slots':sum(1 for slot in slots if slot.status==AppointmentSlot.Status.AVAILABLE),'booked_slots':sum(1 for slot in slots if slot.status==AppointmentSlot.Status.BOOKED),'appointment_ids':list(appointments)})
            schedules.sort(key=lambda row:row['time_range'])
            results.append({**DoctorSerializer(doctor,context={'request':request}).data,'schedules':schedules,'schedule_count':len(schedules)})
        return Response({'date':str(day),'department_id':department.pk,'department_name':department.name,'count':len(results),'results':results})

    @action(detail=True,methods=['get'],url_path='history-patients')
    def history_patients(self,request,pk=None):
        """历史患者：按日期区间分页返回该科室有有效预约的去重患者。"""
        self._require_staff();department=self.get_object()
        start=parse_date_query(request.query_params.get('date_from'),'date_from');end=parse_date_query(request.query_params.get('date_to'),'date_to')
        if start and end and start>end:raise APIValidationError({'date_to':'结束日期不能早于开始日期。'})
        # “历史患者”只统计已经发生的有效预约，未来预约不计入历史。
        base=Appointment.objects.filter(department_scope(department),slot__schedule__date__lte=timezone.localdate()).exclude(status=Appointment.Status.CANCELLED)
        if request.user.role==User.Role.DOCTOR:base=base.filter(doctor__user=request.user)
        if start:base=base.filter(slot__schedule__date__gte=start)
        if end:base=base.filter(slot__schedule__date__lte=min(end,timezone.localdate()))
        search=request.query_params.get('search','').strip()
        if search:base=base.filter(Q(patient__user__first_name__icontains=search)|Q(patient__patient_no__icontains=search)|Q(patient__user__phone__icontains=search))
        rows=base.values('patient_id').annotate(visit_count=Count('id'),last_visit=Max('slot__schedule__date')).order_by('-last_visit','patient_id')
        page,size=page_meta(request);total=rows.count();offset=(page-1)*size;page_rows=list(rows[offset:offset+size])
        patients={item.pk:item for item in PatientProfile.objects.select_related('user').filter(pk__in=[row['patient_id'] for row in page_rows])}
        results=[]
        for row in page_rows:
            patient=patients.get(row['patient_id'])
            if patient is None:continue
            results.append({'patient_id':patient.pk,'patient_no':patient.patient_no,'full_name':patient.user.get_full_name(),'phone':patient.user.phone,'gender_display':patient.get_gender_display(),'visit_count':row['visit_count'],'last_visit':str(row['last_visit']) if row['last_visit'] else None})
        audit(request,'read','department_history_patients',department,'查看科室历史患者')
        return Response({'department_id':department.pk,'department_name':department.name,'date_from':str(start) if start else None,'date_to':str(end) if end else None,'count':total,'page':page,'page_size':size,'results':results})

class DoctorViewSet(viewsets.ModelViewSet):
    serializer_class=DoctorSerializer;queryset=DoctorProfile.objects.select_related('user','department').prefetch_related('departments').filter(user__is_active=True).order_by('doctor_no')
    http_method_names=['get','patch','head','options']
    search_fields=('user__first_name','doctor_no','title','specialty','department__name');ordering_fields=('doctor_no','created_at')
    def get_queryset(self):
        qs=super().get_queryset();department=self.request.query_params.get('department')
        if department:qs=qs.filter(Q(department_id=department)|Q(departments__id=department)|Q(is_super_doctor=True)).distinct()
        return qs
    def perform_update(self,serializer):
        obj=self.get_object()
        if self.request.user.role==User.Role.DOCTOR and obj.user_id!=self.request.user.id:raise PermissionDenied('只能修改自己的医师资料。')
        if self.request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权修改医师资料。')
        obj=serializer.save();audit(self.request,'update','doctor_profile',obj,'更新医师资料')
    @action(detail=False,methods=['get','patch'],url_path='me')
    def me_profile(self,request):
        if request.user.role!=User.Role.DOCTOR:raise PermissionDenied('仅医师可访问个人医师档案。')
        obj=get_object_or_404(DoctorProfile,user=request.user)
        if request.method=='PATCH':
            serializer=self.get_serializer(obj,data=request.data,partial=True);serializer.is_valid(raise_exception=True);serializer.save();audit(request,'update','doctor_profile',obj,'更新个人医师档案')
        return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['get'])
    def slots(self,request,pk=None):
        date=request.query_params.get('date');qs=AppointmentSlot.objects.select_related('schedule').filter(schedule__doctor=self.get_object(),schedule__is_active=True,status=AppointmentSlot.Status.AVAILABLE)
        if date:qs=qs.filter(schedule__date=date)
        qs=qs.filter(schedule__date__gte=timezone.localdate())
        return Response(SlotSerializer(qs,many=True).data)

class PatientViewSet(viewsets.ModelViewSet):
    serializer_class=PatientSerializer;queryset=PatientProfile.objects.select_related('user').order_by('patient_no')
    http_method_names=['get','patch','head','options']
    search_fields=('user__first_name','patient_no','user__phone');ordering_fields=('patient_no','created_at')
    def get_queryset(self):
        """医师只能读取与本人存在预约关系的患者；患者仅本人；管理员全院。"""
        user=self.request.user;qs=super().get_queryset()
        if user.role==User.Role.ADMIN:return qs
        if user.role==User.Role.PATIENT:return qs.filter(user=user)
        if user.role==User.Role.DOCTOR:return qs.filter(appointments__doctor__user=user,appointments__status__in=VALID_RELATIONSHIP_STATUSES).distinct()
        return qs.none()
    def retrieve(self,request,*args,**kwargs):
        obj=self.get_object();audit(request,'read','patient',obj,'读取患者档案');return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['get'],url_path='clinical-history')
    def clinical_history(self,request,pk=None):
        """患者纵向病历：分页返回全部已确认病历、关联检查摘要与附件，按就诊日期倒序。"""
        patient=self.get_object();user=request.user
        if user.role not in {User.Role.ADMIN,User.Role.DOCTOR,User.Role.PATIENT}:raise PermissionDenied('无权读取患者病历。')
        qs=MedicalRecord.objects.filter(appointment__patient=patient,status=MedicalRecord.Status.CONFIRMED).select_related('appointment__patient__user','appointment__doctor__user','appointment__doctor__department','appointment__department','appointment__slot__schedule').prefetch_related('corrections__author','examination_orders__report','examination_orders__files','examination_orders__item','prescriptions','appointment__admissions')
        start=parse_date_query(request.query_params.get('date_from'),'date_from');end=parse_date_query(request.query_params.get('date_to'),'date_to')
        if start and end and start>end:raise APIValidationError({'date_to':'结束日期不能早于开始日期。'})
        if start:qs=qs.filter(appointment__slot__schedule__date__gte=start)
        if end:qs=qs.filter(appointment__slot__schedule__date__lte=end)
        department=request.query_params.get('department','').strip()
        if department:
            if department.isdigit():qs=qs.filter(Q(appointment__department_id=int(department))|Q(appointment__department__isnull=True,appointment__doctor__department_id=int(department)))
            else:qs=qs.filter(Q(appointment__department__name__icontains=department)|Q(appointment__department__isnull=True,appointment__doctor__department__name__icontains=department))
        diagnosis=request.query_params.get('diagnosis','').strip()
        if diagnosis:qs=qs.filter(diagnosis__icontains=diagnosis)
        keyword=request.query_params.get('search','').strip() or request.query_params.get('record_no','').strip()
        if keyword:qs=qs.filter(Q(record_no__icontains=keyword)|Q(diagnosis__icontains=keyword)|Q(chief_complaint__icontains=keyword))
        qs=qs.order_by('-appointment__slot__schedule__date','-confirmed_at','-pk')
        page,size=page_meta(request,default_size=10,maximum=50);total,rows=page_slice(qs,page,size)
        basis='self' if user.role==User.Role.PATIENT else 'admin' if user.role==User.Role.ADMIN else 'doctor_relationship'
        audit(request,'read','patient_clinical_history',patient,f'读取患者纵向病历（{total} 份已确认）')
        return Response({'patient':PatientSerializer(patient,context={'request':request}).data,'count':total,'page':page,'page_size':size,'results':MedicalRecordSerializer(rows,many=True,context={'request':request}).data,'filters':{'date_from':str(start) if start else None,'date_to':str(end) if end else None,'department':department or None,'diagnosis':diagnosis or None,'search':keyword or None},'permission_basis':basis,'notes':'仅返回已确认病历；检查报告与附件按当前业务权限展示。'})
    def perform_update(self,serializer):
        obj=self.get_object()
        if self.request.user.role==User.Role.PATIENT and obj.user_id!=self.request.user.id:raise PermissionDenied('只能修改自己的患者档案。')
        if self.request.user.role not in {User.Role.ADMIN,User.Role.PATIENT}:raise PermissionDenied('无权修改患者档案。')
        obj=serializer.save();audit(self.request,'update','patient_profile',obj,'更新患者档案')
    @action(detail=False,methods=['get','patch'],url_path='me')
    def me_profile(self,request):
        if request.user.role!=User.Role.PATIENT:raise PermissionDenied('仅患者可访问个人患者档案。')
        obj=get_object_or_404(PatientProfile,user=request.user)
        if request.method=='PATCH':
            serializer=self.get_serializer(obj,data=request.data,partial=True);serializer.is_valid(raise_exception=True);serializer.save();audit(request,'update','patient_profile',obj,'更新个人患者档案')
        return Response(self.get_serializer(obj).data)

class ScheduleViewSet(viewsets.ModelViewSet):
    serializer_class=ScheduleSerializer;queryset=DoctorSchedule.objects.select_related('doctor__user').prefetch_related('slots');http_method_names=['get','post','patch','head','options']
    ordering_fields=('date','start_time','created_at')
    def get_queryset(self):
        qs=super().get_queryset();user=self.request.user
        if user.role==User.Role.DOCTOR:qs=qs.filter(doctor__user=user)
        elif user.role==User.Role.PATIENT:qs=qs.filter(is_active=True,date__gte=timezone.localdate())
        return qs
    def perform_create(self,serializer):
        user=self.request.user
        if user.role==User.Role.DOCTOR:obj=serializer.save(doctor=user.doctor_profile)
        elif user.role==User.Role.ADMIN:obj=serializer.save()
        else:raise PermissionDenied('无权创建排班。')
        audit(self.request,'create','schedule',obj)
    def perform_update(self,serializer):
        if self.request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权修改排班。')
        obj=serializer.save();audit(self.request,'update','schedule',obj)
    @action(detail=False,methods=['get'])
    def outpatient(self,request):
        """门诊就诊视图：医师 → 排班 → 号源 → 患者，支持日期区间、科室、医师与状态筛选。"""
        user=request.user
        if user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('门诊就诊视图仅对管理员和医师开放。')
        today=timezone.localdate();day=parse_date_query(request.query_params.get('date'),'date');start=parse_date_query(request.query_params.get('date_from'),'date_from');end=parse_date_query(request.query_params.get('date_to'),'date_to')
        if day:start=end=day
        if start is None:start=end=today
        if end is None:end=start
        if start>end:raise APIValidationError({'date_to':'结束日期不能早于开始日期。'})
        if (end-start).days>31:raise APIValidationError({'date_to':'查询区间不能超过 31 天。'})
        department_id=int_query(request.query_params.get('department'),'department');doctor_id=int_query(request.query_params.get('doctor'),'doctor');state=request.query_params.get('status','').strip()
        valid_states=set(Appointment.Status.values)|{AppointmentSlot.Status.AVAILABLE,AppointmentSlot.Status.CLOSED}
        if state and state not in valid_states:raise APIValidationError({'status':'不支持的预约或号源状态。'})
        qs=DoctorSchedule.objects.select_related('doctor__user','doctor__department').prefetch_related('doctor__departments','slots__appointments__patient__user','slots__appointments__medical_record','slots__appointments__department','slots__appointments__doctor__user').filter(date__range=(start,end))
        if doctor_id:qs=qs.filter(doctor_id=doctor_id)
        if department_id:qs=qs.filter(Q(doctor__department_id=department_id)|Q(doctor__departments__id=department_id)).distinct()
        if user.role==User.Role.DOCTOR:qs=qs.filter(doctor__user=user)
        qs=qs.order_by('date','doctor__doctor_no','start_time','pk')
        page,size=page_meta(request);total,schedules=page_slice(qs,page,size)
        status_labels={**{value:label for value,label in Appointment.Status.choices},AppointmentSlot.Status.AVAILABLE:'可预约',AppointmentSlot.Status.CLOSED:'已关闭'}
        groups={};visible=0;active_states={Appointment.Status.PENDING,Appointment.Status.IN_PROGRESS,Appointment.Status.COMPLETED}
        for schedule in schedules:
            slots=[]
            for slot in sorted(schedule.slots.all(),key=lambda item:(item.start_time,item.pk)):
                appointments=sorted(slot.appointments.all(),key=lambda item:(item.created_at,item.pk))
                active=next((item for item in reversed(appointments) if item.status in active_states),None)
                latest=appointments[-1] if appointments else None
                appointment=None
                if state==AppointmentSlot.Status.AVAILABLE:
                    if active is not None or slot.status!=AppointmentSlot.Status.AVAILABLE:continue
                elif state==AppointmentSlot.Status.CLOSED:
                    if active is not None or slot.status!=AppointmentSlot.Status.CLOSED:continue
                elif state:
                    matching=[item for item in appointments if item.status==state]
                    if not matching:continue
                    appointment=matching[-1]
                else:
                    appointment=active
                    if appointment is None and slot.status!=AppointmentSlot.Status.AVAILABLE:appointment=latest
                appointment_state=appointment.status if appointment else slot.status
                record=None
                if appointment is not None:
                    try:record=appointment.medical_record
                    except MedicalRecord.DoesNotExist:record=None
                slots.append({'id':slot.pk,'start_time':slot.start_time,'end_time':slot.end_time,'slot_status':slot.status,'slot_status_display':slot.get_status_display(),'state':appointment_state,'state_label':status_labels.get(appointment_state,appointment_state),'appointment':None if appointment is None else {'id':appointment.pk,'appointment_no':appointment.appointment_no,'status':appointment.status,'status_display':appointment.get_status_display(),'reason':appointment.reason,'doctor_name':appointment.doctor.user.get_full_name(),'patient':{'id':appointment.patient_id,'patient_no':appointment.patient.patient_no,'full_name':appointment.patient.user.get_full_name(),'phone':appointment.patient.user.phone,'gender_display':appointment.patient.get_gender_display(),'allergies':appointment.patient.allergies},'record':None if record is None else {'id':record.pk,'record_no':record.record_no,'status':record.status,'status_display':record.get_status_display()},'department_id':appointment.department_id or appointment.doctor.department_id,'department_name':(appointment.department or appointment.doctor.department).name}})
            if not slots:continue
            visible+=len(slots)
            doctor=schedule.doctor;group=groups.get(doctor.pk)
            if group is None:group=groups[doctor.pk]={'doctor':DoctorSerializer(doctor,context={'request':request}).data,'schedules':[]};groups[doctor.pk]=group
            group['schedules'].append({'id':schedule.pk,'date':str(schedule.date),'time_range':f'{schedule.start_time:%H:%M}–{schedule.end_time:%H:%M}','slot_minutes':schedule.slot_minutes,'is_active':schedule.is_active,'slots':slots})
        audit(request,'read','outpatient_visits',None,f'查看门诊就诊视图 {start} 至 {end}')
        return Response({'date_from':str(start),'date_to':str(end),'count':total,'page':page,'page_size':size,'slot_count':visible,'results':list(groups.values()),'status_labels':status_labels,'notes':'空号源与预约状态使用同一套颜色键；医师仅能看到本人排班与预约。'})

class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class=AppointmentSerializer;queryset=Appointment.objects.select_related('patient__user','doctor__user','doctor__department','slot__schedule');http_method_names=['get','post','head','options']
    search_fields=('appointment_no','patient__user__first_name','doctor__user__first_name','reason');ordering_fields=('created_at','slot__schedule__date','slot__start_time')
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset();state=self.request.query_params.get('status')
        if user.role==User.Role.PATIENT:qs=qs.filter(patient__user=user)
        elif user.role==User.Role.DOCTOR:qs=qs.filter(doctor__user=user)
        if state:qs=qs.filter(status=state)
        day=parse_date_query(self.request.query_params.get('date'),'date')
        if day:qs=qs.filter(slot__schedule__date=day)
        if self.request.query_params.get('without_record')=='true':qs=qs.filter(medical_record__isnull=True)
        return qs
    def perform_create(self,serializer):
        if self.request.user.role!=User.Role.PATIENT:raise PermissionDenied('只有患者可以预约挂号。')
        obj=serializer.save();audit(self.request,'create','appointment',obj,'患者预约挂号')
    def _transition(self,request,action_name):
        obj=transition_appointment(appointment=self.get_object(),user=request.user,action=action_name);audit(request,action_name,'appointment',obj);return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['post'])
    def cancel(self,request,pk=None):return self._transition(request,'cancel')
    @action(detail=True,methods=['post'])
    def start(self,request,pk=None):return self._transition(request,'start')
    @action(detail=True,methods=['post'])
    def complete(self,request,pk=None):return self._transition(request,'complete')
    @action(detail=True,methods=['post'],url_path='no-show')
    def no_show(self,request,pk=None):return self._transition(request,'no_show')
    @action(detail=True,methods=['get'])
    def workspace(self,request,pk=None):
        appointment=self.get_object();user=request.user
        if user.role==User.Role.PATIENT:raise PermissionDenied('诊疗工作区仅供医务人员使用。')
        if user.role==User.Role.DOCTOR and appointment.doctor.user_id!=user.id:raise PermissionDenied('只能访问本人负责的诊疗工作区。')
        records=MedicalRecord.objects.filter(appointment__patient=appointment.patient).select_related('appointment__doctor__user','appointment__patient__user','appointment__doctor__department','appointment__department','appointment__slot__schedule').prefetch_related('corrections__author').order_by('-appointment__slot__schedule__date')
        current=records.filter(appointment=appointment).first()
        # 工作区只展示该患者已确认的历史病历，避免通过接诊入口读取其他医师的草稿。
        history=records.filter(status=MedicalRecord.Status.CONFIRMED).exclude(appointment=appointment)
        prescriptions=Prescription.objects.filter(record__appointment=appointment).select_related('record__appointment__patient__user','doctor__user').prefetch_related('items__medicine')
        examinations=ExaminationOrder.objects.filter(record__appointment=appointment).select_related('patient__user','doctor__user','record','item').prefetch_related('files')
        admissions=InpatientAdmission.objects.filter(patient=appointment.patient).select_related('patient__user','attending_doctor__user','department','appointment','bed')[:10]
        audit(request,'read','visit_workspace',appointment,f'打开诊疗工作区 {appointment.appointment_no}')
        return Response({'appointment':self.get_serializer(appointment).data,'patient':PatientSerializer(appointment.patient).data,'current_record':MedicalRecordSerializer(current,context={'request':request}).data if current else None,'history':MedicalRecordSerializer(history[:10],many=True,context={'request':request}).data,'history_count':history.count(),'prescriptions':PrescriptionSerializer(prescriptions,many=True,context={'request':request}).data,'examinations':ExaminationSerializer(examinations,many=True,context={'request':request}).data,'admissions':InpatientSerializer(admissions,many=True,context={'request':request}).data})

class MedicalRecordViewSet(viewsets.ModelViewSet):
    serializer_class=MedicalRecordSerializer;queryset=MedicalRecord.objects.select_related('appointment__patient__user','appointment__doctor__user','appointment__slot__schedule').prefetch_related('corrections__author');http_method_names=['get','post','patch','head','options']
    search_fields=('record_no','appointment__patient__user__first_name','diagnosis','chief_complaint');ordering_fields=('created_at','updated_at','confirmed_at')
    def get_queryset(self):
        """医师可读本人病历及被授权患者的已确认病历；草稿仍只属于接诊医师。"""
        user=self.request.user;qs=super().get_queryset()
        if user.role==User.Role.DOCTOR:qs=qs.filter(Q(appointment__doctor__user=user)|Q(appointment__patient__appointments__doctor__user=user,appointment__patient__appointments__status__in=VALID_RELATIONSHIP_STATUSES,status=MedicalRecord.Status.CONFIRMED)).distinct()
        elif user.role==User.Role.PATIENT:qs=qs.filter(appointment__patient__user=user,status=MedicalRecord.Status.CONFIRMED)
        patient=self.request.query_params.get('patient')
        if patient:qs=qs.filter(appointment__patient_id=patient)
        state=self.request.query_params.get('status')
        if state:qs=qs.filter(status=state)
        return qs
    def retrieve(self,request,*args,**kwargs):
        obj=self.get_object();audit(request,'read','medical_record',obj,'读取电子病历');return Response(self.get_serializer(obj).data)
    def perform_create(self,serializer):
        if self.request.user.role!=User.Role.DOCTOR:raise PermissionDenied('仅医师可创建病历。')
        obj=serializer.save();audit(self.request,'create','medical_record',obj,'创建病历草稿')
    def perform_update(self,serializer):
        obj=self.get_object()
        if self.request.user.role!=User.Role.DOCTOR or obj.appointment.doctor.user_id!=self.request.user.id or obj.status!=MedicalRecord.Status.DRAFT:raise PermissionDenied('仅主诊医师可编辑病历草稿。')
        obj=serializer.save();audit(self.request,'update','medical_record',obj,'更新病历草稿')
    @action(detail=True,methods=['post'])
    def confirm(self,request,pk=None):
        obj=self.get_object()
        if request.user.role!=User.Role.DOCTOR or obj.appointment.doctor.user_id!=request.user.id:raise PermissionDenied('仅主诊医师可确认病历。')
        if obj.status!=MedicalRecord.Status.DRAFT:raise APIValidationError('病历已经确认。')
        obj.status=MedicalRecord.Status.CONFIRMED;obj.confirmed_at=timezone.now();obj.save(update_fields=['status','confirmed_at','updated_at']);audit(request,'confirm','medical_record',obj,'确认电子病历')
        return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['post'],url_path='complete-visit')
    def complete_visit(self,request,pk=None):
        obj=self.get_object()
        if request.user.role!=User.Role.DOCTOR or obj.appointment.doctor.user_id!=request.user.id:raise PermissionDenied('仅主诊医师可完成本次诊疗。')
        if obj.status!=MedicalRecord.Status.CONFIRMED:raise APIValidationError('请先确认电子病历。')
        appointment=transition_appointment(appointment=obj.appointment,user=request.user,action='complete');audit(request,'complete','appointment',appointment,'医师完成诊疗')
        return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['post'])
    def corrections(self,request,pk=None):
        obj=self.get_object();content=str(request.data.get('content','')).strip()
        if request.user.role!=User.Role.DOCTOR or obj.appointment.doctor.user_id!=request.user.id:raise PermissionDenied('仅主诊医师可追加更正。')
        if obj.status!=MedicalRecord.Status.CONFIRMED:raise APIValidationError('仅已确认病历可追加更正。')
        if not content:raise APIValidationError({'content':'更正内容不能为空。'})
        correction=MedicalRecordCorrection.objects.create(record=obj,author=request.user,content=content);audit(request,'correct','medical_record',obj,'追加病历更正')
        return Response(CorrectionSerializer(correction).data,status=201)

class MedicineViewSet(viewsets.ModelViewSet):
    serializer_class=MedicineSerializer;queryset=Medicine.objects.all();permission_classes=[IsAdminOrReadOnly];http_method_names=['get','post','patch','head','options']
    search_fields=('name','specification');ordering_fields=('name','stock','price')
    def get_queryset(self):
        qs=super().get_queryset();search=self.request.query_params.get('search','').strip()
        if self.request.query_params.get('available')=='true':qs=qs.filter(is_active=True,stock__gt=0)
        if search:qs=qs.filter(Q(name__icontains=search)|Q(specification__icontains=search))
        return qs
    def perform_create(self,serializer):
        obj=serializer.save();record_stock_movement(medicine=obj,quantity=obj.stock,movement_type=MedicineStockMovement.Type.RECEIPT,operator=self.request.user,note='初始入库');audit(self.request,'create','medicine',obj,'新增药品')
    def perform_update(self,serializer):obj=serializer.save();audit(self.request,'update','medicine',obj,'更新药品')
    @action(detail=True,methods=['post'],url_path='adjust-stock')
    @transaction.atomic
    def adjust_stock(self,request,pk=None):
        if request.user.role!=User.Role.ADMIN:raise PermissionDenied('仅管理员可调整库存。')
        medicine=Medicine.objects.select_for_update().get(pk=self.get_object().pk)
        try:delta=int(request.data.get('delta'))
        except (TypeError,ValueError):raise APIValidationError({'delta':'请输入整数库存变动值。'})
        if medicine.stock+delta<0:raise APIValidationError({'delta':'库存不足，不能执行本次出库。'})
        medicine.stock+=delta;medicine.save(update_fields=['stock','updated_at']);record_stock_movement(medicine=medicine,quantity=delta,movement_type=MedicineStockMovement.Type.ADJUSTMENT,operator=request.user,note=str(request.data.get('note','人工调整'))[:200]);audit(request,'adjust_stock','medicine',medicine,f'库存调整 {delta:+d}')
        return Response(self.get_serializer(medicine).data)

class MedicineStockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes=[IsAdmin];serializer_class=MedicineStockMovementSerializer;queryset=MedicineStockMovement.objects.select_related('medicine','operator','prescription')
    search_fields=('medicine__name','note','prescription__prescription_no');ordering_fields=('created_at',)
    def get_queryset(self):
        qs=super().get_queryset();medicine=self.request.query_params.get('medicine');movement_type=self.request.query_params.get('movement_type');date_from=self.request.query_params.get('date_from');date_to=self.request.query_params.get('date_to')
        if medicine:qs=qs.filter(medicine_id=medicine)
        if movement_type:qs=qs.filter(movement_type=movement_type)
        if date_from:qs=qs.filter(created_at__date__gte=date_from)
        if date_to:qs=qs.filter(created_at__date__lte=date_to)
        return qs

class ExaminationItemViewSet(viewsets.ModelViewSet):
    permission_classes=[IsAdminOrReadOnly];serializer_class=ExaminationItemSerializer;queryset=ExaminationItem.objects.all();http_method_names=['get','post','patch','head','options']
    search_fields=('name','description');ordering_fields=('name','price','category')
    def get_queryset(self):
        qs=super().get_queryset();active=self.request.query_params.get('active')
        if active in {'true','false'}:qs=qs.filter(is_active=active=='true')
        return qs

class WardBedViewSet(viewsets.ModelViewSet):
    permission_classes=[IsAdminWriteOrClinicalRead];serializer_class=WardBedSerializer;queryset=WardBed.objects.select_related('department');http_method_names=['get','post','patch','head','options']
    search_fields=('ward_name','bed_no','department__name');ordering_fields=('ward_name','bed_no','daily_rate')
    def get_queryset(self):
        user=self.request.user
        if user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('仅管理员和医师可以查看床位看板。')
        qs=super().get_queryset();department=self.request.query_params.get('department');available=self.request.query_params.get('available');active=self.request.query_params.get('active');ward=self.request.query_params.get('ward');occupancy=self.request.query_params.get('occupancy')
        if department:qs=qs.filter(department_id=department)
        if ward:qs=qs.filter(ward_name=ward)
        if available=='true':qs=qs.filter(is_active=True,is_occupied=False)
        if active in {'true','false'}:qs=qs.filter(is_active=active=='true')
        if occupancy=='occupied':qs=qs.filter(is_occupied=True)
        elif occupancy=='available':qs=qs.filter(is_occupied=False)
        return qs
    def perform_create(self,serializer):obj=serializer.save();audit(self.request,'create','ward_bed',obj,f'新增床位 {obj}');return obj
    def perform_update(self,serializer):
        bed=self.get_object()
        if bed.is_occupied:
            protected=('department','ward_name','bed_no','is_active')
            if any(field in serializer.validated_data and serializer.validated_data[field]!=getattr(bed,field) for field in protected):
                raise APIValidationError('占用中的床位不能修改科室、病区、床号或停用。')
        obj=serializer.save();audit(self.request,'update','ward_bed',obj,f'更新床位 {obj}');return obj
    @action(detail=True,methods=['get'])
    def occupancy(self,request,pk=None):
        bed=self.get_object()
        if bed.is_occupied:
            admission=bed.admissions.filter(status=InpatientAdmission.Status.ADMITTED).select_related('patient__user','attending_doctor__user','department','bed').order_by('-admitted_at').first()
        else:admission=None
        audit(request,'read','ward_bed',bed,f'查看床位 {bed} 占用详情')
        return Response({'bed':self.get_serializer(bed).data,'occupied':bool(admission),'admission':None if admission is None else BedOccupancySerializer(admission,context={'request':request}).data})
    @action(detail=False,methods=['get'])
    def board(self,request):
        """看板专用接口：一次返回筛选范围内按病区分组的床位、完整选项与准确状态统计，不受分页影响。"""
        user=request.user
        if user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('仅管理员和医师可以查看床位看板。')
        department=self._int_param('department');ward=self.request.query_params.get('ward','').strip() or None
        occupancy=request.query_params.get('occupancy','');active=request.query_params.get('active','')
        filtered=WardBed.objects.select_related('department')
        if department:filtered=filtered.filter(department_id=department)
        if ward:filtered=filtered.filter(ward_name=ward)
        if active in {'true','false'}:filtered=filtered.filter(is_active=active=='true')
        if occupancy=='occupied':filtered=filtered.filter(is_occupied=True)
        elif occupancy=='available':filtered=filtered.filter(is_occupied=False).exclude(is_active=False)
        beds=list(filtered.order_by('department__name','ward_name','bed_no'))
        admissions={}
        occupied_ids=[bed.pk for bed in beds if bed.is_occupied]
        if occupied_ids:
            for admission in InpatientAdmission.objects.filter(bed_id__in=occupied_ids,status=InpatientAdmission.Status.ADMITTED).select_related('patient__user','attending_doctor__user','bed').order_by('admitted_at','pk'):
                admissions[admission.bed_id]=admission
        group_map={};room_map={}
        stats={'total':0,'available':0,'occupied':0,'inactive':0}
        items=[]
        for bed in beds:
            admission=admissions.get(bed.pk)
            status=bed_status_key(bed,admission)
            stats['total']+=1;stats[status]+=1
            detail=board_bed_payload(bed,admission)
            items.append(detail)
            key=(bed.department_id,bed.ward_name)
            group=group_map.get(key)
            if group is None:
                group=group_map[key]={'department_id':bed.department_id,'department_name':bed.department.name,'ward_name':bed.ward_name,'stats':{'total':0,'available':0,'occupied':0,'inactive':0},'beds':[]}
            group['stats']['total']+=1;group['stats'][status]+=1;group['beds'].append(detail)
            room=room_map.get(bed.ward_name)
            if room is None:
                room=room_map[bed.ward_name]={'ward_name':bed.ward_name,'stats':{'total':0,'available':0,'occupied':0,'inactive':0},'beds':[],'_department_ids':set(),'_department_names':set()}
            room['stats']['total']+=1;room['stats'][status]+=1;room['beds'].append(detail);room['_department_ids'].add(bed.department_id);room['_department_names'].add(bed.department.name)
        rooms=[]
        for name in sorted(room_map):
            room=room_map[name];room['department_ids']=sorted(room.pop('_department_ids'));room['department_names']=sorted(room.pop('_department_names'));rooms.append(room)
        all_beds=list(WardBed.objects.select_related('department').order_by('department__name','ward_name','bed_no'))
        department_options=[];ward_options=[];seen_departments=set();seen_wards=set()
        for bed in all_beds:
            if bed.department_id not in seen_departments:
                seen_departments.add(bed.department_id);department_options.append({'id':bed.department_id,'name':bed.department.name,'bed_count':0})
            if bed.ward_name not in seen_wards:
                seen_wards.add(bed.ward_name);ward_options.append({'name':bed.ward_name,'department_id':bed.department_id})
        counts={option['id']:0 for option in department_options}
        for bed in all_beds:counts[bed.department_id]=counts.get(bed.department_id,0)+1
        for option in department_options:option['bed_count']=counts.get(option['id'],0)
        global_stats={'total':0,'available':0,'occupied':0,'inactive':0}
        for bed in all_beds:
            admission=admissions.get(bed.pk)
            global_stats[bed_status_key(bed,admission)]+=1;global_stats['total']+=1
        audit(request,'read','ward_bed_board',None,f'查看床位看板（{stats["total"]} 张，全部 {global_stats["total"]} 张）')
        wards=[group_map[key] for key in sorted(group_map,key=lambda key:(group_map[key]['department_name'],key[1]))]
        department_map={}
        for group in wards:
            department=department_map.get(group['department_id'])
            if department is None:
                department=department_map[group['department_id']]={'department_id':group['department_id'],'department_name':group['department_name'],'stats':{'total':0,'available':0,'occupied':0,'inactive':0},'wards':[]}
            for status in ('total','available','occupied','inactive'):department['stats'][status]+=group['stats'][status]
            department['wards'].append({'ward_name':group['ward_name'],'stats':group['stats'],'beds':group['beds']})
        departments=[department_map[key] for key in sorted(department_map,key=lambda key:department_map[key]['department_name'])]
        return Response({'filters':{'department':department,'ward':ward,'occupancy':occupancy or None,'active':active or None},'total':stats['total'],'stats':stats,'ward_stats':[{'ward_name':group['ward_name'],'department_id':group['department_id'],'total':group['stats']['total'],'occupied':group['stats']['occupied'],'available':group['stats']['available'],'inactive':group['stats']['inactive']} for group in wards],'options':{'departments':department_options,'wards':ward_options},'global_stats':global_stats,'groups':wards,'departments':departments,'rooms':rooms,'beds':items})
    def _int_param(self,name):
        value=self.request.query_params.get(name)
        if not value:return None
        try:return int(value)
        except (TypeError,ValueError):raise APIValidationError({name:'参数必须为整数。'})

class PrescriptionViewSet(viewsets.ModelViewSet):
    serializer_class=PrescriptionSerializer;queryset=Prescription.objects.select_related('record__appointment__patient__user','doctor__user','billing_record__inpatient_admission').prefetch_related('items__medicine');http_method_names=['get','post','head','options']
    search_fields=('prescription_no','record__appointment__patient__user__first_name','record__diagnosis');ordering_fields=('created_at',)
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset()
        if user.role==User.Role.DOCTOR:qs=qs.filter(Q(doctor__user=user)|Q(record__appointment__patient__appointments__doctor__user=user,record__appointment__patient__appointments__status__in=VALID_RELATIONSHIP_STATUSES)).distinct()
        elif user.role==User.Role.PATIENT:qs=qs.filter(record__appointment__patient__user=user)
        patient=self.request.query_params.get('patient')
        if patient:qs=qs.filter(record__appointment__patient_id=patient)
        state=self.request.query_params.get('status')
        if state:qs=qs.filter(status=state)
        return qs
    def perform_create(self,serializer):
        if self.request.user.role!=User.Role.DOCTOR:raise PermissionDenied('仅医师可开具处方。')
        obj=serializer.save();audit(self.request,'create','prescription',obj,'开具电子处方')
    @action(detail=True,methods=['post'])
    @transaction.atomic
    def cancel(self,request,pk=None):
        obj=self.get_object()
        if request.user.role!=User.Role.DOCTOR or obj.doctor.user_id!=request.user.id:raise PermissionDenied('只能作废本人开具的处方。')
        if obj.status!=Prescription.Status.ISSUED:raise APIValidationError('只有待缴费取药的处方可以作废。')
        obj.status=Prescription.Status.CANCELLED;obj.save(update_fields=['status','updated_at'])
        try:
            bill=obj.billing_record
            if bill.status==BillingRecord.Status.UNPAID:bill.status=BillingRecord.Status.CANCELLED;bill.save(update_fields=['status','updated_at'])
        except BillingRecord.DoesNotExist:pass
        audit(request,'cancel','prescription',obj);return Response(self.get_serializer(obj).data)

class ExaminationViewSet(viewsets.ModelViewSet):
    serializer_class=ExaminationSerializer;queryset=ExaminationOrder.objects.select_related('patient__user','doctor__user','record','billing_record__inpatient_admission').prefetch_related('files');http_method_names=['get','post','head','options']
    search_fields=('order_no','patient__user__first_name','doctor__user__first_name','clinical_question');ordering_fields=('created_at','completed_at')
    def get_queryset(self):
        """检查列表按业务关系收口：医师仅本人或被授权患者的检查，患者仅本人已发布报告。"""
        user=self.request.user;qs=super().get_queryset()
        if user.role==User.Role.PATIENT:qs=qs.filter(patient__user=user,status=ExaminationOrder.Status.PUBLISHED)
        elif user.role==User.Role.DOCTOR:qs=qs.filter(Q(doctor__user=user)|Q(patient__appointments__doctor__user=user,patient__appointments__status__in=VALID_RELATIONSHIP_STATUSES)).distinct()
        patient=self.request.query_params.get('patient')
        if patient:qs=qs.filter(patient_id=patient)
        state=self.request.query_params.get('status')
        if state:qs=qs.filter(status=state)
        date_from=parse_date_query(self.request.query_params.get('date_from'),'date_from');date_to=parse_date_query(self.request.query_params.get('date_to'),'date_to')
        if date_from:qs=qs.filter(created_at__date__gte=date_from)
        if date_to:qs=qs.filter(created_at__date__lte=date_to)
        return qs
    def retrieve(self,request,*args,**kwargs):
        obj=self.get_object();audit(request,'read','examination',obj,'读取检查详情');return Response(self.get_serializer(obj).data)
    def perform_create(self,serializer):
        if self.request.user.role!=User.Role.DOCTOR:raise PermissionDenied('仅医师可申请检查。')
        obj=serializer.save();audit(self.request,'create','examination',obj,'创建检查申请')
    @action(detail=True,methods=['post'])
    @transaction.atomic
    def cancel(self,request,pk=None):
        order=self.get_object()
        if request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权取消检查。')
        if order.status not in {ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS}:raise APIValidationError('当前检查不可取消。')
        order.status=ExaminationOrder.Status.CANCELLED;order.save(update_fields=['status','updated_at'])
        try:
            bill=order.billing_record
            if bill.status==BillingRecord.Status.UNPAID:bill.status=BillingRecord.Status.CANCELLED;bill.save(update_fields=['status','updated_at'])
        except BillingRecord.DoesNotExist:pass
        audit(request,'cancel','examination',order,'取消检查申请');return Response(self.get_serializer(order).data)
    def ensure_report_manager(self,request,order):
        if request.user.role==User.Role.ADMIN:return
        if request.user.role==User.Role.DOCTOR:return
        raise PermissionDenied('仅医师或管理员可处理检查报告。')
    @action(detail=True,methods=['post'])
    def start(self,request,pk=None):
        order=self.get_object();self.ensure_report_manager(request,order)
        if order.status!=ExaminationOrder.Status.REQUESTED:raise APIValidationError('仅已申请的检查可以开始处理。')
        order.status=ExaminationOrder.Status.IN_PROGRESS;order.save(update_fields=['status','updated_at']);audit(request,'start','examination',order,'开始处理检查申请')
        return Response(self.get_serializer(order).data)
    @action(detail=True,methods=['post'])
    @transaction.atomic
    def report(self,request,pk=None):
        order=self.get_object();self.ensure_report_manager(request,order)
        if order.status in {ExaminationOrder.Status.PUBLISHED,ExaminationOrder.Status.CANCELLED}:raise APIValidationError('已发布或已取消的检查不能修改报告。')
        existing=getattr(order,'report',None)
        if existing and existing.status==ExaminationReport.Status.PUBLISHED:raise APIValidationError('已发布的检查报告不能修改。')
        serializer=ReportSerializer(existing,data=request.data)
        serializer.is_valid(raise_exception=True);report=serializer.save(order=order);order.status=ExaminationOrder.Status.COMPLETED;order.completed_at=timezone.now();order.save(update_fields=['status','completed_at','updated_at']);audit(request,'update','examination_report',report,'录入检查报告')
        return Response(ReportSerializer(report).data)
    @action(detail=True,methods=['post'])
    @transaction.atomic
    def publish(self,request,pk=None):
        order=self.get_object();self.ensure_report_manager(request,order)
        if order.status!=ExaminationOrder.Status.COMPLETED:raise APIValidationError('仅已完成报告的检查可以发布。')
        if not hasattr(order,'report'):raise APIValidationError('请先录入检查报告。')
        report=order.report;report.status=ExaminationReport.Status.PUBLISHED;report.published_by=request.user;report.published_at=timezone.now();report.save(update_fields=['status','published_by','published_at','updated_at'])
        order.status=ExaminationOrder.Status.PUBLISHED;order.save(update_fields=['status','updated_at']);audit(request,'publish','examination_report',report,'发布检查报告');return Response(self.get_serializer(order).data)
    @action(detail=True,methods=['post'])
    def upload(self,request,pk=None):
        order=self.get_object()
        if request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权上传医疗文件。')
        if order.status in {ExaminationOrder.Status.PUBLISHED,ExaminationOrder.Status.CANCELLED}:raise APIValidationError('已发布或已取消的检查不能上传附件。')
        uploaded=request.FILES.get('file')
        if not uploaded:raise APIValidationError({'file':'请选择文件。'})
        if uploaded.size>10*1024*1024:raise APIValidationError({'file':'文件不能超过 10MB。'})
        suffix=uploaded.name.lower().rsplit('.',1)[-1]
        if suffix not in {'jpg','jpeg','png','pdf','dcm','nii','gz'}:raise APIValidationError({'file':'不支持的文件格式。'})
        item=MedicalFile.objects.create(order=order,file=uploaded,original_name=uploaded.name,file_type=suffix,size=uploaded.size,uploaded_by=request.user);audit(request,'upload','medical_file',item,'上传检查资料')
        return Response(MedicalFileSerializer(item,context={'request':request}).data,status=201)

@api_view(['GET'])
def medical_file_download(request,pk):
    item=get_object_or_404(MedicalFile.objects.select_related('order__patient__user','order__doctor__user'),pk=pk);user=request.user
    doctor_allowed=user.role==User.Role.DOCTOR and (item.order.doctor.user_id==user.id or has_doctor_patient_relationship(user=user,patient_id=item.order.patient_id))
    allowed=user.role==User.Role.ADMIN or doctor_allowed or (user.role==User.Role.PATIENT and item.order.patient.user_id==user.id and item.order.status==ExaminationOrder.Status.PUBLISHED)
    if not allowed:raise PermissionDenied('无权访问该医疗文件。')
    try:handle=item.file.open('rb')
    except (FileNotFoundError,OSError):raise Http404('文件不存在。')
    audit(request,'download','medical_file',item,'下载医疗文件');return FileResponse(handle,content_type=mimetypes.guess_type(item.original_name)[0] or 'application/octet-stream',as_attachment=True,filename=item.original_name)

class BillingViewSet(viewsets.ModelViewSet):
    serializer_class=BillingSerializer;queryset=BillingRecord.objects.select_related('patient__user','appointment__doctor__user','prescription','examination','inpatient_admission__department');http_method_names=['get','post','patch','head','options']
    search_fields=('bill_no','patient__user__first_name','description');ordering_fields=('created_at','amount')
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset();state=self.request.query_params.get('status');admission=self.request.query_params.get('admission')
        if user.role==User.Role.PATIENT:qs=qs.filter(patient__user=user)
        elif user.role==User.Role.DOCTOR:qs=qs.filter(Q(patient__admissions__attending_doctor__user=user)|Q(appointment__doctor__user=user)).distinct()
        if state:qs=qs.filter(status=state)
        if admission:qs=qs.filter(inpatient_admission_id=admission)
        return qs
    @action(detail=False,methods=['get'],url_path='examination-costs')
    def examination_costs(self,request):
        """患者检查费用周期统计：日期区间、每日趋势、按项目汇总与分页明细。"""
        user=request.user
        if user.role==User.Role.PATIENT:
            requested=request.query_params.get('patient') or request.query_params.get('patient_id')
            patient=request.user.patient_profile
            if requested not in (None,'') and str(requested)!=str(patient.pk):raise PermissionDenied('不能查询其他患者的检查费用。')
        elif user.role==User.Role.ADMIN:
            patient_id=request.query_params.get('patient') or request.query_params.get('patient_id')
            if not patient_id:raise APIValidationError({'patient':'管理员查询检查费用时必须选择患者。'})
            patient=get_object_or_404(PatientProfile.objects.select_related('user'),pk=patient_id)
        else:raise PermissionDenied('检查费用统计仅对患者本人和管理员开放。')
        today=timezone.localdate();start=parse_date_query(request.query_params.get('date_from'),'date_from',today-timedelta(days=29));end=parse_date_query(request.query_params.get('date_to'),'date_to',today)
        if start>end:raise APIValidationError({'date_to':'结束日期不能早于开始日期。'})
        if (end-start).days>366:raise APIValidationError({'date_to':'查询区间不能超过 367 天。'})
        base=BillingRecord.objects.select_related('examination','patient__user').filter(patient=patient,category=BillingRecord.Category.EXAMINATION,examination__isnull=False,created_at__date__range=(start,end))
        active=base.exclude(status=BillingRecord.Status.CANCELLED)
        totals=active.aggregate(billed=Sum('amount'))
        paid=active.filter(status=BillingRecord.Status.PAID).aggregate(value=Sum('amount'))['value'] or Decimal('0')
        unpaid=active.filter(status=BillingRecord.Status.UNPAID).aggregate(value=Sum('amount'))['value'] or Decimal('0')
        cancelled=base.filter(status=BillingRecord.Status.CANCELLED).aggregate(value=Sum('amount'))['value'] or Decimal('0')
        summary={'total_amount':money(totals['billed']),'paid_amount':money(paid),'unpaid_amount':money(unpaid),'cancelled_amount':money(cancelled),'bill_count':active.count(),'cancelled_count':base.filter(status=BillingRecord.Status.CANCELLED).count()}
        daily={}
        for row in active.values('created_at__date').annotate(total=Sum('amount'),paid=Sum('amount',filter=Q(status=BillingRecord.Status.PAID)),unpaid=Sum('amount',filter=Q(status=BillingRecord.Status.UNPAID))):
            daily[row['created_at__date']]=row
        trend=[];cursor=start
        while cursor<=end:
            row=daily.get(cursor)
            trend.append({'date':str(cursor),'total':money(row['total'] if row else 0),'paid':money(row['paid'] if row else 0),'unpaid':money(row['unpaid'] if row else 0)})
            cursor+=timedelta(days=1)
        item_rows=[]
        for row in active.values('examination__item_name_snapshot','examination__item__name','examination__type').annotate(total=Sum('amount'),count=Count('id')):
            label=row['examination__item_name_snapshot'] or row['examination__item__name'] or '其他检查'
            entry=next((item for item in item_rows if item['item_name']==label),None)
            if entry is None:item_rows.append({'item_name':label,'type':row['examination__type'],'type_display':dict(ExaminationOrder.Type.choices).get(row['examination__type'],row['examination__type']),'total_amount':money(row['total']),'bill_count':row['count']})
            else:entry['total_amount']=money(Decimal(entry['total_amount'])+Decimal(row['total']));entry['bill_count']+=row['count']
        item_rows.sort(key=lambda item:Decimal(item['total_amount']),reverse=True)
        page,size=page_meta(request);total=base.count();offset=(page-1)*size;rows=list(base.order_by('-created_at','-pk')[offset:offset+size])
        audit(request,'read','examination_costs',patient,f'查看检查费用 {start} 至 {end}')
        return Response({'patient':{'id':patient.pk,'patient_no':patient.patient_no,'full_name':patient.user.get_full_name()},'date_from':str(start),'date_to':str(end),'date_basis':'按账单创建日期（费用发生日期）统计，起止日均包含；金额使用账单金额快照。','summary':summary,'trend':trend,'by_item':item_rows,'count':total,'page':page,'page_size':size,'results':BillingSerializer(rows,many=True,context={'request':request}).data,'max_range_days':367})
    @action(detail=False,methods=['get'],url_path='medicine-costs')
    def medicine_costs(self,request):
        """患者药品费用周期统计：覆盖处方账单与手工药品账单，按药品/历史处方/手工费用汇总。"""
        user=request.user
        if user.role==User.Role.PATIENT:
            requested=request.query_params.get('patient') or request.query_params.get('patient_id')
            patient=request.user.patient_profile
            if requested not in (None,'') and str(requested)!=str(patient.pk):raise PermissionDenied('不能查询其他患者的药品费用。')
        elif user.role==User.Role.ADMIN:
            patient_id=request.query_params.get('patient') or request.query_params.get('patient_id')
            if not patient_id:raise APIValidationError({'patient':'管理员查询药品费用时必须选择患者。'})
            patient=get_object_or_404(PatientProfile.objects.select_related('user'),pk=patient_id)
        else:raise PermissionDenied('药品费用统计仅对患者本人和管理员开放。')
        today=timezone.localdate();start=parse_date_query(request.query_params.get('date_from'),'date_from',today-timedelta(days=29));end=parse_date_query(request.query_params.get('date_to'),'date_to',today)
        if start>end:raise APIValidationError({'date_to':'结束日期不能早于开始日期。'})
        if (end-start).days>366:raise APIValidationError({'date_to':'查询区间不能超过 367 天。'})
        base=BillingRecord.objects.select_related('prescription','patient__user').prefetch_related('prescription__items__medicine').filter(patient=patient,category=BillingRecord.Category.MEDICINE,created_at__date__range=(start,end))
        active=base.exclude(status=BillingRecord.Status.CANCELLED)
        totals=active.aggregate(billed=Sum('amount'))
        paid=active.filter(status=BillingRecord.Status.PAID).aggregate(value=Sum('amount'))['value'] or Decimal('0')
        unpaid=active.filter(status=BillingRecord.Status.UNPAID).aggregate(value=Sum('amount'))['value'] or Decimal('0')
        cancelled=base.filter(status=BillingRecord.Status.CANCELLED).aggregate(value=Sum('amount'))['value'] or Decimal('0')
        summary={'total_amount':money(totals['billed']),'paid_amount':money(paid),'unpaid_amount':money(unpaid),'cancelled_amount':money(cancelled),'bill_count':active.count(),'cancelled_count':base.filter(status=BillingRecord.Status.CANCELLED).count()}
        daily={}
        for row in active.values('created_at__date').annotate(total=Sum('amount'),paid=Sum('amount',filter=Q(status=BillingRecord.Status.PAID)),unpaid=Sum('amount',filter=Q(status=BillingRecord.Status.UNPAID))):
            daily[row['created_at__date']]=row
        trend=[];cursor=start
        while cursor<=end:
            row=daily.get(cursor)
            trend.append({'date':str(cursor),'total':money(row['total'] if row else 0),'paid':money(row['paid'] if row else 0),'unpaid':money(row['unpaid'] if row else 0)})
            cursor+=timedelta(days=1)
        # 药品汇总：处方按明细快照药品分摊；历史无快照处方使用原账单总额；手工账单统一归入“手工药品费用”。
        buckets={}
        def add_bucket(label,amount,quantity,bill_id):
            entry=buckets.get(label)
            if entry is None:
                entry=buckets[label]={'medicine_name':label,'total':Decimal('0'),'quantity':0,'bill_ids':set()}
                buckets[label]=entry
            entry['total']+=Decimal(amount);entry['quantity']+=int(quantity or 0);entry['bill_ids'].add(bill_id)
        rendered=BillingSerializer(list(active.order_by('created_at','pk')),many=True,context={'request':request}).data
        for row in rendered:
            details=row.get('charge_details') or []
            if row.get('prescription_id'):
                if not details or any(not line.get('price_snapshot') for line in details):
                    add_bucket('历史处方明细',row['amount'],sum(int(line.get('quantity') or 0) for line in details) or 1,row['id'])
                else:
                    for line in details:add_bucket(line.get('medicine_name') or '药品明细',line.get('amount') or 0,line.get('quantity') or 0,row['id'])
            else:add_bucket('手工药品费用',row['amount'],1,row['id'])
        medicine_rows=[{'medicine_name':entry['medicine_name'],'total_amount':money(entry['total']),'quantity':entry['quantity'],'bill_count':len(entry['bill_ids'])} for entry in buckets.values()]
        medicine_rows.sort(key=lambda item:Decimal(item['total_amount']),reverse=True)
        page,size=page_meta(request);total=base.count();offset=(page-1)*size;rows=list(base.order_by('-created_at','-pk')[offset:offset+size])
        audit(request,'read','medicine_costs',patient,f'查看药品费用 {start} 至 {end}')
        return Response({'patient':{'id':patient.pk,'patient_no':patient.patient_no,'full_name':patient.user.get_full_name()},'date_from':str(start),'date_to':str(end),'date_basis':'按账单创建日期（费用发生日期）统计，起止日均包含；处方药品按明细快照汇总，历史处方使用原账单总额，手工账单归入手工药品费用。','summary':summary,'trend':trend,'by_medicine':medicine_rows,'count':total,'page':page,'page_size':size,'results':BillingSerializer(rows,many=True,context={'request':request}).data,'max_range_days':367})
    def perform_create(self,serializer):
        if self.request.user.role!=User.Role.ADMIN:raise PermissionDenied('仅管理员可创建费用账单。')
        obj=serializer.save();audit(self.request,'create','billing',obj,'创建费用账单')
    def perform_update(self,serializer):
        if self.request.user.role!=User.Role.ADMIN:raise PermissionDenied('仅管理员可修改费用账单。')
        if self.get_object().status!=BillingRecord.Status.UNPAID:raise APIValidationError('仅待缴费账单可以修改。')
        obj=serializer.save();audit(self.request,'update','billing',obj,'更新费用账单')
    @action(detail=True,methods=['post'])
    @transaction.atomic
    def pay(self,request,pk=None):
        bill=BillingRecord.objects.select_for_update().select_related('patient__user','prescription').get(pk=self.get_object().pk)
        if bill.status!=BillingRecord.Status.UNPAID:raise APIValidationError('当前账单不可缴费。')
        if request.user.role==User.Role.PATIENT and bill.patient.user_id!=request.user.id:raise PermissionDenied('只能支付本人的账单。')
        if request.user.role not in {User.Role.ADMIN,User.Role.PATIENT}:raise PermissionDenied('无权执行缴费。')
        if bill.prescription_id:
            prescription=Prescription.objects.select_for_update().get(pk=bill.prescription_id)
            if prescription.status!=Prescription.Status.ISSUED:raise APIValidationError('关联处方当前不可发药。')
            items=list(PrescriptionItem.objects.filter(prescription=prescription).select_related('medicine'))
            medicines={item.pk:item for item in Medicine.objects.select_for_update().filter(pk__in=[line.medicine_id for line in items])}
            shortages=[]
            for line in items:
                medicine=medicines[line.medicine_id]
                if not medicine.is_active or medicine.stock<line.quantity:shortages.append(f'{medicine.name}（库存 {medicine.stock}，需要 {line.quantity}）')
            if shortages:raise APIValidationError({'stock':'库存不足：'+'；'.join(shortages)})
            for line in items:
                medicine=medicines[line.medicine_id];medicine.stock-=line.quantity;medicine.save(update_fields=['stock','updated_at']);record_stock_movement(medicine=medicine,quantity=-line.quantity,movement_type=MedicineStockMovement.Type.DISPENSE,operator=request.user,prescription=prescription,note='支付后自动发药')
            prescription.status=Prescription.Status.DISPENSED;prescription.dispensed_at=timezone.now();prescription.save(update_fields=['status','dispensed_at','updated_at']);audit(request,'dispense','prescription',prescription,'支付完成并自动发药')
        bill.status=BillingRecord.Status.PAID;bill.payment_method=str(request.data.get('payment_method','演示支付'))[:30];bill.paid_at=timezone.now();bill.save(update_fields=['status','payment_method','paid_at','updated_at']);audit(request,'pay','billing',bill,'完成费用结算')
        return Response(self.get_serializer(bill).data)
    @action(detail=True,methods=['post'])
    def cancel(self,request,pk=None):
        if request.user.role!=User.Role.ADMIN:raise PermissionDenied('仅管理员可取消账单。')
        bill=self.get_object()
        if bill.status!=BillingRecord.Status.UNPAID:raise APIValidationError('仅待缴费账单可以取消。')
        bill.status=BillingRecord.Status.CANCELLED;bill.save(update_fields=['status','updated_at']);audit(request,'cancel','billing',bill,'取消费用账单');return Response(self.get_serializer(bill).data)

def admission_charge_payload(admission,date_from=None,date_to=None):
    """住院费用清单：逐项费用与真实明细行、费用合计、已付/待付与住院中预计床位费。取消的账单单独列出且不计入合计。"""
    def parse(value):
        if not value:return None
        try:return date_cls.fromisoformat(str(value))
        except ValueError:raise APIValidationError({'date':'日期格式应为 YYYY-MM-DD。'})
    start=parse(date_from);end=parse(date_to)
    bills=list(BillingRecord.objects.filter(inpatient_admission=admission).select_related('prescription','examination','patient__user').order_by('created_at','id'))
    serializer=BillingSerializer(bills,many=True)
    items=[]
    for rendered in serializer.data:
        row=dict(rendered)
        charge_date=date_cls.fromisoformat(row['charge_date']) if row['charge_date'] else None
        if charge_date and start and charge_date<start:continue
        if charge_date and end and charge_date>end:continue
        details=[dict(line) for line in (row.get('charge_details') or [])]
        for line in details:
            if line.get('amount') is None:line['amount']=row['amount']
        details_total=sum((Decimal(line['amount']) for line in details),Decimal('0'))
        row['charge_details']=details
        row['details_total']=str(details_total.quantize(Decimal('0.01')))
        row['details_consistent']=bool(details) and details_total==Decimal(row['amount'])
        items.append(row)
    billable=[row for row in items if row['status']!=BillingRecord.Status.CANCELLED]
    def money(value):return str(Decimal(value).quantize(Decimal('0.01')))
    totals={}
    for row in billable:totals[row['category']]=totals.get(row['category'],Decimal('0'))+Decimal(row['amount'])
    paid=sum((Decimal(row['amount']) for row in billable if row['status']==BillingRecord.Status.PAID),Decimal('0'))
    unpaid=sum((Decimal(row['amount']) for row in billable if row['status']==BillingRecord.Status.UNPAID),Decimal('0'))
    cancelled=sum((Decimal(row['amount']) for row in items if row['status']==BillingRecord.Status.CANCELLED),Decimal('0'))
    projected=admission.projected_bed_fee if admission.status==InpatientAdmission.Status.ADMITTED else Decimal('0')
    order={value:index for index,value in enumerate(BillingRecord.Category.values)}
    categories=[{'category':key,'label':dict(BillingRecord.Category.choices).get(key,key),'total':money(value)} for key,value in sorted(totals.items(),key=lambda row:order.get(row[0],99))]
    detail_lines=sum(len(row['charge_details']) for row in billable)
    summary={'billed_amount':money(paid+unpaid),'paid_amount':money(paid),'unpaid_amount':money(unpaid),'cancelled_amount':money(cancelled),'projected_bed_fee':money(projected),'estimated_total':money(paid+unpaid+projected),'bill_count':len(billable),'cancelled_count':len(items)-len(billable),'detail_line_count':detail_lines,'bed_daily_rate':money(admission.daily_rate_snapshot),'days_admitted':admission.days_admitted,'billable_days':admission.billable_days,'bed_bill_generated':BillingRecord.objects.filter(admission=admission).exists(),'categories':categories}
    return {'admission':InpatientChargeSummarySerializer(admission,context={'charge_totals':totals}).data,'items':items,'summary':summary,'bed_fee_rule':'住院中床位费按本地日期逐日预估（至少一天），出院时固定为唯一床位费账单；费用发生日期为账单创建日期。'}

class InpatientViewSet(viewsets.ModelViewSet):
    serializer_class=InpatientSerializer;queryset=InpatientAdmission.objects.select_related('patient__user','attending_doctor__user','department','appointment','bed');http_method_names=['get','post','patch','head','options']
    search_fields=('admission_no','patient__user__first_name','ward','bed_no','admission_diagnosis');ordering_fields=('created_at','admitted_at','discharged_at')
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset();state=self.request.query_params.get('status');department=self.request.query_params.get('department');bed=self.request.query_params.get('bed');patient=self.request.query_params.get('patient')
        if user.role==User.Role.PATIENT:qs=qs.filter(patient__user=user)
        if state:qs=qs.filter(status=state)
        if department:qs=qs.filter(department_id=department)
        if bed:qs=qs.filter(bed_id=bed)
        if patient:qs=qs.filter(patient_id=patient)
        return qs.order_by('-created_at')
    def retrieve(self,request,*args,**kwargs):
        obj=self.get_object();audit(request,'read','inpatient',obj,f'查看住院详情 {obj.admission_no}');return Response(self.get_serializer(obj).data)
    def perform_create(self,serializer):
        if self.request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权创建住院记录。')
        obj=serializer.save();audit(self.request,'create','inpatient',obj,'创建住院申请')
    def perform_update(self,serializer):
        if self.request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权修改住院记录。')
        if self.get_object().status in {InpatientAdmission.Status.DISCHARGED,InpatientAdmission.Status.CANCELLED}:raise APIValidationError('已结束的住院记录不可修改。')
        obj=serializer.save();audit(self.request,'update','inpatient',obj,'更新住院记录')
    @action(detail=True,methods=['get'])
    def charges(self,request,pk=None):
        admission=self.get_object()
        audit(request,'read','inpatient_charges',admission,f'查看住院费用清单 {admission.admission_no}')
        payload=admission_charge_payload(admission,date_from=request.query_params.get('date_from'),date_to=request.query_params.get('date_to'))
        payload['role']=request.user.role
        return Response(payload)
    @action(detail=True,methods=['post'])
    def admit(self,request,pk=None):
        if request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权办理入院。')
        admission=self.get_object();ensure_admission_operator(admission=admission,user=request.user)
        obj=admit_patient(admission=admission);audit(request,'admit','inpatient',obj,'办理入院');return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['post'])
    def discharge(self,request,pk=None):
        if request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权办理出院。')
        admission=self.get_object();ensure_admission_operator(admission=admission,user=request.user)
        obj=finish_admission(admission=admission,summary=str(request.data.get('discharge_summary','')));audit(request,'discharge','inpatient',obj,'办理出院并生成费用');return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['post'])
    def cancel(self,request,pk=None):
        if request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权取消住院。')
        admission=self.get_object();ensure_admission_operator(admission=admission,user=request.user)
        obj=finish_admission(admission=admission,cancel=True);audit(request,'cancel','inpatient',obj,'取消住院并释放床位');return Response(self.get_serializer(obj).data)

class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes=[IsAdmin];serializer_class=AuditSerializer;queryset=AuditLog.objects.select_related('user')
    search_fields=('user__username','user__first_name','action','resource','description');ordering_fields=('created_at',)
    def get_queryset(self):
        qs=super().get_queryset();action_name=self.request.query_params.get('action');resource=self.request.query_params.get('resource');user_id=self.request.query_params.get('user');date_from=self.request.query_params.get('date_from');date_to=self.request.query_params.get('date_to')
        if action_name:qs=qs.filter(action=action_name)
        if resource:qs=qs.filter(resource=resource)
        if user_id:qs=qs.filter(user_id=user_id)
        if date_from:qs=qs.filter(created_at__date__gte=date_from)
        if date_to:qs=qs.filter(created_at__date__lte=date_to)
        return qs

@api_view(['GET'])
def statistics_overview(request):
    user=request.user;today=timezone.localdate()
    if user.role==User.Role.ADMIN:
        paid_total=BillingRecord.objects.filter(status=BillingRecord.Status.PAID).aggregate(total=Sum('amount'))['total'] or 0
        cards=[['医师总数',DoctorProfile.objects.filter(user__is_active=True).count()],['注册患者',PatientProfile.objects.filter(user__is_active=True).count()],['今日预约',Appointment.objects.filter(slot__schedule__date=today).count()],['今日接诊',Appointment.objects.filter(slot__schedule__date=today,status=Appointment.Status.COMPLETED).count()],['当前住院',InpatientAdmission.objects.filter(status=InpatientAdmission.Status.ADMITTED).count()],['累计结算',f'¥{paid_total:.2f}']]
        base=Appointment.objects.all()
    elif user.role==User.Role.DOCTOR:
        qs=Appointment.objects.filter(doctor__user=user,slot__schedule__date=today);cards=[['今日预约',qs.count()],['待接诊',qs.filter(status=Appointment.Status.PENDING).count()],['诊疗中',qs.filter(status=Appointment.Status.IN_PROGRESS).count()],['已完成',qs.filter(status=Appointment.Status.COMPLETED).count()],['全院待检查',ExaminationOrder.objects.filter(status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS]).count()],['住院患者',InpatientAdmission.objects.filter(status=InpatientAdmission.Status.ADMITTED).count()]]
        base=Appointment.objects.filter(doctor__user=user)
    else:
        qs=Appointment.objects.filter(patient__user=user);cards=[['近期预约',qs.filter(status=Appointment.Status.PENDING).count()],['历史就诊',qs.filter(status=Appointment.Status.COMPLETED).count()],['待出报告',ExaminationOrder.objects.filter(patient__user=user,status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS,ExaminationOrder.Status.COMPLETED]).count()],['有效处方',Prescription.objects.filter(record__appointment__patient__user=user,status=Prescription.Status.ISSUED).count()]]
        base=qs
    dates=[today-timedelta(days=offset) for offset in range(6,-1,-1)]
    counted={row['slot__schedule__date']:row['value'] for row in base.filter(slot__schedule__date__range=(dates[0],today)).values('slot__schedule__date').annotate(value=Count('id'))}
    recent=base.select_related('patient__user','doctor__user','slot__schedule').order_by('-created_at')[:6]
    payload={'cards':cards,'trend':[{'date':str(day),'value':counted.get(day,0)} for day in dates],'appointment_status':[{'status':label,'value':base.filter(status=value).count()} for value,label in Appointment.Status.choices],'recent_appointments':[{'id':item.id,'appointment_no':item.appointment_no,'patient_name':item.patient.user.get_full_name(),'doctor_name':item.doctor.user.get_full_name(),'date':str(item.slot.schedule.date),'time':item.slot.start_time.strftime('%H:%M'),'status':item.get_status_display()} for item in recent]}
    if user.role==User.Role.ADMIN:
        payload['department_distribution']=list(base.values(name=F('doctor__department__name')).annotate(value=Count('id')).order_by('-value')[:10])
        payload['doctor_workload']=list(Appointment.objects.filter(status=Appointment.Status.COMPLETED).values(name=F('doctor__user__first_name')).annotate(value=Count('id')).order_by('-value')[:10])
        payload['billing_distribution']=list(BillingRecord.objects.values(name=F('category')).annotate(value=Sum('amount')).order_by('-value'))
        payload['operation_summary']={'pending_appointments':Appointment.objects.filter(status=Appointment.Status.PENDING).count(),'pending_examinations':ExaminationOrder.objects.filter(status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS]).count(),'unpaid_bills':BillingRecord.objects.filter(status=BillingRecord.Status.UNPAID).count(),'low_stock':Medicine.objects.filter(is_active=True,stock__lte=10).count()}
    return Response(payload)

def _change(current,previous):
    if not previous:return None if not current else 100
    return round((float(current)-float(previous))*100/float(previous),1)

@api_view(['GET'])
def statistics_dashboard(request):
    user=request.user;range_key=request.query_params.get('range','30d');range_days={'7d':7,'30d':30,'90d':90}
    if range_key not in range_days:raise APIValidationError({'range':'仅支持 7d、30d 或 90d。'})
    days=range_days[range_key];today=timezone.localdate();start=today-timedelta(days=days-1);previous_end=start-timedelta(days=1);previous_start=previous_end-timedelta(days=days-1)
    appointments=Appointment.objects.select_related('patient__user','doctor__user','doctor__department','slot__schedule')
    if user.role==User.Role.DOCTOR:appointments=appointments.filter(doctor__user=user)
    elif user.role==User.Role.PATIENT:appointments=appointments.filter(patient__user=user)
    current=appointments.filter(slot__schedule__date__range=(start,today));previous=appointments.filter(slot__schedule__date__range=(previous_start,previous_end))
    def kpi(key,label,value,unit='',previous_value=None,tone='neutral'):
        return {'key':key,'label':label,'value':value,'unit':unit,'change':_change(value,previous_value) if previous_value is not None else None,'tone':tone}
    if user.role==User.Role.ADMIN:
        revenue=BillingRecord.objects.filter(status=BillingRecord.Status.PAID,paid_at__date__range=(start,today)).aggregate(value=Sum('amount'))['value'] or 0
        previous_revenue=BillingRecord.objects.filter(status=BillingRecord.Status.PAID,paid_at__date__range=(previous_start,previous_end)).aggregate(value=Sum('amount'))['value'] or 0
        kpis=[kpi('visits','预约量',current.count(),'人次',previous.count()),kpi('completed','完成诊疗',current.filter(status=Appointment.Status.COMPLETED).count(),'人次',previous.filter(status=Appointment.Status.COMPLETED).count()),kpi('revenue','结算收入',float(revenue),'元',float(previous_revenue)),kpi('inpatients','当前住院',InpatientAdmission.objects.filter(status=InpatientAdmission.Status.ADMITTED).count(),'人'),kpi('examinations','待处理检查',ExaminationOrder.objects.filter(status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS]).count(),'项',tone='warning'),kpi('low_stock','低库存药品',Medicine.objects.filter(is_active=True,stock__lte=10).count(),'种',tone='danger')]
    elif user.role==User.Role.DOCTOR:
        today_qs=appointments.filter(slot__schedule__date=today)
        kpis=[kpi('today','今日预约',today_qs.count(),'人次'),kpi('pending','待接诊',today_qs.filter(status=Appointment.Status.PENDING).count(),'人',tone='warning'),kpi('active','诊疗中',today_qs.filter(status=Appointment.Status.IN_PROGRESS).count(),'人'),kpi('completed','完成诊疗',current.filter(status=Appointment.Status.COMPLETED).count(),'人次',previous.filter(status=Appointment.Status.COMPLETED).count()),kpi('examinations','全院待检查',ExaminationOrder.objects.filter(status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS]).count(),'项',tone='warning'),kpi('inpatients','住院患者',InpatientAdmission.objects.filter(status=InpatientAdmission.Status.ADMITTED).count(),'人')]
    else:
        upcoming=appointments.filter(status=Appointment.Status.PENDING,slot__schedule__date__gte=today).count();unpaid=BillingRecord.objects.filter(patient__user=user,status=BillingRecord.Status.UNPAID).aggregate(value=Sum('amount'))['value'] or 0
        kpis=[kpi('upcoming','待就诊预约',upcoming,'项'),kpi('unpaid','待支付费用',float(unpaid),'元',tone='warning' if unpaid else 'neutral'),kpi('reports','已发布报告',ExaminationOrder.objects.filter(patient__user=user,status=ExaminationOrder.Status.PUBLISHED).count(),'份'),kpi('medicine','待取药处方',Prescription.objects.filter(record__appointment__patient__user=user,status=Prescription.Status.ISSUED).count(),'张',tone='warning')]
    appointment_counts={row['slot__schedule__date']:row for row in current.values('slot__schedule__date').annotate(visits=Count('id'),completed=Count('id',filter=Q(status=Appointment.Status.COMPLETED)))}
    revenue_counts={row['paid_at__date']:row['value'] for row in BillingRecord.objects.filter(status=BillingRecord.Status.PAID,paid_at__date__range=(start,today)).values('paid_at__date').annotate(value=Sum('amount'))} if user.role==User.Role.ADMIN else {}
    series=[]
    for offset in range(days):
        day=start+timedelta(days=offset);row=appointment_counts.get(day,{})
        series.append({'date':str(day),'visits':row.get('visits',0),'completed':row.get('completed',0),'revenue':float(revenue_counts.get(day,0))})
    recent=current.order_by('-created_at')[:8]
    payload={'meta':{'range':range_key,'start':str(start),'end':str(today),'generated_at':timezone.now().isoformat(),'role':user.role},'kpis':kpis,'timeseries':series,'appointment_status':[{'name':label,'value':current.filter(status=value).count()} for value,label in Appointment.Status.choices],'recent_activity':[{'id':item.id,'number':item.appointment_no,'patient':item.patient.user.get_full_name(),'doctor':item.doctor.user.get_full_name(),'department':item.doctor.department.name,'date':str(item.slot.schedule.date),'time':item.slot.start_time.strftime('%H:%M'),'status':item.get_status_display()} for item in recent]}
    if user.role==User.Role.ADMIN:
        total_beds=WardBed.objects.filter(is_active=True).count();occupied_beds=WardBed.objects.filter(is_active=True,is_occupied=True).count()
        payload.update({'department_workload':list(current.values(name=F('doctor__department__name')).annotate(value=Count('id')).order_by('-value')[:10]),'doctor_workload':list(current.filter(status=Appointment.Status.COMPLETED).values(name=F('doctor__user__first_name')).annotate(value=Count('id')).order_by('-value')[:10]),'billing_categories':list(BillingRecord.objects.filter(status=BillingRecord.Status.PAID,paid_at__date__range=(start,today)).values(name=F('category')).annotate(value=Sum('amount')).order_by('-value')),'bed_utilization':{'total':total_beds,'occupied':occupied_beds,'available':total_beds-occupied_beds,'rate':round(occupied_beds*100/total_beds,1) if total_beds else 0},'inventory_alerts':list(Medicine.objects.filter(is_active=True,stock__lte=10).values('id','name','specification','stock').order_by('stock')[:10]),'inpatient_status':[{'name':label,'value':InpatientAdmission.objects.filter(status=value).count()} for value,label in InpatientAdmission.Status.choices],'workflow':[{'name':'预约','value':current.count()},{'name':'进入诊疗','value':current.filter(status__in=[Appointment.Status.IN_PROGRESS,Appointment.Status.COMPLETED]).count()},{'name':'完成诊疗','value':current.filter(status=Appointment.Status.COMPLETED).count()},{'name':'确认病历','value':MedicalRecord.objects.filter(appointment__in=current,status=MedicalRecord.Status.CONFIRMED).count()},{'name':'开具处方','value':Prescription.objects.filter(record__appointment__in=current).count()},{'name':'完成结算','value':BillingRecord.objects.filter(appointment__in=current,status=BillingRecord.Status.PAID).count()}],'alerts':[{'label':'待就诊预约','value':Appointment.objects.filter(status=Appointment.Status.PENDING).count(),'tone':'warning','path':'/console/outpatient?tab=appointments'},{'label':'待处理检查','value':ExaminationOrder.objects.filter(status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS]).count(),'tone':'warning','path':'/console/clinical?tab=examinations'},{'label':'待结算账单','value':BillingRecord.objects.filter(status=BillingRecord.Status.UNPAID).count(),'tone':'danger','path':'/console/operations?tab=bills'},{'label':'低库存药品','value':Medicine.objects.filter(is_active=True,stock__lte=10).count(),'tone':'danger','path':'/console/clinical?tab=medicines'}]})
    elif user.role==User.Role.DOCTOR:
        schedule=appointments.filter(slot__schedule__date=today).order_by('slot__start_time')
        payload.update({'today_schedule':[{'id':item.id,'time':item.slot.start_time.strftime('%H:%M'),'patient':item.patient.user.get_full_name(),'reason':item.reason,'status':item.status,'status_label':item.get_status_display()} for item in schedule],'examination_queue':[{'id':item.id,'number':item.order_no,'patient':item.patient.user.get_full_name(),'type':item.get_type_display(),'status':item.status,'status_label':item.get_status_display(),'created_at':item.created_at.isoformat()} for item in ExaminationOrder.objects.filter(status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS,ExaminationOrder.Status.COMPLETED]).select_related('patient__user').order_by('created_at')[:8]],'alerts':[{'label':'待接诊','value':schedule.filter(status=Appointment.Status.PENDING).count(),'tone':'warning','path':'/doctor/outpatient?tab=appointments'},{'label':'诊疗中','value':schedule.filter(status=Appointment.Status.IN_PROGRESS).count(),'tone':'neutral','path':'/doctor/outpatient?tab=appointments'},{'label':'待处理检查','value':ExaminationOrder.objects.filter(status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS]).count(),'tone':'warning','path':'/doctor/clinical?tab=examinations'}]})
    else:
        next_item=appointments.filter(status=Appointment.Status.PENDING,slot__schedule__date__gte=today).order_by('slot__schedule__date','slot__start_time').first()
        next_appointment=None if not next_item else {'id':next_item.id,'number':next_item.appointment_no,'patient':next_item.patient.user.get_full_name(),'doctor':next_item.doctor.user.get_full_name(),'department':next_item.doctor.department.name,'date':str(next_item.slot.schedule.date),'time':next_item.slot.start_time.strftime('%H:%M'),'status':next_item.get_status_display()}
        payload.update({'next_appointment':next_appointment,'alerts':[{'label':'待支付账单','value':BillingRecord.objects.filter(patient__user=user,status=BillingRecord.Status.UNPAID).count(),'tone':'warning','path':'/patient/finance?tab=bills'},{'label':'待取药处方','value':Prescription.objects.filter(record__appointment__patient__user=user,status=Prescription.Status.ISSUED).count(),'tone':'warning','path':'/patient/care?tab=prescriptions'}]})
    return Response(payload)

class AIServiceViewSet(viewsets.ModelViewSet):
    serializer_class=AIServiceSerializer;queryset=AIService.objects.all();http_method_names=['get','post','patch','head','options']
    def create(self,request,*args,**kwargs):
        if request.user.role!=User.Role.ADMIN:raise PermissionDenied('仅管理员可配置智能服务。')
        return super().create(request,*args,**kwargs)
    def update(self,request,*args,**kwargs):
        if request.user.role!=User.Role.ADMIN:raise PermissionDenied('仅管理员可配置智能服务。')
        return super().update(request,*args,**kwargs)

class AITaskViewSet(mixins.CreateModelMixin,mixins.RetrieveModelMixin,mixins.ListModelMixin,viewsets.GenericViewSet):
    serializer_class=AITaskSerializer;queryset=AIAnalysisTask.objects.select_related('patient__user','file__order','service')
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset()
        if user.role==User.Role.PATIENT:return qs.filter(patient__user=user)
        if user.role==User.Role.DOCTOR:return qs
        return qs
    def perform_create(self,serializer):
        service=serializer.validated_data['service'];file=serializer.validated_data['file'];user=self.request.user
        if not service.is_enabled:raise APIValidationError('该智能服务尚未启用。')
        if user.role==User.Role.PATIENT and (file.order.patient.user_id!=user.id or file.order.status!=ExaminationOrder.Status.PUBLISHED):raise PermissionDenied('无权分析该医疗文件。')
        obj=serializer.save(patient=file.order.patient,created_by=user);audit(self.request,'create','ai_task',obj,'创建智能分析任务')
    @action(detail=True,methods=['get'])
    def result(self,request,pk=None):
        obj=self.get_object()
        return Response({'id':obj.pk,'status':obj.status,'result':obj.result if obj.status==AIAnalysisTask.Status.SUCCEEDED else None,'error_message':obj.error_message})
    @action(detail=True,methods=['post'])
    def cancel(self,request,pk=None):
        obj=self.get_object()
        if obj.status not in {AIAnalysisTask.Status.PENDING,AIAnalysisTask.Status.RUNNING}:raise APIValidationError('当前任务状态不可取消。')
        obj.status=AIAnalysisTask.Status.CANCELLED;obj.save(update_fields=['status','updated_at']);audit(request,'cancel','ai_task',obj,'取消智能分析任务')
        return Response(self.get_serializer(obj).data)

token_refresh=TokenRefreshView.as_view()
