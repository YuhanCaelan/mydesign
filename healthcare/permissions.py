from rest_framework.permissions import BasePermission,SAFE_METHODS
from .models import User

class HasRole(BasePermission):
    roles=()
    def has_permission(self,request,view):return bool(request.user and request.user.is_authenticated and request.user.is_active and request.user.role in self.roles)
class IsAdmin(HasRole):roles=(User.Role.ADMIN,)
class IsDoctor(HasRole):roles=(User.Role.DOCTOR,)
class IsPatient(HasRole):roles=(User.Role.PATIENT,)
class IsAdminOrReadOnly(BasePermission):
    def has_permission(self,request,view):return bool(request.user and request.user.is_authenticated and (request.method in SAFE_METHODS or request.user.role==User.Role.ADMIN))
class IsClinicalStaff(HasRole):roles=(User.Role.ADMIN,User.Role.DOCTOR)
class IsAdminWriteOrClinicalRead(BasePermission):
    """床位看板：管理员和医师可读，只有管理员可写。"""
    def has_permission(self,request,view):return bool(request.user and request.user.is_authenticated and request.user.is_active and (request.user.role in (User.Role.ADMIN,User.Role.DOCTOR) if request.method in SAFE_METHODS else request.user.role==User.Role.ADMIN))
