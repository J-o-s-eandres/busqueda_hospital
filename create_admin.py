from app import create_app
from app import db

from app.models import User

app = create_app()

with app.app_context():

    usuario = User.query.filter_by(
        username="admin"
    ).first()

    if usuario:

        print("Ya existe")

    else:

        admin = User(
            username="admin",
            role="admin"
        )

        admin.set_password("admin123")

        db.session.add(admin)

        db.session.commit()

        print("Administrador creado")