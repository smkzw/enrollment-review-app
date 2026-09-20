"""Read-local retention preserves validation and bounds live ORM references."""

import gc
import weakref

import pytest
from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.storage.read_retention import retain_read_records


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "read_retention_fixture"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str]


@pytest.fixture
def database():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Record(id=index, value=str(index)) for index in range(6)])
        session.commit()
    yield engine
    engine.dispose()


def test_repeated_reads_reuse_records_but_not_validation(database):
    queries = []
    event.listen(database, "before_cursor_execute", lambda *args: queries.append(args[2]))
    validations = []
    with Session(database) as session, retain_read_records(session):
        for _ in range(3):
            record = session.get(Record, 1)
            validations.append(record.value)
            assert record.value == "1"
            del record
            gc.collect()
    assert validations == ["1"] * 3
    assert len(queries) == 1


def test_capacity_eviction_reloads_instead_of_hiding_record(database):
    with Session(database) as session, retain_read_records(session, capacity=2):
        first = session.get(Record, 0)
        reference = weakref.ref(first)
        del first
        for index in range(1, 6):
            assert session.get(Record, index).value == str(index)
        gc.collect()
        assert reference() is None
        assert len(session.identity_map) <= 2
        assert session.get(Record, 0).value == "0"


@pytest.mark.parametrize("fail", [False, True])
def test_scope_releases_records_and_listener_even_on_failure(database, fail):
    with Session(database) as session:
        before = len(session.dispatch.loaded_as_persistent)
        try:
            with retain_read_records(session):
                record = session.get(Record, 1)
                reference = weakref.ref(record)
                del record
                if fail:
                    raise RuntimeError("validation failed")
        except RuntimeError as exc:
            assert str(exc) == "validation failed"
        gc.collect()
        assert reference() is None
        assert len(session.dispatch.loaded_as_persistent) == before


def test_next_request_reads_changed_source(database):
    with Session(database) as session, retain_read_records(session):
        assert session.get(Record, 1).value == "1"
    with database.begin() as connection:
        connection.execute(update(Record).where(Record.id == 1).values(value="changed"))
    with Session(database) as session, retain_read_records(session):
        assert session.get(Record, 1).value == "changed"


def test_invalid_capacity_is_rejected(database):
    with Session(database) as session, pytest.raises(ValueError):
        with retain_read_records(session, capacity=0):
            pytest.fail("invalid capacity was accepted")
