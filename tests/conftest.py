import os
import tempfile
import pytest
from app import create_app, db
from app.models import User, Estado, Hospital, Area, Person, seed_estatuses


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    GOOGLE_SHEET_ID = None
    GOOGLE_SERVICE_ACCOUNT_EMAIL = None
    GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY = None


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_estatuses()
        db.session.expire_on_commit = False
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def admin_user(app):
    u = User(
        username="admin",
        nombre="Admin",
        apellido="User",
        role="admin",
        active=True,
    )
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def helper_user(app):
    u = User(
        username="helper",
        nombre="Helper",
        apellido="User",
        role="helper",
        active=True,
    )
    u.set_password("helper123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def viewer_user(app):
    u = User(
        username="viewer",
        nombre="Viewer",
        apellido="User",
        role="viewer",
        active=True,
    )
    u.set_password("viewer123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def logged_client(app, client, admin_user):
    client.post("/auth/login", data={
        "username": "admin",
        "password": "admin123",
    })
    return client


@pytest.fixture
def catalog_data(app):
    estado = Estado(nombre="Anzoátegui")
    db.session.add(estado)
    db.session.commit()

    hospital = Hospital(nombre="Hospital Central", estado_id=estado.id)
    db.session.add(hospital)
    db.session.commit()

    area = Area(nombre="Emergencia")
    db.session.add(area)
    db.session.commit()

    return {"estado": estado, "hospital": hospital, "area": area}


@pytest.fixture
def sample_person(app, catalog_data):
    p = Person(
        nombre="Juan",
        apellido="Pérez",
        cedula="V12345678",
        sexo="Masculino",
        edad=35,
        estado_id=catalog_data["estado"].id,
        hospital_id=catalog_data["hospital"].id,
        area_id=catalog_data["area"].id,
        tiene_familiar=True,
        nombre_familiar="María Pérez",
        telefono="0412-1234567",
        estatus="Hospitalizado",
    )
    db.session.add(p)
    db.session.commit()
    return p
