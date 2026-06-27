import time
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from .models import User
from .forms import LoginForm

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

MAX_ATTEMPTS = 3
LOCKOUT_MINUTES = 5
_failed_attempts: dict[str, dict] = {}


def _get_ip():
    return request.remote_addr or "unknown"


def _is_locked_out(ip):
    entry = _failed_attempts.get(ip)
    if not entry:
        return False
    if entry["count"] >= MAX_ATTEMPTS:
        if time.time() < entry["lockout_until"]:
            return True
        del _failed_attempts[ip]
    return False


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    ip = _get_ip()
    remaining = None

    if _is_locked_out(ip):
        mins = int((_failed_attempts[ip]["lockout_until"] - time.time()) // 60) + 1
        flash(
            f"Demasiados intentos. Espera {mins} minuto(s) antes de intentar de nuevo.",
            "danger",
        )
        return render_template("auth/login.html", form=LoginForm())

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            _failed_attempts.pop(ip, None)
            login_user(user)
            flash("Bienvenido", "success")
            return redirect(url_for("public.search"))

        entry = _failed_attempts.setdefault(ip, {"count": 0, "lockout_until": 0})
        entry["count"] += 1
        if entry["count"] >= MAX_ATTEMPTS:
            entry["lockout_until"] = time.time() + LOCKOUT_MINUTES * 60
            flash(
                f"Credenciales incorrectas. Has alcanzado el máximo de {MAX_ATTEMPTS} intentos. "
                f"Espera {LOCKOUT_MINUTES} minutos.",
                "danger",
            )
        else:
            remaining = MAX_ATTEMPTS - entry["count"]
            flash(
                f"Credenciales incorrectas. Te quedan {remaining} intento(s).",
                "danger",
            )
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada", "info")
    return redirect(url_for("public.index"))
