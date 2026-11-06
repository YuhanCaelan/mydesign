from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import User, Doctor, Patient


class UserMapper:
    def __init__(self, db: Session): self.db = db
    def find_by_id(self, user_id: int): return self.db.get(User, user_id)
    def find_by_username(self, username: str):
        return self.db.scalar(select(User).where(User.username == username))
    def find_doctor_by_user(self, user_id: int):
        return self.db.scalar(select(Doctor).where(Doctor.user_id == user_id))
    def find_patient_by_user(self, user_id: int):
        return self.db.scalar(select(Patient).where(Patient.user_id == user_id))
