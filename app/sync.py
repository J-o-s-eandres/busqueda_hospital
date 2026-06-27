from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from flask import current_app
from sqlalchemy.exc import IntegrityError
from .models import (
    db,
    Person,
    Estado,
    Hospital,
    Area,
    Estatus,
    SyncLog,
    normalize_name,
    seed_estatuses,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADERS = [
    "nombre",
    "apellido",
    "cedula",
    "sexo",
    "edad",
    "telefono",
    "estado_salud",
    "tiene_familiar",
    "nombre_familiar",
    "estatus",
    "observaciones",
    "estado",
    "hospital",
    "area",
]


def get_gspread_client():
    import json
    import os
    
    # 🔧 PRIMERO: Intentar con el JSON completo
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        try:
            info = json.loads(service_account_json)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            current_app.logger.error(f"Error loading JSON credentials: {e}")
    
    # FALLBACK: Usar variables individuales (por si acaso)
    email = current_app.config.get("GOOGLE_SERVICE_ACCOUNT_EMAIL")
    private_key = current_app.config.get("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY")
    if not email or not private_key:
        raise RuntimeError("No Google credentials found. Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_EMAIL/_PRIVATE_KEY")
    
    info = {
        "type": "service_account",
        "project_id": "hospital-busqueda",
        "private_key_id": "1",
        "private_key": private_key,
        "client_email": email,
        "client_id": "1",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{email}",
    }
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_sheet():
    sheet_id = current_app.config["GOOGLE_SHEET_ID"]
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID not set")
    client = get_gspread_client()
    return client.open_by_key(sheet_id).sheet1


def _find_or_create_catalog(model, nombre, extra=None):
    if not nombre:
        return None
    name = normalize_name(nombre)
    if not name:
        return None
    obj = model.query.filter_by(nombre=name).first()
    if not obj:
        try:
            kwargs = {"nombre": name}
            if extra:
                kwargs.update(extra)
            obj = model(**kwargs)
            db.session.add(obj)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            obj = model.query.filter_by(nombre=name).first()
    return obj


def pull_from_sheet():
    # 🔧 INICIALIZAR LAS VARIABLES AQUÍ
    imported = 0
    updated = 0
    
    # Asegurar que los estatus base existen
    try:
        seed_estatuses()
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error seeding estatus: {e}")
        db.session.rollback()
    
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows:
        return {"imported": 0, "updated": 0, "total": 0}

    for sheet_idx, row in enumerate(all_rows):
        if sheet_idx == 0:
            continue  # skip header

        def cell(idx):
            return row[idx].strip() if len(row) > idx else ""

        nombre = cell(0)
        apellido = cell(1)
        cedula = cell(2)
        sexo = cell(3)
        edad_raw = cell(4)
        telefono = cell(5)
        estado_salud = cell(6)
        tiene_familiar_raw = cell(7)
        nombre_familiar = cell(8)
        estatus_raw = cell(9)
        observaciones = cell(10)
        estado_nombre = cell(11)
        hospital_nombre = cell(12)
        area_nombre = cell(13)

        if not nombre and not apellido and not cedula:
            continue

        edad = None
        if edad_raw and edad_raw.replace(".", "").replace(",", "").isdigit():
            try:
                edad = int(float(edad_raw))
            except (ValueError, TypeError):
                pass

        tiene_familiar = tiene_familiar_raw.upper() in (
            "S",
            "SÍ",
            "SI",
            "YES",
            "TRUE",
            "1",
        )

        # Crear o buscar estatus
        estatus_obj = None
        if estatus_raw:
            estatus_norm = normalize_name(estatus_raw)
            if estatus_norm:
                estatus_obj = Estatus.query.filter_by(nombre=estatus_norm).first()
                if not estatus_obj:
                    try:
                        estatus_obj = Estatus(nombre=estatus_norm)
                        db.session.add(estatus_obj)
                        db.session.flush()
                        current_app.logger.info(f"✅ Nuevo estatus creado: {estatus_norm}")
                    except IntegrityError:
                        db.session.rollback()
                        estatus_obj = Estatus.query.filter_by(nombre=estatus_norm).first()
        
        estatus_nombre = estatus_obj.nombre if estatus_obj else ""

        estado_obj = _find_or_create_catalog(Estado, estado_nombre)
        hospital_obj = _find_or_create_catalog(
            Hospital,
            hospital_nombre,
            {"estado_id": estado_obj.id} if estado_obj else None,
        )
        area_obj = _find_or_create_catalog(Area, area_nombre)
        db.session.flush()

        sheet_row_num = sheet_idx + 1

        person = None
        if cedula:
            person = Person.query.filter_by(cedula=cedula).first()
        if not person:
            person = Person.query.filter_by(sheet_row=sheet_row_num).first()

        if person:
            person.nombre = nombre or person.nombre
            person.apellido = apellido or person.apellido
            if cedula:
                person.cedula = cedula
            person.sexo = sexo or person.sexo
            person.edad = edad or person.edad
            person.telefono = telefono or person.telefono
            person.estado_salud = estado_salud or person.estado_salud
            person.tiene_familiar = tiene_familiar
            person.nombre_familiar = nombre_familiar or person.nombre_familiar
            if estatus_nombre:
                person.estatus = estatus_nombre
            person.observaciones = observaciones or person.observaciones
            person.estado_id = estado_obj.id if estado_obj else person.estado_id
            person.hospital_id = hospital_obj.id if hospital_obj else person.hospital_id
            person.area_id = area_obj.id if area_obj else person.area_id
            person.sheet_row = sheet_row_num
            updated += 1
        else:
            person = Person(
                nombre=nombre,
                apellido=apellido,
                cedula=cedula if cedula else None,
                sexo=sexo,
                edad=edad,
                telefono=telefono,
                estado_salud=estado_salud,
                tiene_familiar=tiene_familiar,
                nombre_familiar=nombre_familiar,
                estatus=estatus_nombre,
                observaciones=observaciones,
                estado_id=estado_obj.id if estado_obj else None,
                hospital_id=hospital_obj.id if hospital_obj else None,
                area_id=area_obj.id if area_obj else None,
                sheet_row=sheet_row_num,
                fecha_registro=datetime.utcnow(),
            )
            db.session.add(person)
            imported += 1

    db.session.commit()
    return {"imported": imported, "updated": updated, "total": len(all_rows) - 1}


def push_to_sheet():
    sheet = _get_sheet()
    persons = Person.query.order_by(Person.id.asc()).all()
    rows = [HEADERS]
    for idx, p in enumerate(persons, start=2):
        p.sheet_row = idx
        rows.append(
            [
                p.nombre or "",
                p.apellido or "",
                p.cedula or "",
                p.sexo or "",
                str(p.edad) if p.edad is not None else "",
                p.telefono or "",
                p.estado_salud or "",
                "S" if p.tiene_familiar else "N",
                p.nombre_familiar or "",
                p.estatus or "",
                p.observaciones or "",
                p.estado.nombre if p.estado else "",
                p.hospital.nombre if p.hospital else "",
                p.area.nombre if p.area else "",
            ]
        )

    sheet.clear()
    sheet.update(rows, value_input_option="USER_ENTERED")
    db.session.commit()
    return {"written": len(persons)}


def sync_all():
    pull = pull_from_sheet()
    push = push_to_sheet()

    log = SyncLog(
        imported=pull["imported"],
        duplicated=pull["total"] - pull["imported"] - pull["updated"],
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()

    return {
        "imported": pull["imported"],
        "updated": pull["updated"],
        "pushed": push["written"],
        "total_in_sheet": pull["total"],
    }


# Legacy entry point for the scheduler
def sync_google_sheet():
    return pull_from_sheet()