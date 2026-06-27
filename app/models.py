from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import db, login_manager
from flask import current_app


# ---------------------------------------------------------------------------
# Flask-Login user loader
# ---------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    nombre = db.Column(db.String(120), nullable=True)
    apellido = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="helper")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ---------------------------------------------------------------------------
# Catalog models
# ---------------------------------------------------------------------------
class Estado(db.Model):
    __tablename__ = "estados"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), unique=True, nullable=False)
    persons = db.relationship("Person", back_populates="estado")


class Hospital(db.Model):
    __tablename__ = "hospitals"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(250), unique=True, nullable=False)
    estado_id = db.Column(db.Integer, db.ForeignKey("estados.id"), nullable=True)
    estado = db.relationship("Estado", backref="hospitals")
    persons = db.relationship("Person", back_populates="hospital")


class Area(db.Model):
    __tablename__ = "areas"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    persons = db.relationship("Person", back_populates="area")


# ---------------------------------------------------------------------------
# Estatus model (catálogo de estatus)
# ---------------------------------------------------------------------------
class Estatus(db.Model):
    __tablename__ = "estatuses"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Person model (paciente)
# ---------------------------------------------------------------------------
class Person(db.Model):
    __tablename__ = "persons"
    id = db.Column(db.Integer, primary_key=True)
    # Información básica del paciente
    nombre = db.Column(db.String(120), nullable=False)
    apellido = db.Column(db.String(120), nullable=True)
    cedula = db.Column(db.String(30), nullable=True)
    sexo = db.Column(db.String(20), nullable=True)
    edad = db.Column(db.Integer, nullable=True)
    fecha_ingreso = db.Column(db.DateTime, nullable=True)
    # Relaciones a catálogos
    estado_id = db.Column(db.Integer, db.ForeignKey("estados.id"), nullable=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=True)
    area_id = db.Column(db.Integer, db.ForeignKey("areas.id"), nullable=True)
    estado = db.relationship("Estado", back_populates="persons")
    hospital = db.relationship("Hospital", back_populates="persons")
    area = db.relationship("Area", back_populates="persons")
    # Estado de salud y familia
    estado_salud = db.Column(db.Text, nullable=True)
    tiene_familiar = db.Column(db.Boolean, default=False)
    nombre_familiar = db.Column(db.String(200), nullable=True)
    telefono = db.Column(db.String(80), nullable=True)
    observaciones = db.Column(db.Text, nullable=True)
    # Control de importación desde Google Sheet
    sheet_row = db.Column(db.Integer, nullable=True)
    # Timestamps
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Estatus del paciente
    ESTATUS_CHOICES = (
        "Hospitalizado",
        "Trasladado",
        "Alta",
        "Fallecido",
        "No localizado",
    )
    estatus = db.Column(db.String(30), default="Hospitalizado")


# ---------------------------------------------------------------------------
# SyncLog model
# ---------------------------------------------------------------------------
class SyncLog(db.Model):
    __tablename__ = "sync_logs"
    id = db.Column(db.Integer, primary_key=True)
    imported = db.Column(db.Integer, nullable=False)
    duplicated = db.Column(db.Integer, nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    target_type = db.Column(db.String(30), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="audit_logs")


def log_action(user, action, target_type, target_id=None, details=None):
    log = AuditLog(
        user_id=user.id,
        username=user.username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.session.add(log)


def require_role(*roles):
    from flask import abort
    from flask_login import current_user

    if current_user.role not in roles:
        abort(403)


def normalize_name(name):
    if not name or not isinstance(name, str):
        return ""
    name = name.strip().lower()
    return name


def display_name(name):
    if not name:
        return ""
    return name.strip().capitalize()


from sqlalchemy.exc import IntegrityError


def seed_estatuses():
    """Seed estatuses with table existence check."""
    from sqlalchemy import inspect
    # Verify the 'estatuses' table exists; create all tables if missing
    inspector = inspect(db.engine)
    if 'estatuses' not in inspector.get_table_names():
        print("⚠️ Tabla 'estatuses' no existe, creando todas las tablas...")
        db.create_all()
        # Re‑inspect after creation
        inspector = inspect(db.engine)
        if 'estatuses' not in inspector.get_table_names():
            print("❌ No se pudo crear la tabla 'estatuses'")
            return 0
    defaults = ["Hospitalizado", "Trasladado", "Alta", "Fallecido", "No localizado"]
    created = 0
    for s in defaults:
        if not Estatus.query.filter_by(nombre=s).first():
            db.session.add(Estatus(nombre=s))
            created += 1
    if created:
        try:
            db.session.commit()
            print(f"✅ {created} estatus creados")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error al guardar estatuses: {e}")
    return created