import mimetypes
from datetime import timedelta
from django.db import transaction
from django.db.models import Count,F,Q,Sum
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
from .permissions import IsAdmin,IsAdminOrReadOnly
from .serializers import *
from .services import admit_patient,audit,finish_admission,record_stock_movement,transition_appointment

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
        qs=User.objects.select_related('doctor_profile__department','patient_profile').exclude(is_superuser=True).order_by('-created_at');search=self.request.query_params.get('search','').strip()
        if search:qs=qs.filter(Q(username__icontains=search)|Q(first_name__icontains=search)|Q(phone__icontains=search))
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
        user=self.request.user;qs=super().get_queryset()
        if user.role==User.Role.ADMIN:return qs
        if user.role==User.Role.PATIENT:return qs.filter(user=user)
        if user.role==User.Role.DOCTOR:return qs.filter(appointments__doctor__user=user).distinct()
        return qs.none()
    def retrieve(self,request,*args,**kwargs):
        obj=self.get_object();audit(request,'read','patient',obj,'读取患者档案');return Response(self.get_serializer(obj).data)
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

class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class=AppointmentSerializer;queryset=Appointment.objects.select_related('patient__user','doctor__user','doctor__department','slot__schedule');http_method_names=['get','post','head','options']
    search_fields=('appointment_no','patient__user__first_name','doctor__user__first_name','reason');ordering_fields=('created_at','slot__schedule__date','slot__start_time')
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset();state=self.request.query_params.get('status')
        if user.role==User.Role.PATIENT:qs=qs.filter(patient__user=user)
        elif user.role==User.Role.DOCTOR:qs=qs.filter(doctor__user=user)
        if state:qs=qs.filter(status=state)
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
        records=MedicalRecord.objects.filter(appointment__patient=appointment.patient).select_related('appointment__doctor__user','appointment__patient__user','appointment__slot__schedule').prefetch_related('corrections__author').order_by('-appointment__slot__schedule__date')
        current=records.filter(appointment=appointment).first()
        prescriptions=Prescription.objects.filter(record__appointment=appointment).select_related('record__appointment__patient__user','doctor__user').prefetch_related('items__medicine')
        examinations=ExaminationOrder.objects.filter(record__appointment=appointment).select_related('patient__user','doctor__user','record','item').prefetch_related('files')
        admissions=InpatientAdmission.objects.filter(patient=appointment.patient).select_related('patient__user','attending_doctor__user','department','appointment','bed')[:10]
        return Response({'appointment':self.get_serializer(appointment).data,'patient':PatientSerializer(appointment.patient).data,'current_record':MedicalRecordSerializer(current,context={'request':request}).data if current else None,'history':MedicalRecordSerializer(records.exclude(appointment=appointment)[:10],many=True,context={'request':request}).data,'prescriptions':PrescriptionSerializer(prescriptions,many=True,context={'request':request}).data,'examinations':ExaminationSerializer(examinations,many=True,context={'request':request}).data,'admissions':InpatientSerializer(admissions,many=True,context={'request':request}).data})

class MedicalRecordViewSet(viewsets.ModelViewSet):
    serializer_class=MedicalRecordSerializer;queryset=MedicalRecord.objects.select_related('appointment__patient__user','appointment__doctor__user','appointment__slot__schedule').prefetch_related('corrections__author');http_method_names=['get','post','patch','head','options']
    search_fields=('record_no','appointment__patient__user__first_name','diagnosis','chief_complaint');ordering_fields=('created_at','updated_at','confirmed_at')
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset()
        if user.role==User.Role.DOCTOR:qs=qs.filter(appointment__doctor__user=user)
        elif user.role==User.Role.PATIENT:qs=qs.filter(appointment__patient__user=user,status=MedicalRecord.Status.CONFIRMED)
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
    permission_classes=[IsAdminOrReadOnly];serializer_class=WardBedSerializer;queryset=WardBed.objects.select_related('department');http_method_names=['get','post','patch','head','options']
    search_fields=('ward_name','bed_no','department__name');ordering_fields=('ward_name','bed_no','daily_rate')
    def get_queryset(self):
        qs=super().get_queryset();department=self.request.query_params.get('department');available=self.request.query_params.get('available');active=self.request.query_params.get('active')
        if department:qs=qs.filter(department_id=department)
        if available=='true':qs=qs.filter(is_active=True,is_occupied=False)
        if active in {'true','false'}:qs=qs.filter(is_active=active=='true')
        return qs

