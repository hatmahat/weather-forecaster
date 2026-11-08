"""
Unit test fixtures for database and repository testing.

This module provides test fixtures for unit tests that need database access.
Uses MySQL 8.0 test database with SQLAlchemy nested transactions (SAVEPOINT) for test isolation.

IMPORTANT: Requires MySQL 8.0 test container running on localhost:3307
           Start with: docker-compose -f docker-compose.test.yml up -d
"""
import pytest
import os
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base

# MySQL test database URL (matches docker-compose.test.yml)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "mysql+pymysql://test_user:test_pass@localhost:3307/app_test"
)


@pytest.fixture(scope="session")
def test_engine():
    """
    Create MySQL 8.0 test engine (session-scoped, shared across all tests).

    Assumes MySQL test container is running on localhost:3307.
    Start with: docker-compose -f docker-compose.test.yml up -d

    Uses MySQL 8.0 to match production and catch MySQL-specific issues:
    - JSON column queries (job_metadata->'$.retrain')
    - ENUM handling
    - Transaction isolation behavior
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,  # Set to True for SQL debugging
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session")
def TestSessionLocal(test_engine):
    """Create a sessionmaker bound to the test engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db(test_engine, TestSessionLocal) -> Generator[Session, None, None]:
    """
    Provide a transactional database session with SAVEPOINT isolation.

    Critical pattern from SQLAlchemy docs for test isolation when repositories
    call db.commit() directly:

    1. Begin outer transaction (never committed)
    2. Begin nested transaction (SAVEPOINT)
    3. Test runs, repositories call db.commit()
    4. Event listener restarts SAVEPOINT after each commit
    5. After test: rollback outer transaction (undo all commits)

    This ensures:
    - Repository code can call db.commit() naturally
    - Each test gets clean database state
    - No cross-test contamination

    Usage:
        def test_repository(db):
            repo = JobRepository()
            job = repo.create_job(db, "TEST")  # calls db.commit()
            assert job.id is not None
            # Cleanup happens automatically via rollback

    Reference:
        https://docs.sqlalchemy.org/en/latest/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    session = TestSessionLocal(bind=connection)
    nested = connection.begin_nested()

    # Critical: Restart SAVEPOINT after each commit() so isolation is maintained
    # Only restart if the nested transaction ended (not the outer transaction)
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            session.begin_nested()

    yield session

    # Cleanup: rollback outer transaction (undoes all commits in test)
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def db_session(db) -> Session:
    """
    Alias for db fixture (for backward compatibility).

    Usage:
        def test_repository(db_session):
            repo = JobRepository()
            job = repo.create(db_session, {...})
    """
    return db
