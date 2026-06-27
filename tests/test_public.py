import json


def test_search_page_loads(client):
    resp = client.get("/public/search")
    assert resp.status_code == 200
    assert b"B" in resp.data or b"b" in resp.data


def test_api_empty(client):
    resp = client.get("/public/api/persons")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_api_with_person(client, sample_person):
    resp = client.get("/public/api/persons")
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["nombre"] == "Juan"
    assert data[0]["apellido"] == "Pérez"
    assert data[0]["cedula"] == "V12345678"


def test_api_filter_by_name(client, sample_person):
    resp = client.get("/public/api/persons?nombre=Juan")
    data = resp.get_json()
    assert len(data) == 1

    resp = client.get("/public/api/persons?nombre=NoExiste")
    data = resp.get_json()
    assert len(data) == 0


def test_api_filter_by_apellido(client, sample_person):
    resp = client.get("/public/api/persons?nombre=Pérez")
    data = resp.get_json()
    assert len(data) == 1


def test_api_filter_by_estado(client, sample_person, catalog_data):
    resp = client.get(f"/public/api/persons?estado_id={catalog_data['estado'].id}")
    data = resp.get_json()
    assert len(data) == 1

    resp = client.get("/public/api/persons?estado_id=99999")
    data = resp.get_json()
    assert len(data) == 0


def test_api_filter_by_hospital(client, sample_person, catalog_data):
    resp = client.get(f"/public/api/persons?hospital_id={catalog_data['hospital'].id}")
    data = resp.get_json()
    assert len(data) == 1


def test_api_filter_by_area(client, sample_person, catalog_data):
    resp = client.get(f"/public/api/persons?area_id={catalog_data['area'].id}")
    data = resp.get_json()
    assert len(data) == 1


def test_api_returns_all_fields(client, sample_person):
    resp = client.get("/public/api/persons")
    data = resp.get_json()
    p = data[0]
    assert "nombre" in p
    assert "apellido" in p
    assert "cedula" in p
    assert "edad" in p
    assert "sexo" in p
    assert "estado" in p
    assert "hospital" in p
    assert "area" in p
    assert "estatus" in p
    assert "telefono" in p
    assert "tiene_familiar" in p
    assert "observaciones" in p
    assert "fecha_registro" in p


def test_api_sin_informacion(client):
    from app import db
    from app.models import Person
    with client.application.app_context():
        p = Person(nombre="Test")
        db.session.add(p)
        db.session.commit()

    resp = client.get("/public/api/persons")
    data = resp.get_json()
    sin_info = [p for p in data if p.get("cedula") == "sin información"]
    assert len(sin_info) == 1
