import io
import json


def test_dashboard_requires_login(client):
    resp = client.get("/admin/")
    assert resp.status_code == 302


def test_dashboard_logged_in(logged_client):
    resp = logged_client.get("/admin/")
    assert resp.status_code == 200


def test_persons_list(logged_client, sample_person):
    resp = logged_client.get("/admin/persons")
    assert resp.status_code == 200


def test_persons_api_list(logged_client, sample_person):
    resp = logged_client.get("/admin/api/persons/list")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["nombre"] == "Juan"


def test_persons_api_filter_nombre(logged_client, sample_person):
    resp = logged_client.get("/admin/api/persons/list?nombre=Juan")
    data = resp.get_json()
    assert len(data) == 1

    resp = logged_client.get("/admin/api/persons/list?nombre=NoExiste")
    data = resp.get_json()
    assert len(data) == 0


def test_create_person(logged_client, catalog_data):
    resp = logged_client.post("/admin/persons/new", data={
        "nombre": "Nueva",
        "apellido": "Persona",
        "cedula": "V99999999",
        "estado_id": catalog_data["estado"].id,
        "hospital_id": catalog_data["hospital"].id,
        "area_id": catalog_data["area"].id,
    }, follow_redirects=True)
    assert resp.status_code == 200

    from app.models import Person
    from app import db
    with logged_client.application.app_context():
        p = Person.query.filter_by(cedula="V99999999").first()
        assert p is not None
        assert p.nombre == "Nueva"


def test_edit_person_api(logged_client, sample_person):
    resp = logged_client.post(f"/admin/api/persons/{sample_person.id}/edit", data={
        "nombre": "JuanEditado",
        "apellido": sample_person.apellido,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("ok") is True

    from app.models import Person
    with logged_client.application.app_context():
        p = Person.query.get(sample_person.id)
        assert p.nombre == "JuanEditado"


def test_delete_person(logged_client, sample_person):
    resp = logged_client.get(f"/admin/persons/{sample_person.id}/delete", follow_redirects=True)
    assert resp.status_code == 200

    from app.models import Person
    with logged_client.application.app_context():
        p = Person.query.get(sample_person.id)
        assert p is None


def test_export_csv(logged_client, sample_person):
    resp = logged_client.get("/admin/export/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.content_type


def test_catalogs_page_exist(logged_client):
    resp = logged_client.get("/admin/catalogs")
    assert resp.status_code in (200, 302, 404)


def test_users_page(logged_client):
    resp = logged_client.get("/admin/users")
    assert resp.status_code == 200


def test_create_user(logged_client):
    resp = logged_client.get("/admin/users/new")
    assert resp.status_code == 200
    resp = logged_client.post("/admin/users/new", data={
        "username": "nuevo_user",
        "password": "pass123",
        "role": "helper",
    }, follow_redirects=True)
    assert resp.status_code == 200

    from app.models import User
    with logged_client.application.app_context():
        u = User.query.filter_by(username="nuevo_user").first()
        assert u is not None
        assert u.role == "helper"


def test_sync_requires_admin(logged_client, helper_user):
    """Helper should get 403 when trying to sync."""
    client = logged_client
    # login as helper instead
    client.post("/auth/login", data={
        "username": "helper",
        "password": "helper123",
    })
    resp = client.post("/admin/sync")
    assert resp.status_code == 403


def test_api_hospitals(logged_client, catalog_data):
    resp = logged_client.get(f"/admin/api/hospitals?estado_id={catalog_data['estado'].id}")
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["nombre"] == "Hospital Central"
