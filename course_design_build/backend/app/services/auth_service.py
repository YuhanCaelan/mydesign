from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core.security import create_access_token, verify_password
from app.mappers import UserMapper
from app.schemas import LoginRequest


class AuthService:
    def __init__(self, db: Session): self.mapper = UserMapper(db)

    def login(self, payload: LoginRequest):
        user = self.mapper.find_by_username(payload.username)
        if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=400, detail="用户名或密码错误")
        return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer",
                "user": self.user_info(user)}

    @staticmethod
    def user_info(user):
        return {"id": user.id, "username": user.username, "full_name": user.full_name,
                "role": user.role, "phone": user.phone}
