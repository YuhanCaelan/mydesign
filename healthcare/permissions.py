from rest_framework.permissions import BasePermission,SAFE_METHODS
from .models import User

class HasRole(BasePermission):
    roles=()
    def has_permission(self,request,view):return bool(request.user and request.user.is_authenticated and request.user.is_active and request.user.role in self.roles)
class IsAdmin(HasRole):roles=(User.Role.ADMIN,)
class IsDoctor(HasRole):roles=(User.Role.DOCTOR,)
class IsNurse(HasRole):roles=(User.Role.NURSE,)
class IsStaff(HasRole):roles=(User.Role.STAFF,)
class IsPatient(HasRole):roles=(User.Role.PATIENT,)
class IsAdminOrReadOnly(BasePermission):
    def has_permission(self,request,view):return bool(request.user and request.user.is_authenticated and (request.method in SAFE_METHODS or request.user.role==User.Role.ADMIN))
class IsClinicalStaff(HasRole):roles=(User.Role.ADMIN,User.Role.DOCTOR)
class IsAdminWriteOrClinicalRead(BasePermission):
    """床位看板：医务人员可读，只有管理员可写。"""
    def has_permission(self,request,view):
        if not (request.user and request.user.is_authenticated and request.user.is_active):return False
        if request.method in SAFE_METHODS:return request.user.role in (User.Role.ADMIN,User.Role.DOCTOR,User.Role.STAFF,User.Role.NURSE)
        return request.user.role==User.Role.ADMIN

def is_admin(user):return bool(user and user.is_authenticated and user.role==User.Role.ADMIN)
def is_staff(user,station=None):
    return bool(user and user.is_authenticated and user.role==User.Role.STAFF and (station is None or user.station==station))
def is_nurse(user):return bool(user and user.is_authenticated and user.role==User.Role.NURSE)
def can_manage_schedule(user):return is_admin(user) or is_staff(user,User.Station.SCHEDULE)
def can_dispense(user):return is_admin(user) or is_staff(user,User.Station.PHARMACY)
def can_execute(user):return is_admin(user) or is_staff(user,User.Station.EXECUTION) or is_nurse(user)
def can_refund(user):return is_admin(user) or is_staff(user,User.Station.CASHIER)
def can_admit(user):return is_admin(user) or is_staff(user,User.Station.ADMISSION)