class PrescriptionViewSet(viewsets.ModelViewSet):
    serializer_class=PrescriptionSerializer;queryset=Prescription.objects.select_related('record__appointment__patient__user','doctor__user').prefetch_related('items__medicine');http_method_names=['get','post','head','options']
    search_fields=('prescription_no','record__appointment__patient__user__first_name','record__diagnosis');ordering_fields=('created_at',)
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset()
        if user.role==User.Role.DOCTOR:return qs.filter(doctor__user=user)
        if user.role==User.Role.PATIENT:return qs.filter(record__appointment__patient__user=user)
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
    serializer_class=ExaminationSerializer;queryset=ExaminationOrder.objects.select_related('patient__user','doctor__user','record').prefetch_related('files');http_method_names=['get','post','head','options']
    search_fields=('order_no','patient__user__first_name','doctor__user__first_name','clinical_question');ordering_fields=('created_at','completed_at')
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset()
        if user.role==User.Role.PATIENT:qs=qs.filter(patient__user=user,status=ExaminationOrder.Status.PUBLISHED)
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
    allowed=user.role in {User.Role.ADMIN,User.Role.DOCTOR} or (user.role==User.Role.PATIENT and item.order.patient.user_id==user.id and item.order.status==ExaminationOrder.Status.PUBLISHED)
    if not allowed:raise PermissionDenied('无权访问该医疗文件。')
    try:handle=item.file.open('rb')
    except (FileNotFoundError,OSError):raise Http404('文件不存在。')
    audit(request,'download','medical_file',item,'下载医疗文件');return FileResponse(handle,content_type=mimetypes.guess_type(item.original_name)[0] or 'application/octet-stream',as_attachment=True,filename=item.original_name)

class BillingViewSet(viewsets.ModelViewSet):
    serializer_class=BillingSerializer;queryset=BillingRecord.objects.select_related('patient__user','appointment__doctor__user','prescription');http_method_names=['get','post','patch','head','options']
    search_fields=('bill_no','patient__user__first_name','description');ordering_fields=('created_at','amount')
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset();state=self.request.query_params.get('status')
        if user.role==User.Role.PATIENT:qs=qs.filter(patient__user=user)
        elif user.role==User.Role.DOCTOR:qs=qs.filter(appointment__doctor__user=user)
        if state:qs=qs.filter(status=state)
        return qs
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

