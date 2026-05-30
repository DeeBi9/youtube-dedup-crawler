from sqlalchemy import create_engine, text, Column, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Session


DB_PATH = "crawler.db"
engine = None


class Base(DeclarativeBase):
    pass


class ScanQueue(Base):
    __tablename__ = "scan_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    url = Column(Text, nullable=False)
    thumbnail = Column(Text, nullable=True)
    phash = Column(String, nullable=False)
    created_at = Column(String, nullable=False, server_default=text("(datetime('now'))"))


def get_engine():
    global engine
    if engine is None:
        engine = create_engine(
            f"sqlite:///{DB_PATH}",
            connect_args={"check_same_thread": False},
        )
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()
    return engine


def init_db():
    eng = get_engine()
    Base.metadata.create_all(eng)


def load_all_phashes():
    """Return list of ImageHash objects loaded from scan_queue."""
    import imagehash

    eng = get_engine()
    with Session(eng) as session:
        rows = session.execute(text("SELECT phash FROM scan_queue")).fetchall()
    return [imagehash.hex_to_hash(row[0]) for row in rows]
