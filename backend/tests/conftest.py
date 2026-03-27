import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

from app.db.base import Base
from app.models import entities  # noqa: F401 — register models
from app.models.entities import User, Workspace


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(User(email="t@example.com", api_key="k"))
    session.flush()
    session.add(Workspace(user_id=1, name="W"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def twilio_request_body():
    return b"MessageSid=SM123&From=whatsapp%3A%2B15550001111&To=whatsapp%3B%2B15550002222&Body=hello"

