from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Shared metadata for all ORM models. Alembic autogenerates against this."""