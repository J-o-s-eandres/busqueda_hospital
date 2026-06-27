from app import db
from app.models import User, Person, Estado, Hospital, Area, Estatus
from app.models import normalize_name, display_name, seed_estatuses, log_action


def test_create_user(app):
    with app.app_context():
        u = User(username="test", role="admin")
        u.set_password("secret")
        db.session.add(u)
        db.session.commit()

        fetched = User.query.filter_by(username="test").first()
        assert fetched is not None
        assert fetched.role == "admin"
        assert fetched.check_password("secret") is True
        assert fetched.check_password("wrong") is False


def test_create_person(app, catalog_data):
    p = Person(
        nombre="María",
        apellido="González",
        cedula="V87654321",
        estado_id=catalog_data["estado"].id,
        hospital_id=catalog_data["hospital"].id,
        area_id=catalog_data["area"].id,
    )
    db.session.add(p)
    db.session.commit()

    fetched = Person.query.filter_by(cedula="V87654321").first()
    assert fetched is not None
    assert fetched.nombre == "María"
    assert fetched.apellido == "González"
    assert fetched.estado.nombre == "Anzoátegui"
    assert fetched.hospital.nombre == "Hospital Central"
    assert fetched.area.nombre == "Emergencia"
    assert fetched.estatus == "Hospitalizado"


def test_person_estatus_default(app):
    with app.app_context():
        p = Person(nombre="Test")
        db.session.add(p)
        db.session.commit()
        assert p.estatus == "Hospitalizado"


def test_seed_estatuses(app):
    with app.app_context():
        count = seed_estatuses()
        total = Estatus.query.count()
        assert total == 5
        for name in ["Hospitalizado", "Trasladado", "Alta", "Fallecido", "No localizado"]:
            assert Estatus.query.filter_by(nombre=name).first() is not None


def test_seed_estatuses_idempotent(app):
    with app.app_context():
        seed_estatuses()
        first_count = Estatus.query.count()
        seed_estatuses()
        second_count = Estatus.query.count()
        assert first_count == second_count == 5


def test_normalize_name():
    assert normalize_name("  Juan  ") == "juan"
    assert normalize_name("MARÍA") == "maría"
    assert normalize_name("") == ""
    assert normalize_name(None) == ""


def test_display_name():
    assert display_name("juan") == "Juan"
    assert display_name("maría pérez") == "María pérez"
    assert display_name("") == ""
    assert display_name(None) == ""


def test_user_roles(app):
    admin = User(username="a1", role="admin")
    admin.set_password("p1")
    helper = User(username="h1", role="helper")
    helper.set_password("p2")
    viewer = User(username="v1", role="viewer")
    viewer.set_password("p3")
    db.session.add_all([admin, helper, viewer])
    db.session.commit()

    assert User.query.filter_by(role="admin").count() == 1
    assert User.query.filter_by(role="helper").count() == 1
    assert User.query.filter_by(role="viewer").count() == 1


def test_log_action(app, admin_user):
    log_action(admin_user, "create", "Person", 1, "Test log")
    db.session.commit()

    from app.models import AuditLog
    log = AuditLog.query.first()
    assert log is not None
    assert log.action == "create"
    assert log.target_type == "Person"
    assert log.username == "admin"


def test_catalog_relationships(app, catalog_data):
    with app.app_context():
        estado = Estado.query.filter_by(nombre="Anzoátegui").first()
        assert len(estado.persons) == 0

        p = Person(nombre="Test", estado_id=estado.id)
        db.session.add(p)
        db.session.commit()

        assert len(estado.persons) == 1
        assert estado.persons[0].nombre == "Test"


def test_person_estatus_choices(app):
    with app.app_context():
        valid = Person.ESTATUS_CHOICES
        for s in valid:
            p = Person(nombre="Test", estatus=s)
            db.session.add(p)
            db.session.commit()
            assert p.estatus == s


def test_estado_unique_constraint(app):
    e1 = Estado(nombre="TestEstado2")
    db.session.add(e1)
    db.session.commit()
    from sqlalchemy.exc import IntegrityError
    import pytest
    e2 = Estado(nombre="TestEstado2")
    db.session.add(e2)
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()
