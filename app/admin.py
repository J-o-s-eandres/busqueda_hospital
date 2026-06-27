import csv
import io
import os
from datetime import datetime

import pandas as pd
from flask import (
    Blueprint,
    render_template,
    request,
    Response,
    redirect,
    url_for,
    flash,
    jsonify,
    current_app,
)
from flask_login import login_required, login_user, logout_user, current_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
from .models import (
    db,
    User,
    Person,
    Estado,
    Hospital,
    Area,
    Estatus,
    AuditLog,
    log_action,
    require_role,
    normalize_name,
    display_name,
    seed_estatuses,
)
from .forms import UserForm, PersonForm

ALLOWED_EXCEL_EXTENSIONS = {".xlsx"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_excel_file(file):
    if not file or file.filename == "":
        return False, "Selecciona un archivo Excel"
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXCEL_EXTENSIONS:
        return False, "Solo se permiten archivos .xlsx"
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return (
            False,
            f"El archivo excede el tamaño máximo de {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )
    return True, ""


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
def dashboard():
    total_persons = Person.query.count()
    total_estados = Estado.query.count()
    total_hospitals = Hospital.query.count()
    total_areas = Area.query.count()

    persons_per_hospital = (
        db.session.query(Hospital.nombre, func.count(Person.id))
        .outerjoin(Person, Person.hospital_id == Hospital.id)
        .group_by(Hospital.id)
        .order_by(func.count(Person.id).desc())
        .all()
    )
    persons_per_estatus = (
        db.session.query(Person.estatus, func.count(Person.id))
        .group_by(Person.estatus)
        .all()
    )
    persons_per_estado = (
        db.session.query(Estado.nombre, func.count(Person.id))
        .outerjoin(Person, Person.estado_id == Estado.id)
        .group_by(Estado.id)
        .order_by(func.count(Person.id).desc())
        .all()
    )
    persons_per_area = (
        db.session.query(Area.nombre, func.count(Person.id))
        .outerjoin(Person, Person.area_id == Area.id)
        .group_by(Area.id)
        .order_by(func.count(Person.id).desc())
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        counts={
            "persons": total_persons,
            "estados": total_estados,
            "hospitals": total_hospitals,
            "areas": total_areas,
        },
        persons_per_hospital=[
            {"label": r[0] or "Sin hospital", "count": r[1]}
            for r in persons_per_hospital
        ],
        persons_per_estatus=[
            {"label": r[0] or "Sin estatus", "count": r[1]} for r in persons_per_estatus
        ],
        persons_per_estado=[
            {"label": r[0] or "Sin estado", "count": r[1]} for r in persons_per_estado
        ],
        persons_per_area=[
            {"label": r[0] or "Sin área", "count": r[1]} for r in persons_per_area
        ],
    )


@admin_bp.route("/export/csv")
@login_required
def export_csv():
    require_role("admin")
    columns = [
        "id",
        "nombre",
        "apellido",
        "cedula",
        "telefono",
        "hospital",
        "area",
        "estado_salud",
        "tiene_familiar",
        "estatus",
    ]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for person in Person.query.all():
        writer.writerow(
            [
                person.id,
                person.nombre or "",
                person.apellido or "",
                person.cedula or "",
                person.telefono or "",
                person.hospital.nombre if person.hospital else "",
                person.area.nombre if person.area else "",
                person.estado_salud or "",
                "Sí" if person.tiene_familiar else "No",
                person.estatus or "",
            ]
        )

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=persons.csv"},
    )


@admin_bp.route("/api/stats")
@login_required
def api_stats():
    persons_per_hospital = (
        db.session.query(Hospital.nombre, func.count(Person.id))
        .outerjoin(Person, Person.hospital_id == Hospital.id)
        .group_by(Hospital.id)
        .all()
    )
    persons_per_estatus = (
        db.session.query(Person.estatus, func.count(Person.id))
        .group_by(Person.estatus)
        .all()
    )
    return jsonify(
        {
            "total_persons": Person.query.count(),
            "total_hospitals": Hospital.query.count(),
            "total_estados": Estado.query.count(),
            "persons_per_hospital": [
                {"label": r[0] or "Sin hospital", "count": r[1]}
                for r in persons_per_hospital
            ],
            "persons_per_estatus": [
                {"label": r[0] or "Sin estatus", "count": r[1]}
                for r in persons_per_estatus
            ],
        }
    )


@admin_bp.route("/users")
@login_required
def users():
    require_role("admin", "helper")
    all_users = User.query.all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
def user_form():
    require_role("admin", "helper")
    form = UserForm()
    user_id = request.args.get("user_id", type=int)
    user = User.query.get(user_id) if user_id else None

    if user_id and current_user.role != "admin":
        flash("Solo el administrador puede editar usuarios", "danger")
        return redirect(url_for("admin.users"))

    if form.validate_on_submit():
        if user:
            if current_user.role != "admin":
                flash("Solo el administrador puede editar usuarios", "danger")
                return redirect(url_for("admin.users"))
            user.username = form.username.data
            user.nombre = form.nombre.data
            user.apellido = form.apellido.data
            user.role = form.role.data
            if form.password.data:
                user.set_password(form.password.data)
            log_action(
                current_user,
                "update",
                "User",
                user.id,
                f"Editó usuario {user.username}",
            )
            flash("Usuario actualizado", "success")
        else:
            if current_user.role != "admin":
                flash("Solo el administrador puede crear usuarios", "danger")
                return redirect(url_for("admin.users"))
            if not form.password.data:
                flash("La contraseña es obligatoria para nuevos usuarios", "danger")
                return render_template("admin/user_form.html", form=form, user=user)
            existing = User.query.filter_by(username=form.username.data).first()
            if existing:
                flash("El nombre de usuario ya existe", "danger")
                return render_template("admin/user_form.html", form=form, user=user)
            user = User(
                username=form.username.data,
                nombre=form.nombre.data,
                apellido=form.apellido.data,
                role=form.role.data,
                active=True,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            log_action(
                current_user, "create", "User", None, f"Creó usuario {user.username}"
            )
            flash("Usuario creado", "success")
        db.session.commit()
        return redirect(url_for("admin.users"))

    if user:
        form.username.data = user.username
        form.nombre.data = user.nombre
        form.apellido.data = user.apellido
        form.role.data = user.role

    return render_template("admin/user_form.html", form=form, user=user)


@admin_bp.route("/users/<int:user_id>/delete")
@login_required
def delete_user(user_id):
    require_role("admin")
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("No puedes eliminarte a ti mismo", "danger")
        return redirect(url_for("admin.users"))
    log_action(
        current_user, "delete", "User", user.id, f"Eliminó usuario {user.username}"
    )
    db.session.delete(user)
    db.session.commit()
    flash("Usuario eliminado", "success")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# CRUD Hospitales
# ---------------------------------------------------------------------------
@admin_bp.route("/hospitals")
@login_required
def hospitals():
    require_role("admin", "helper")
    all_items = Hospital.query.order_by(Hospital.nombre).all()
    return render_template("admin/hospital_list.html", items=all_items)


@admin_bp.route("/hospitals/new", methods=["GET", "POST"])
@login_required
def hospital_new():
    require_role("admin", "helper")
    error = None
    if request.method == "POST":
        nombre = normalize_name(request.form.get("nombre", ""))
        if len(nombre) < 3:
            error = "El nombre del hospital debe tener al menos 3 caracteres"
        elif Hospital.query.filter_by(nombre=nombre).first():
            error = f"El hospital '{display_name(nombre)}' ya existe"
        else:
            h = Hospital(
                nombre=nombre, estado_id=request.form.get("estado_id", type=int) or None
            )
            db.session.add(h)
            db.session.commit()
            log_action(
                current_user,
                "create",
                "Hospital",
                h.id,
                f"Creó hospital {display_name(nombre)}",
            )
            flash(f"Hospital '{display_name(nombre)}' creado", "success")
            return redirect(url_for("admin.hospitals"))
    estados = Estado.query.order_by(Estado.nombre).all()
    return render_template(
        "admin/hospital_form.html", item=None, error=error, estados=estados
    )


@admin_bp.route("/hospitals/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def hospital_edit(item_id):
    require_role("admin", "helper")
    h = Hospital.query.get_or_404(item_id)
    error = None
    if request.method == "POST":
        nombre = normalize_name(request.form.get("nombre", ""))
        if len(nombre) < 3:
            error = "El nombre del hospital debe tener al menos 3 caracteres"
        elif nombre != h.nombre and Hospital.query.filter_by(nombre=nombre).first():
            error = f"El hospital '{display_name(nombre)}' ya existe"
        else:
            h.nombre = nombre
            h.estado_id = request.form.get("estado_id", type=int) or None
            db.session.commit()
            log_action(
                current_user,
                "update",
                "Hospital",
                h.id,
                f"Editó hospital {display_name(nombre)}",
            )
            flash(f"Hospital '{display_name(nombre)}' actualizado", "success")
            return redirect(url_for("admin.hospitals"))
    estados = Estado.query.order_by(Estado.nombre).all()
    return render_template(
        "admin/hospital_form.html", item=h, error=error, estados=estados
    )


@admin_bp.route("/hospitals/<int:item_id>/delete")
@login_required
def hospital_delete(item_id):
    require_role("admin")
    h = Hospital.query.get_or_404(item_id)
    log_action(
        current_user,
        "delete",
        "Hospital",
        h.id,
        f"Eliminó hospital {display_name(h.nombre)}",
    )
    db.session.delete(h)
    db.session.commit()
    flash(f"Hospital '{display_name(h.nombre)}' eliminado", "success")
    return redirect(url_for("admin.hospitals"))


# ---------------------------------------------------------------------------
# CRUD Áreas
# ---------------------------------------------------------------------------
@admin_bp.route("/areas")
@login_required
def areas():
    require_role("admin", "helper")
    all_items = Area.query.order_by(Area.nombre).all()
    return render_template("admin/area_list.html", items=all_items)


@admin_bp.route("/areas/new", methods=["GET", "POST"])
@login_required
def area_new():
    require_role("admin", "helper")
    error = None
    if request.method == "POST":
        nombre = normalize_name(request.form.get("nombre", ""))
        if len(nombre) < 3:
            error = "El nombre del área debe tener al menos 3 caracteres"
        elif Area.query.filter_by(nombre=nombre).first():
            error = f"El área '{display_name(nombre)}' ya existe"
        else:
            a = Area(nombre=nombre)
            db.session.add(a)
            db.session.commit()
            log_action(
                current_user,
                "create",
                "Area",
                a.id,
                f"Creó área {display_name(nombre)}",
            )
            flash(f"Área '{display_name(nombre)}' creada", "success")
            return redirect(url_for("admin.areas"))
    return render_template("admin/area_form.html", item=None, error=error)


@admin_bp.route("/areas/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def area_edit(item_id):
    require_role("admin", "helper")
    a = Area.query.get_or_404(item_id)
    error = None
    if request.method == "POST":
        nombre = normalize_name(request.form.get("nombre", ""))
        if len(nombre) < 3:
            error = "El nombre del área debe tener al menos 3 caracteres"
        elif nombre != a.nombre and Area.query.filter_by(nombre=nombre).first():
            error = f"El área '{display_name(nombre)}' ya existe"
        else:
            a.nombre = nombre
            db.session.commit()
            log_action(
                current_user,
                "update",
                "Area",
                a.id,
                f"Editó área {display_name(nombre)}",
            )
            flash(f"Área '{display_name(nombre)}' actualizada", "success")
            return redirect(url_for("admin.areas"))
    return render_template("admin/area_form.html", item=a, error=error)


@admin_bp.route("/areas/<int:item_id>/delete")
@login_required
def area_delete(item_id):
    require_role("admin")
    a = Area.query.get_or_404(item_id)
    log_action(
        current_user, "delete", "Area", a.id, f"Eliminó área {display_name(a.nombre)}"
    )
    db.session.delete(a)
    db.session.commit()
    flash(f"Área '{display_name(a.nombre)}' eliminada", "success")
    return redirect(url_for("admin.areas"))


# ---------------------------------------------------------------------------
# CRUD Estatus
# ---------------------------------------------------------------------------
@admin_bp.route("/estatuses")
@login_required
def estatuses():
    require_role("admin", "helper")
    all_items = Estatus.query.order_by(Estatus.nombre).all()
    return render_template("admin/estatus_list.html", items=all_items)


@admin_bp.route("/estatuses/new", methods=["GET", "POST"])
@login_required
def estatus_new():
    require_role("admin", "helper")
    error = None
    if request.method == "POST":
        nombre = normalize_name(request.form.get("nombre", ""))
        if len(nombre) < 3:
            error = "El nombre del estatus debe tener al menos 3 caracteres"
        elif Estatus.query.filter_by(nombre=nombre).first():
            error = f"El estatus '{display_name(nombre)}' ya existe"
        else:
            s = Estatus(nombre=nombre)
            db.session.add(s)
            db.session.commit()
            log_action(
                current_user,
                "create",
                "Estatus",
                s.id,
                f"Creó estatus {display_name(nombre)}",
            )
            flash(f"Estatus '{display_name(nombre)}' creado", "success")
            return redirect(url_for("admin.estatuses"))
    return render_template("admin/estatus_form.html", item=None, error=error)


@admin_bp.route("/estatuses/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def estatus_edit(item_id):
    require_role("admin", "helper")
    s = Estatus.query.get_or_404(item_id)
    error = None
    if request.method == "POST":
        nombre = normalize_name(request.form.get("nombre", ""))
        if len(nombre) < 3:
            error = "El nombre del estatus debe tener al menos 3 caracteres"
        elif nombre != s.nombre and Estatus.query.filter_by(nombre=nombre).first():
            error = f"El estatus '{display_name(nombre)}' ya existe"
        else:
            s.nombre = nombre
            db.session.commit()
            log_action(
                current_user,
                "update",
                "Estatus",
                s.id,
                f"Editó estatus {display_name(nombre)}",
            )
            flash(f"Estatus '{display_name(nombre)}' actualizado", "success")
            return redirect(url_for("admin.estatuses"))
    return render_template("admin/estatus_form.html", item=s, error=error)


@admin_bp.route("/estatuses/<int:item_id>/delete")
@login_required
def estatus_delete(item_id):
    require_role("admin")
    s = Estatus.query.get_or_404(item_id)
    log_action(
        current_user,
        "delete",
        "Estatus",
        s.id,
        f"Eliminó estatus {display_name(s.nombre)}",
    )
    db.session.delete(s)
    db.session.commit()
    flash(f"Estatus '{display_name(s.nombre)}' eliminado", "success")
    return redirect(url_for("admin.estatuses"))


# ---------------------------------------------------------------------------
# Persons
# ---------------------------------------------------------------------------
@admin_bp.route("/persons")
@login_required
def persons():
    estados = Estado.query.order_by(Estado.nombre).all()
    areas = Area.query.order_by(Area.nombre).all()
    estatuses = Estatus.query.order_by(Estatus.nombre).all()
    return render_template(
        "admin/persons.html",
        estados=estados,
        areas=areas,
        estatuses=estatuses,
        display_name=display_name,
    )


@admin_bp.route("/persons/upload", methods=["GET", "POST"])
@login_required
def upload_persons():
    require_role("admin", "helper")
    if request.method == "POST":
        file = request.files.get("file")
        ok, err = validate_excel_file(file)
        if not ok:
            flash(err, "danger")
            return render_template("admin/upload.html")

        try:
            df = pd.read_excel(file, dtype=str)
        except Exception as e:
            flash(f"Error al leer el archivo: {e}", "danger")
            return render_template("admin/upload.html")

        if df.empty:
            flash("El archivo está vacío", "danger")
            return render_template("admin/upload.html")

        required_cols = {"nombre", "apellido", "cedula"}
        given_cols = set(df.columns.str.strip().str.lower())
        if not required_cols.issubset(given_cols):
            flash(
                "Columnas requeridas: nombre, apellido, cedula. "
                "Columnas opcionales: sexo, edad, telefono, estado_salud, "
                "tiene_familiar, nombre_familiar, estatus, observaciones, "
                "estado, hospital, area — usa la primer fila como encabezado. "
                "Usa 'N' en cedula si la persona no tiene cédula conocida.",
                "danger",
            )
            return render_template("admin/upload.html")

        col_map = {c.strip().lower(): c.strip() for c in df.columns}
        imported = 0
        updated = 0
        skipped = 0
        errors = []

        for idx, row in df.iterrows():
            nombre = str(row.get(col_map.get("nombre", ""), "")).strip()
            apellido = str(row.get(col_map.get("apellido", ""), "")).strip()
            cedula_raw = str(row.get(col_map.get("cedula", ""), "")).strip()

            if (
                not nombre
                or not apellido
                or not cedula_raw
                or cedula_raw.upper() == "NAN"
            ):
                skipped += 1
                continue

            cedula = None if cedula_raw.upper() == "N" else cedula_raw
            existing = None
            if cedula:
                existing = Person.query.filter_by(cedula=cedula).first()
            if not existing and not cedula:
                existing = Person.query.filter(
                    Person.nombre.ilike(nombre),
                    Person.apellido.ilike(apellido),
                    Person.cedula.is_(None)
                ).first()

            def get_val(key):
                raw = row.get(col_map.get(key, ""))
                if pd.isna(raw):
                    return ""
                return str(raw).strip()

            def get_int(key):
                raw = row.get(col_map.get(key, ""))
                if pd.isna(raw):
                    return None
                try:
                    return int(float(str(raw).strip()))
                except (ValueError, TypeError):
                    return None

            def get_bool(key):
                raw = row.get(col_map.get(key, ""))
                if pd.isna(raw):
                    return False
                return str(raw).strip().upper() == "S"

            sexo_raw = get_val("sexo")
            sexo = {"M": "Masculino", "F": "Femenino"}.get(sexo_raw.upper(), sexo_raw) if sexo_raw else ""
            telefono = get_val("telefono")
            estado_salud = get_val("estado_salud")
            nombre_familiar = get_val("nombre_familiar")
            observaciones = get_val("observaciones")
            edad = get_int("edad")
            tiene_familiar = get_bool("tiene_familiar")

            estatus = normalize_name(get_val("estatus"))
            if estatus:
                try:
                    if not Estatus.query.filter_by(nombre=estatus).first():
                        db.session.add(Estatus(nombre=estatus))
                        db.session.flush()
                except IntegrityError:
                    db.session.rollback()

            estado_nombre = get_val("estado")
            hospital_nombre = normalize_name(get_val("hospital"))
            area_nombre = normalize_name(get_val("area"))

            estado_obj = None
            if estado_nombre:
                estado_obj = Estado.query.filter_by(nombre=estado_nombre).first()
                if not estado_obj:
                    try:
                        estado_obj = Estado(nombre=estado_nombre)
                        db.session.add(estado_obj)
                        db.session.flush()
                    except IntegrityError:
                        db.session.rollback()
                        estado_obj = Estado.query.filter_by(
                            nombre=estado_nombre
                        ).first()

            hospital_obj = None
            if hospital_nombre:
                hospital_obj = Hospital.query.filter_by(nombre=hospital_nombre).first()
                if not hospital_obj:
                    try:
                        hospital_obj = Hospital(
                            nombre=hospital_nombre,
                            estado_id=estado_obj.id if estado_obj else None,
                        )
                        db.session.add(hospital_obj)
                        db.session.flush()
                    except IntegrityError:
                        db.session.rollback()
                        hospital_obj = Hospital.query.filter_by(
                            nombre=hospital_nombre
                        ).first()

            area_obj = None
            if area_nombre:
                area_obj = Area.query.filter_by(nombre=area_nombre).first()
                if not area_obj:
                    try:
                        area_obj = Area(nombre=area_nombre)
                        db.session.add(area_obj)
                        db.session.flush()
                    except IntegrityError:
                        db.session.rollback()
                        area_obj = Area.query.filter_by(nombre=area_nombre).first()

            db.session.flush()

            data = dict(
                nombre=nombre,
                apellido=apellido,
                cedula=cedula,
                sexo=sexo,
                edad=edad,
                telefono=telefono,
                estado_salud=estado_salud,
                tiene_familiar=tiene_familiar,
                nombre_familiar=nombre_familiar,
                estatus=estatus,
                observaciones=observaciones,
                estado_id=estado_obj.id if estado_obj else None,
                hospital_id=hospital_obj.id if hospital_obj else None,
                area_id=area_obj.id if area_obj else None,
            )

            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                data["fecha_registro"] = datetime.utcnow()
                db.session.add(Person(**data))
                imported += 1

        db.session.commit()

        log_action(
            current_user,
            "import",
            "Person",
            None,
            f"Importación Excel: {imported} nuevas, {updated} actualizadas, {skipped} omitidas",
        )

        msg = f"Importadas {imported} nuevas, actualizadas {updated}, omitidas {skipped} filas inválidas."
        if errors:
            msg += f" {len(errors)} errores."
        flash(msg, "success" if not errors else "warning")
        return redirect(url_for("admin.persons"))

    return render_template("admin/upload.html")


@admin_bp.route("/api/persons/preview-upload", methods=["POST"])
@login_required
def api_preview_upload():
    require_role("admin", "helper")
    file = request.files.get("file")
    ok, err = validate_excel_file(file)
    if not ok:
        return jsonify({"error": err}), 400

    try:
        df = pd.read_excel(file, dtype=str)
    except Exception as e:
        return jsonify({"error": f"Error al leer el archivo: {e}"}), 400

    if df.empty:
        return jsonify({"error": "El archivo está vacío"}), 400

    required_cols = {"nombre", "apellido", "cedula"}
    given_cols = set(df.columns.str.strip().str.lower())
    if not required_cols.issubset(given_cols):
        return jsonify(
            {"error": "Faltan columnas requeridas: nombre, apellido, cedula"}
        ), 400

    col_map = {c.strip().lower(): c.strip() for c in df.columns}

    # Load valid estatuses from DB
    estatus_map = {s.nombre: True for s in Estatus.query.all()}

    def get_val(row, key):
        raw = row.get(col_map.get(key, ""))
        if pd.isna(raw):
            return ""
        return str(raw).strip()

    rows = []
    valid_count = 0
    invalid_count = 0

    for idx, row in df.iterrows():
        row_errors = []

        nombre = get_val(row, "nombre")
        apellido = get_val(row, "apellido")
        cedula_raw = get_val(row, "cedula")

        if not nombre:
            row_errors.append("nombre es requerido")
        if not apellido:
            row_errors.append("apellido es requerido")
        if not cedula_raw or cedula_raw.upper() == "NAN":
            row_errors.append("cedula es requerida (usa 'N' si se desconoce)")

        edad_raw = get_val(row, "edad")
        if edad_raw:
            try:
                int(float(edad_raw))
            except (ValueError, TypeError):
                row_errors.append("edad debe ser un número entero")

        sexo_raw = get_val(row, "sexo")
        sexo = {"M": "Masculino", "F": "Femenino"}.get(sexo_raw.upper(), sexo_raw) if sexo_raw else ""
        if sexo and sexo not in ("Masculino", "Femenino"):
            row_errors.append("sexo debe ser 'Masculino', 'Femenino', 'M' o 'F'")

        estatus = normalize_name(get_val(row, "estatus"))
        if estatus and estatus not in estatus_map:
            row_errors.append(
                f"estatus inválido: '{estatus}' — usa un estatus registrado"
            )

        hospital_nombre = normalize_name(get_val(row, "hospital"))
        if hospital_nombre and len(hospital_nombre) < 3:
            row_errors.append("hospital debe tener al menos 3 caracteres")

        area_nombre = normalize_name(get_val(row, "area"))
        if area_nombre and len(area_nombre) < 3:
            row_errors.append("area debe tener al menos 3 caracteres")

        tiene_familiar = get_val(row, "tiene_familiar")
        if tiene_familiar and tiene_familiar.upper() not in ("S", "N"):
            row_errors.append("tiene_familiar debe ser 'S' o 'N'")

        cedula_display = cedula_raw if cedula_raw.upper() != "N" else "(sin cédula)"

        if not row_errors:
            preview_cedula = None if cedula_raw.upper() == "N" else cedula_raw
            preview_existing = None
            if preview_cedula:
                preview_existing = Person.query.filter_by(cedula=preview_cedula).first()
            if not preview_existing and not preview_cedula and nombre and apellido:
                preview_existing = Person.query.filter(
                    Person.nombre.ilike(nombre),
                    Person.apellido.ilike(apellido),
                    Person.cedula.is_(None)
                ).first()
            action = "Actualizar" if preview_existing else "Crear"
        else:
            action = "—"

        rows.append(
            {
                "row": idx + 2,
                "nombre": nombre or "(vacío)",
                "apellido": apellido or "(vacío)",
                "cedula": cedula_display,
                "sexo": sexo,
                "edad": edad_raw,
                "telefono": get_val(row, "telefono"),
                "estado_salud": get_val(row, "estado_salud"),
                "tiene_familiar": tiene_familiar,
                "nombre_familiar": get_val(row, "nombre_familiar"),
                "estatus": estatus,
                "observaciones": get_val(row, "observaciones"),
                "estado": get_val(row, "estado"),
                "hospital": hospital_nombre,
                "area": area_nombre,
                "action": action,
                "errors": row_errors,
                "valid": len(row_errors) == 0,
            }
        )

        if row_errors:
            invalid_count += 1
        else:
            valid_count += 1

    return jsonify(
        {
            "total": len(rows),
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "rows": rows,
            "has_errors": invalid_count > 0,
        }
    )


@admin_bp.route("/persons/new", methods=["GET", "POST"])
@login_required
def person_form():
    require_role("admin", "helper")
    person_id = request.args.get("person_id", type=int)
    person = Person.query.get(person_id) if person_id else None
    estados = Estado.query.order_by(Estado.nombre).all()
    hospitals = Hospital.query.order_by(Hospital.nombre).all()
    areas = Area.query.order_by(Area.nombre).all()
    estatuses = Estatus.query.order_by(Estatus.nombre).all()
    if not estatuses:
        seed_estatuses()
        estatuses = Estatus.query.order_by(Estatus.nombre).all()

    if request.method == "POST":
        if person:
            person.nombre = request.form["nombre"]
            person.apellido = request.form.get("apellido", "")
            person.cedula = request.form.get("cedula", "")
            person.sexo = request.form.get("sexo", "")
            person.edad = request.form.get("edad", type=int)
            person.telefono = request.form.get("telefono", "")
            person.estado_salud = request.form.get("estado_salud", "")
            person.tiene_familiar = request.form.get("tiene_familiar") == "on"
            person.nombre_familiar = request.form.get("nombre_familiar", "")
            person.estatus = normalize_name(
                request.form.get("estatus", "hospitalizado")
            )
            person.observaciones = request.form.get("observaciones", "")
            person.estado_id = request.form.get("estado_id", type=int) or None
            person.hospital_id = request.form.get("hospital_id", type=int) or None
            person.area_id = request.form.get("area_id", type=int) or None
            log_action(
                current_user,
                "update",
                "Person",
                person.id,
                f"Editó persona {person.nombre} {person.apellido}",
            )
            flash("Persona actualizada", "success")
        else:
            person = Person(
                nombre=request.form["nombre"],
                apellido=request.form.get("apellido", ""),
                cedula=request.form.get("cedula", ""),
                sexo=request.form.get("sexo", ""),
                edad=request.form.get("edad", type=int),
                telefono=request.form.get("telefono", ""),
                estado_salud=request.form.get("estado_salud", ""),
                tiene_familiar=request.form.get("tiene_familiar") == "on",
                nombre_familiar=request.form.get("nombre_familiar", ""),
                estatus=normalize_name(request.form.get("estatus", "hospitalizado")),
                observaciones=request.form.get("observaciones", ""),
                estado_id=request.form.get("estado_id", type=int) or None,
                hospital_id=request.form.get("hospital_id", type=int) or None,
                area_id=request.form.get("area_id", type=int) or None,
            )
            db.session.add(person)
            log_action(
                current_user,
                "create",
                "Person",
                None,
                f"Creó persona {person.nombre} {person.apellido}",
            )
            flash("Persona creada", "success")
        db.session.commit()
        return redirect(url_for("admin.persons"))

    return render_template(
        "admin/person_form.html",
        person=person,
        estados=estados,
        hospitals=hospitals,
        areas=areas,
        estatuses=estatuses,
        display_name=display_name,
    )


@admin_bp.route("/persons/<int:person_id>/delete")
@login_required
def delete_person(person_id):
    require_role("admin", "helper")
    person = Person.query.get_or_404(person_id)
    log_action(
        current_user,
        "delete",
        "Person",
        person.id,
        f"Eliminó persona {person.nombre} {person.apellido}",
    )
    db.session.delete(person)
    db.session.commit()
    flash("Persona eliminada", "success")
    return redirect(url_for("admin.persons"))


@admin_bp.route("/api/persons/list")
@login_required
def api_persons_list():
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
        data.append({
            "id": p.id,
            "nombre": p.nombre or "",
            "apellido": p.apellido or "",
            "cedula": p.cedula or "",
            "edad": p.edad,
            "sexo": p.sexo or "",
            "telefono": p.telefono or "",
            "estado": p.estado.nombre if p.estado else "",
            "hospital": p.hospital.nombre if p.hospital else "",
            "area": p.area.nombre if p.area else "",
            "estatus": p.estatus or "",
            "tiene_familiar": "Sí" if p.tiene_familiar else "No",
            "estado_id": p.estado_id,
            "hospital_id": p.hospital_id,
            "area_id": p.area_id,
        })
    return jsonify(data)


@admin_bp.route("/api/persons/<int:person_id>")
@login_required
def api_person(person_id):
    p = db.session.get(Person, person_id)
    if not p:
        return jsonify({"error": "Persona no encontrada"}), 404
    return jsonify(
        {
            "id": p.id,
            "nombre": p.nombre,
            "apellido": p.apellido,
            "cedula": p.cedula,
            "sexo": p.sexo,
            "edad": p.edad,
            "telefono": p.telefono,
            "estado_salud": p.estado_salud,
            "tiene_familiar": p.tiene_familiar,
            "nombre_familiar": p.nombre_familiar,
            "estatus": p.estatus,
            "observaciones": p.observaciones,
            "estado_id": p.estado_id,
            "hospital_id": p.hospital_id,
            "area_id": p.area_id,
        }
    )


@admin_bp.route("/api/persons/<int:person_id>/edit", methods=["POST"])
@login_required
def api_edit_person(person_id):
    require_role("admin", "helper")
    p = Person.query.get_or_404(person_id)
    p.nombre = request.form.get("nombre", p.nombre)
    p.apellido = request.form.get("apellido", p.apellido)
    p.cedula = request.form.get("cedula", p.cedula)
    p.sexo = request.form.get("sexo", p.sexo)
    p.edad = request.form.get("edad", type=int) or p.edad
    p.telefono = request.form.get("telefono", p.telefono)
    p.estado_salud = request.form.get("estado_salud", p.estado_salud)
    p.tiene_familiar = request.form.get("tiene_familiar") == "on"
    p.nombre_familiar = request.form.get("nombre_familiar", p.nombre_familiar)
    p.estatus = normalize_name(request.form.get("estatus", p.estatus))
    p.observaciones = request.form.get("observaciones", p.observaciones)
    p.estado_id = request.form.get("estado_id", type=int) or p.estado_id
    p.hospital_id = request.form.get("hospital_id", type=int) or p.hospital_id
    p.area_id = request.form.get("area_id", type=int) or p.area_id
    log_action(
        current_user, "update", "Person", p.id, f"Editó persona {p.nombre} {p.apellido}"
    )
    db.session.commit()
    return jsonify({"ok": True})


@admin_bp.route("/api/hospitals")
@login_required
def api_hospitals():
    estado_id = request.args.get("estado_id", type=int)
    query = Hospital.query
    if estado_id:
        query = query.filter_by(estado_id=estado_id)
    return jsonify([{"id": h.id, "nombre": h.nombre} for h in query.all()])


# admin.py - Mejora la función sync

@admin_bp.route("/sync", methods=["POST"])
@login_required
def sync():
    require_role("admin")
    try:
        # 🔧 Verificar que los estatus existen antes de sincronizar
        from .models import seed_estatuses
        seed_estatuses()
        db.session.commit()
        
        # Verificar que los estatus se crearon
        from .models import Estatus
        estatus_count = Estatus.query.count()
        current_app.logger.info(f"📊 Estatus disponibles: {estatus_count}")
        
        if estatus_count == 0:
            return jsonify({
                "ok": False,
                "error": "No hay estatus en la base de datos. Por favor, ejecuta seed_estatuses()"
            }), 500
        
        from .sync import sync_all
        result = sync_all()
        
        log_action(
            current_user,
            "sync",
            "Sheet",
            None,
            f"Sincronización: {result['imported']} importadas, "
            f"{result['updated']} actualizadas, {result['pushed']} escritas en sheet",
        )
        return jsonify({"ok": True, **result})
    except Exception as e:
        current_app.logger.error(f"Sync failed: {e}")
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500



@admin_bp.route("/logs")
@login_required
def logs():
    require_role("admin")
    page = request.args.get("page", 1, type=int)
    per_page = 50
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page
    )
    return render_template("admin/logs.html", pagination=pagination)


# admin.py - Endpoint para verificar estatus

@admin_bp.route("/api/estatuses")
@login_required
def api_estatuses():
    """Lista todos los estatus disponibles"""
    try:
        from .models import Estatus
        estatuses = Estatus.query.order_by(Estatus.nombre).all()
        return jsonify({
            "count": len(estatuses),
            "estatuses": [{"id": e.id, "nombre": e.nombre} for e in estatuses]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500