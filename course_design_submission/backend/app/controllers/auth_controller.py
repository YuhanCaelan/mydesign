from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas import LoginRequest, LoginResponse, UserInfo
from app.services import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse, summary="账号登录")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return AuthService(db).login(payload)


@router.get("/me", response_model=UserInfo, summary="当前用户")
def me(user=Depends(get_current_user)):
    return AuthService.user_info(user)
