from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import date, datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    created_at = Column(String, nullable=True, default=lambda: date.today().strftime("%Y-%m-%d"))

    # User Preferences (Routine Calibration & Intelligence Constraints)
    daily_quota = Column(Integer, default=6)
    focus_period = Column(String, default="Morning")
    focus_method = Column(String, default="Classic Pomodoro")
    avoid_early_mornings = Column(Boolean, default=False)
    prioritize_critical = Column(Boolean, default=True)
    intensive_pre_exam = Column(Boolean, default=True)
    weekend_preservation = Column(Boolean, default=False)

    # Bidirectional relationships with delete-orphan cascades
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="user", cascade="all, delete-orphan")
    milestones = relationship("Milestone", back_populates="user", cascade="all, delete-orphan")
    resources = relationship("Resource", back_populates="user", cascade="all, delete-orphan")
    schedule_events = relationship("ScheduleEvent", back_populates="user", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="user", cascade="all, delete-orphan")

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    credits = Column(Integer, default=0)
    difficulty = Column(String)
    hours_per_week = Column(Integer, default=0)
    semester = Column(Integer, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="subjects")
    # A subject can have multiple milestones; delete subject deletes its milestones
    milestones = relationship("Milestone", back_populates="subject", cascade="all, delete-orphan")
    resources = relationship("Resource", back_populates="subject", cascade="all, delete-orphan")
    schedule_events = relationship("ScheduleEvent", back_populates="subject", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="subject", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="subject", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    priority = Column(String)
    deadline = Column(String)
    status = Column(String, default="Pending")
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="tasks")
    subject = relationship("Subject", back_populates="tasks")

class Milestone(Base):
    __tablename__ = "milestones"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    subject_name = Column(String)
    exam_date = Column(String, nullable=False)
    title = Column(String, nullable=True)
    completion_percentage = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="milestones")
    subject = relationship("Subject", back_populates="milestones")

class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    link = Column(String, nullable=True)
    upload_date = Column(String, nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="resources")
    subject = relationship("Subject", back_populates="resources")

class ScheduleEvent(Base):
    __tablename__ = "schedule_events"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    session_type = Column(String, nullable=True, default="Deep Focus")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="schedule_events")
    subject = relationship("Subject", back_populates="schedule_events")

class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    completed_at = Column(String, nullable=False)
    session_type = Column(String, nullable=False)

    user = relationship("User", back_populates="study_sessions")
    subject = relationship("Subject", back_populates="study_sessions")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(String, nullable=False, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    user = relationship("User", backref="notifications")