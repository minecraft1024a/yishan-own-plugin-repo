"""数据库模型

定义日程表系统的所有数据模型。
"""

from datetime import datetime
from typing import List

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

# 创建独立的 Base，用于插件数据库
Base = declarative_base()


class Schedule(Base):
    """日程表模型"""

    __tablename__ = "schedule_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, index=True, unique=True)  # YYYY-MM-DD
    version = Column(Integer, default=1, nullable=False)  # 版本号（支持历史）
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # 关系
    items = relationship(
        "ScheduleItem", back_populates="schedule", cascade="all, delete-orphan"
    )

    # 元数据
    generated_by = Column(String(20), default="llm")  # llm/manual/template/fallback
    generation_error = Column(Text, nullable=True)  # 生成时的错误信息

    def __repr__(self) -> str:
        return f"<Schedule(id={self.id}, date={self.date}, items={len(self.items)})>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "date": self.date,
            "version": self.version,
            "is_active": self.is_active,
            "generated_by": self.generated_by,
            "generation_error": self.generation_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "items": [item.to_dict() for item in (self.items or [])],
        }


class ScheduleItem(Base):
    """日程项模型"""

    __tablename__ = "schedule_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(
        Integer,
        ForeignKey("schedule_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    time_range = Column(String(11), nullable=False)  # HH:MM-HH:MM
    activity = Column(String(200), nullable=False)
    priority = Column(Integer, default=3, nullable=False)  # 1-5
    tags = Column(JSON, default=list)  # ["学习", "工作"]

    is_completed = Column(Boolean, default=False)
    is_auto_generated = Column(Boolean, default=True)

    # 关系
    schedule = relationship("Schedule", back_populates="items")

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ScheduleItem(id={self.id}, time_range={self.time_range}, activity={self.activity})>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "time_range": self.time_range,
            "activity": self.activity,
            "priority": self.priority,
            "tags": self.tags or [],
            "is_completed": self.is_completed,
            "is_auto_generated": self.is_auto_generated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MonthlyPlan(Base):
    """月度计划模型（增强版）"""

    __tablename__ = "schedule_monthly_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_month = Column(String(7), nullable=False, index=True)  # YYYY-MM

    plan_text = Column(Text, nullable=False)
    priority = Column(Integer, default=3, nullable=False)  # 1-5
    deadline = Column(String(10), nullable=True)  # YYYY-MM-DD
    tags = Column(JSON, default=list)

    # 状态管理
    status = Column(
        String(20), default="active", index=True
    )  # active/completed/cancelled
    auto_complete_threshold = Column(
        Integer, default=3
    )  # 自动完成阈值（使用N次后自动完成）

    # 使用统计（每次被日程生成引用时 +1）
    usage_count = Column(Integer, default=0)
    last_used_date = Column(String(10), nullable=True)

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
    completed_at = Column(DateTime, nullable=True)  # 记录完成时间（自动或手动）

    def __repr__(self) -> str:
        return f"<MonthlyPlan(id={self.id}, month={self.target_month}, status={self.status})>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "target_month": self.target_month,
            "plan_text": self.plan_text,
            "priority": self.priority,
            "deadline": self.deadline,
            "tags": self.tags or [],
            "status": self.status,
            "auto_complete_threshold": self.auto_complete_threshold,
            "usage_count": self.usage_count,
            "last_used_date": self.last_used_date,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }


class ActivityStatistics(Base):
    """活动统计模型（用于学习和优化）"""

    __tablename__ = "schedule_activity_statistics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_type = Column(String(50), nullable=False, index=True)  # 活动类型（自动分类）

    total_scheduled = Column(Integer, default=0)  # 总共安排次数
    total_completed = Column(Integer, default=0)  # 总共完成次数
    completion_rate = Column(Integer, default=0)  # 完成率（百分比）

    preferred_time_slots = Column(JSON, default=list)  # 偏好时段 ["08:00-10:00"]
    average_duration = Column(Integer, default=0)  # 平均时长（分钟）

    last_updated = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ActivityStatistics(type={self.activity_type}, rate={self.completion_rate}%)>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "activity_type": self.activity_type,
            "total_scheduled": self.total_scheduled,
            "total_completed": self.total_completed,
            "completion_rate": self.completion_rate,
            "preferred_time_slots": self.preferred_time_slots or [],
            "average_duration": self.average_duration,
            "last_updated": self.last_updated.isoformat()
            if self.last_updated
            else None,
        }
