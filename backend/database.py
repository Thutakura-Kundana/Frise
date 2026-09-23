"""Database configuration and setup."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# Database configuration
DATABASE_URL = "sqlite:///./frise.db"

# SQLite configuration with proper settings
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    ensure_food_item_columns()
    ensure_user_columns()


def ensure_food_item_columns():
    """Add new SQLite columns for existing local databases."""
    inspector = inspect(engine)
    if "food_items" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("food_items")
    }
    migrations = {
        "shelf_location": (
            "ALTER TABLE food_items ADD COLUMN shelf_location VARCHAR(100)"
        ),
        "storage_state": (
            "ALTER TABLE food_items ADD COLUMN storage_state VARCHAR(100)"
        ),
        "space_units": (
            "ALTER TABLE food_items ADD COLUMN space_units INTEGER DEFAULT 1"
        ),
    }

    with engine.begin() as connection:
        for column_name, statement in migrations.items():
            if column_name not in existing_columns:
                connection.execute(text(statement))


def ensure_user_columns():
    """Add ownership columns to databases created before authentication."""
    inspector = inspect(engine)
    with engine.begin() as connection:
        table_columns = {
            table: {column["name"] for column in inspector.get_columns(table)}
            for table in ("food_items", "notifications", "activity_logs")
            if table in inspector.get_table_names()
        }
        migrations = {
            "food_items": "ALTER TABLE food_items ADD COLUMN user_id INTEGER",
            "notifications": "ALTER TABLE notifications ADD COLUMN user_id INTEGER",
            "activity_logs": "ALTER TABLE activity_logs ADD COLUMN user_id INTEGER",
        }
        for table, statement in migrations.items():
            if table in table_columns and "user_id" not in table_columns[table]:
                connection.execute(text(statement))
