from sqlalchemy import Column, Integer, String
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String, nullable=False)

    description = Column(String)

    priority = Column(String)

    deadline = Column(String)

    status = Column(String, default="Pending")

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

from sqlalchemy import Column, Integer, String

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    credits = Column(Integer)
    difficulty = Column(String)
    hours_per_week = Column(Integer)

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

class Milestone(Base):
    __tablename__ = "milestones"

    id = Column(Integer, primary_key=True, index=True)

    subject_id = Column(Integer)

    subject_name = Column(String)

    exam_date = Column(String)

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )