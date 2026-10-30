import importlib

import pytest


@pytest.fixture(scope="session")
def flask_app(tmp_path_factory):
    isolated = tmp_path_factory.mktemp("coffee-session")
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("COFFEE_DB_PATH", str(isolated / "session.db"))
        environment.setenv("COFFEE_RUNTIME_DIR", str(isolated / "runtime"))
        environment.setenv("FLASK_DEBUG", "0")
        # Legacy multi-plot fixtures exercise the reusable implementation.
        # Single-base default is separately tested with app.config enabled.
        environment.setenv('SINGLE_PLOT_ID','')
        # config may already have been imported by configuration-only tests.
        import config
        importlib.reload(config)
        from app import create_app

        application = create_app()
        application.config.update(TESTING=True)
        yield application


@pytest.fixture
def client(flask_app, monkeypatch, tmp_path):
    from database import init_db as database

    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    database.init_db()
    return flask_app.test_client()
