"""Read-local retention preserves validation and bounds live ORM references."""

import gc
import weakref
from types import SimpleNamespace

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


@pytest.mark.parametrize("fail", [False, True])
def test_review_preparation_retains_only_during_reading_and_releases_before_save(database, monkeypatch, fail):
    from app.services import review_preparation_command as preparation
    from tests.v2.services.test_work_draft_calculation import material
    authority = material().authority
    queries, validations, saved = [], [], []
    event.listen(database, "before_cursor_execute", lambda *args: queries.append(args[2]))
    context = SimpleNamespace(authority=authority)
    monkeypatch.setattr(preparation, "IdempotencyRepository", lambda _: SimpleNamespace(resolve=lambda **_: (
        SimpleNamespace(result_type="review_context_v2", status=preparation.STATUS_COMMITTED, result_id="context"), True)))
    monkeypatch.setattr(preparation, "FactAuthorityValidator", lambda _: SimpleNamespace(validate=lambda _: None))
    with Session(database) as session, session.begin():
        listeners = len(session.dispatch.loaded_as_persistent)
        def assemble(current, *_args, **_kwargs):
            assert current is session and len(session.dispatch.loaded_as_persistent) == listeners + 1
            for _ in range(4):
                record = session.get(Record, 1)
                assert record.value == "1"
                validations.append(record.value)
                del record
                gc.collect()
            if fail:
                raise ValueError("source rejected")
            return context
        def save(value):
            assert len(session.dispatch.loaded_as_persistent) == listeners
            saved.append(value)
            return value
        monkeypatch.setattr(preparation, "assemble_review_context", assemble)
        monkeypatch.setattr(preparation, "ReviewContextV2Repository", lambda _: SimpleNamespace(save=save))
        kwargs = dict(subject_id=authority.subject_id, review_episode_id=authority.review_episode_id,
            expected_authority=authority, idempotency_key="read-scope", work_draft=True)
        if fail:
            with pytest.raises(ValueError, match="source rejected"):
                preparation.prepare_review(session, object(), **kwargs)
            assert saved == []
        else:
            assert preparation.prepare_review(session, object(), **kwargs) is context
            assert saved == [context]
        assert len(session.dispatch.loaded_as_persistent) == listeners
    assert validations == ["1"] * 4
    assert sum(statement.startswith("SELECT read_retention_fixture.") for statement in queries) == 1
