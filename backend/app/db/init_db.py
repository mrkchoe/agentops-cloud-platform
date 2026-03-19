from sqlalchemy import inspect

from app.db.session import engine
from app.models.entities import Base, model_classes


def init_db() -> None:
    # Ensure tables exist. For this portfolio app we use create_all for local dev.
    inspector = inspect(engine)
    existing = inspector.get_table_names()
    if existing:
        return

    Base.metadata.create_all(bind=engine)

