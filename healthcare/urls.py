from django.urls import include,path
from rest_framework.routers import DefaultRouter
from . import views

router=DefaultRouter()
router.register('users',views.UserViewSet,basename='user');router.register('departments',views.DepartmentViewSet)
router.register('doctors',views.DoctorViewSet);router.register('patients',views.PatientViewSet)
router.register('schedules',views.ScheduleViewSet);router.register('appointments',views.AppointmentViewSet)
router.register('medical-records',views.MedicalRecordViewSet);router.register('medicines',views.MedicineViewSet)
router.register('medicine-stock-movements',views.MedicineStockMovementViewSet,basename='medicine-stock-movement');router.register('examination-items',views.ExaminationItemViewSet);router.register('ward-beds',views.WardBedViewSet)
router.register('prescriptions',views.PrescriptionViewSet);router.register('examinations',views.ExaminationViewSet)
router.register('billing-records',views.BillingViewSet);router.register('inpatients',views.InpatientViewSet)
router.register('audit-logs',views.AuditViewSet);router.register('ai/services',views.AIServiceViewSet,basename='ai-service');router.register('ai/tasks',views.AITaskViewSet,basename='ai-task')
urlpatterns=[
    path('auth/login/',views.login),path('auth/register/',views.register),path('auth/refresh/',views.token_refresh),path('auth/me/',views.me),path('auth/change-password/',views.change_password),
    path('statistics/overview/',views.statistics_overview),path('statistics/dashboard/',views.statistics_dashboard),path('medical-files/<int:pk>/download/',views.medical_file_download),path('',include(router.urls)),
]
