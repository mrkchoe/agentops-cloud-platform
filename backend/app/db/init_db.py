from app.db.session import engine
from app.models.entities import Base


def init_db() -> None:
    # Create any missing tables (additive; does not migrate existing columns).
    Base.metadata.create_all(bind=engine)

