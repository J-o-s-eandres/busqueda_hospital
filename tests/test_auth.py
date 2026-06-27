def test_login_page(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert b"Iniciar" in resp.data or b"login" in resp.data.lower() or b"Login" in resp.data


def test_login_success(client, admin_user):
    resp = client.post("/auth/login", data={
        "username": "admin",
        "password": "admin123",
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_login_wrong_password(client, admin_user):
    resp = client.post("/auth/login", data={
        "username": "admin",
        "password": "wrongpass",
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_logout(client, admin_user):
    client.post("/auth/login", data={
        "username": "admin",
        "password": "admin123",
    })
    resp = client.get("/auth/logout", follow_redirects=True)
    assert resp.status_code == 200


def test_admin_redirects_to_login(client):
    resp = client.get("/admin/", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Iniciar" in resp.data or b"login" in resp.data.lower()


def test_public_access_no_login(client):
    resp = client.get("/public/search")
    assert resp.status_code == 200


def test_public_api_no_login(client, sample_person):
    resp = client.get("/public/api/persons")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["nombre"] == "Juan"
