from flask import Blueprint, render_template, request, jsonify
from .models import db, Person, Estado, Hospital, Area, AuditLog, display_name

public_bp = Blueprint("public", __name__, url_prefix="/public")


def _stats():
    total_persons = Person.query.count()
    total_hospitals = Hospital.query.count()
    total_areas = Area.query.count()

    last_import = (
        AuditLog.query.filter_by(action="import", target_type="Person")
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    last_update = (
        last_import.created_at.strftime("%d/%m/%Y %H:%M") if last_import else None
    )

    return {
        "total_persons": total_persons,
        "total_hospitals": total_hospitals,
        "total_areas": total_areas,
        "last_update": last_update,
    }


@public_bp.route("/")
def index():
    return render_template(
        "public/search.html",
        estados=Estado.query.all(),
        areas=Area.query.all(),
        **_stats(),
    )


@public_bp.route("/search")
def search():
    return render_template(
        "public/search.html",
        estados=Estado.query.all(),
        areas=Area.query.all(),
        **_stats(),
    )


@public_bp.route("/api/persons")
def api_persons():
    query = Person.query
    nombre = request.args.get("nombre", "").strip()
    estado_id = request.args.get("estado_id", "").strip()
    hospital_id = request.args.get("hospital_id", "").strip()
    area_id = request.args.get("area_id", "").strip()

    if nombre:
        query = query.filter(
            Person.nombre.ilike(f"%{nombre}%") | Person.apellido.ilike(f"%{nombre}%")
        )
    if estado_id and estado_id.isdigit():
        query = query.filter_by(estado_id=int(estado_id))
    if hospital_id and hospital_id.isdigit():
        query = query.filter_by(hospital_id=int(hospital_id))
    if area_id and area_id.isdigit():
        query = query.filter_by(area_id=int(area_id))

    persons = query.order_by(Person.fecha_registro.desc()).all()
    data = []
    for p in persons:

        def si(val):
            return val if val and str(val).strip() else "sin información"

        data.append(
            {
                "id": p.id,
                "nombre": p.nombre or "sin información",
                "apellido": si(p.apellido),
                "cedula": si(p.cedula),
                "edad": si(p.edad),
                "sexo": si(p.sexo),
                "estado": display_name(p.estado.nombre)
                if p.estado
                else "sin información",
                "hospital": display_name(p.hospital.nombre)
                if p.hospital
                else "sin información",
                "area": display_name(p.area.nombre) if p.area else "sin información",
                "estado_salud": si(p.estado_salud),
                "tiene_familiar": "Sí" if p.tiene_familiar else "No",
                "nombre_familiar": si(p.nombre_familiar),
                "telefono": si(p.telefono),
                "estatus": display_name(p.estatus) if p.estatus else "sin información",
                "observaciones": si(p.observaciones),
                "fecha_registro": p.fecha_registro.strftime("%Y-%m-%d %H:%M")
                if p.fecha_registro
                else "sin información",
            }
        )
    return jsonify(data)