class InpatientViewSet(viewsets.ModelViewSet):
    serializer_class=InpatientSerializer;queryset=InpatientAdmission.objects.select_related('patient__user','attending_doctor__user','department','appointment','bed');http_method_names=['get','post','patch','head','options']
    search_fields=('admission_no','patient__user__first_name','ward','bed_no','admission_diagnosis');ordering_fields=('created_at','admitted_at','discharged_at')
    def get_queryset(self):
        user=self.request.user;qs=super().get_queryset();state=self.request.query_params.get('status')
        if user.role==User.Role.PATIENT:qs=qs.filter(patient__user=user)
        if state:qs=qs.filter(status=state)
        return qs
    def perform_create(self,serializer):
        if self.request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权创建住院记录。')
        obj=serializer.save();audit(self.request,'create','inpatient',obj,'创建住院申请')
    def perform_update(self,serializer):
        if self.request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权修改住院记录。')
        if self.get_object().status in {InpatientAdmission.Status.DISCHARGED,InpatientAdmission.Status.CANCELLED}:raise APIValidationError('已结束的住院记录不可修改。')
        obj=serializer.save();audit(self.request,'update','inpatient',obj,'更新住院记录')
    @action(detail=True,methods=['post'])
    def admit(self,request,pk=None):
        if request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权办理入院。')
        obj=admit_patient(admission=self.get_object());audit(request,'admit','inpatient',obj,'办理入院');return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['post'])
    def discharge(self,request,pk=None):
        if request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权办理出院。')
        obj=finish_admission(admission=self.get_object(),summary=str(request.data.get('discharge_summary','')));audit(request,'discharge','inpatient',obj,'办理出院并生成费用');return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['post'])
    def cancel(self,request,pk=None):
        if request.user.role not in {User.Role.ADMIN,User.Role.DOCTOR}:raise PermissionDenied('无权取消住院。')
        obj=finish_admission(admission=self.get_object(),cancel=True);audit(request,'cancel','inpatient',obj,'取消住院并释放床位');return Response(self.get_serializer(obj).data)

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
        payload.update({'department_workload':list(current.values(name=F('doctor__department__name')).annotate(value=Count('id')).order_by('-value')[:10]),'doctor_workload':list(current.filter(status=Appointment.Status.COMPLETED).values(name=F('doctor__user__first_name')).annotate(value=Count('id')).order_by('-value')[:10]),'billing_categories':list(BillingRecord.objects.filter(status=BillingRecord.Status.PAID,paid_at__date__range=(start,today)).values(name=F('category')).annotate(value=Sum('amount')).order_by('-value')),'bed_utilization':{'total':total_beds,'occupied':occupied_beds,'available':total_beds-occupied_beds,'rate':round(occupied_beds*100/total_beds,1) if total_beds else 0},'inventory_alerts':list(Medicine.objects.filter(is_active=True,stock__lte=10).values('id','name','specification','stock').order_by('stock')[:10]),'inpatient_status':[{'name':label,'value':InpatientAdmission.objects.filter(status=value).count()} for value,label in InpatientAdmission.Status.choices],'workflow':[{'name':'预约','value':current.count()},{'name':'进入诊疗','value':current.filter(status__in=[Appointment.Status.IN_PROGRESS,Appointment.Status.COMPLETED]).count()},{'name':'完成诊疗','value':current.filter(status=Appointment.Status.COMPLETED).count()},{'name':'确认病历','value':MedicalRecord.objects.filter(appointment__in=current,status=MedicalRecord.Status.CONFIRMED).count()},{'name':'开具处方','value':Prescription.objects.filter(record__appointment__in=current).count()},{'name':'完成结算','value':BillingRecord.objects.filter(appointment__in=current,status=BillingRecord.Status.PAID).count()}],'alerts':[{'label':'待就诊预约','value':Appointment.objects.filter(status=Appointment.Status.PENDING).count(),'tone':'warning','path':'/console/appointments'},{'label':'待处理检查','value':ExaminationOrder.objects.filter(status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS]).count(),'tone':'warning','path':'/console/examinations'},{'label':'待结算账单','value':BillingRecord.objects.filter(status=BillingRecord.Status.UNPAID).count(),'tone':'danger','path':'/console/billing'},{'label':'低库存药品','value':Medicine.objects.filter(is_active=True,stock__lte=10).count(),'tone':'danger','path':'/console/medicines'}]})
    elif user.role==User.Role.DOCTOR:
        schedule=appointments.filter(slot__schedule__date=today).order_by('slot__start_time')
        payload.update({'today_schedule':[{'id':item.id,'time':item.slot.start_time.strftime('%H:%M'),'patient':item.patient.user.get_full_name(),'reason':item.reason,'status':item.status,'status_label':item.get_status_display()} for item in schedule],'examination_queue':[{'id':item.id,'number':item.order_no,'patient':item.patient.user.get_full_name(),'type':item.get_type_display(),'status':item.status,'status_label':item.get_status_display(),'created_at':item.created_at.isoformat()} for item in ExaminationOrder.objects.filter(status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS,ExaminationOrder.Status.COMPLETED]).select_related('patient__user').order_by('created_at')[:8]],'alerts':[{'label':'待接诊','value':schedule.filter(status=Appointment.Status.PENDING).count(),'tone':'warning','path':'/doctor/appointments'},{'label':'诊疗中','value':schedule.filter(status=Appointment.Status.IN_PROGRESS).count(),'tone':'neutral','path':'/doctor/appointments'},{'label':'待处理检查','value':ExaminationOrder.objects.filter(status__in=[ExaminationOrder.Status.REQUESTED,ExaminationOrder.Status.IN_PROGRESS]).count(),'tone':'warning','path':'/doctor/examinations'}]})
    else:
        next_item=appointments.filter(status=Appointment.Status.PENDING,slot__schedule__date__gte=today).order_by('slot__schedule__date','slot__start_time').first()
        next_appointment=None if not next_item else {'id':next_item.id,'number':next_item.appointment_no,'patient':next_item.patient.user.get_full_name(),'doctor':next_item.doctor.user.get_full_name(),'department':next_item.doctor.department.name,'date':str(next_item.slot.schedule.date),'time':next_item.slot.start_time.strftime('%H:%M'),'status':next_item.get_status_display()}
        payload.update({'next_appointment':next_appointment,'alerts':[{'label':'待支付账单','value':BillingRecord.objects.filter(patient__user=user,status=BillingRecord.Status.UNPAID).count(),'tone':'warning','path':'/patient/billing'},{'label':'待取药处方','value':Prescription.objects.filter(record__appointment__patient__user=user,status=Prescription.Status.ISSUED).count(),'tone':'warning','path':'/patient/prescriptions'}]})
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
