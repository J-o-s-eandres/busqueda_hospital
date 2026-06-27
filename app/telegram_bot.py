import json
import os
import requests
from flask import Blueprint, request, current_app

telegram_bp = Blueprint("telegram", __name__, url_prefix="/telegram")
_search_cache = {}
RESULTS_PER_PAGE = 10
API_BASE = "https://api.telegram.org/bot"


def _token():
    return current_app.config.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _api(method):
    return f"{API_BASE}{_token()}/{method}"


def _tg(method, payload):
    try:
        r = requests.post(_api(method), json=payload, timeout=10)
        if not r.ok:
            current_app.logger.error(f"Telegram API error ({method}): {r.status_code} {r.text}")
        return r.json() if r.ok else None
    except Exception as e:
        current_app.logger.error(f"Telegram request failed ({method}): {e}")
        return None


def _cache_path():
    return os.path.join(current_app.instance_path, "search_cache.json")


def _save_state(chat_id, query, mode):
    path = _cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cache = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    cache[str(chat_id)] = {"query": query, "mode": mode}
    with open(path, "w") as f:
        json.dump(cache, f)


def _load_state(chat_id):
    path = _cache_path()
    if not os.path.exists(path):
        return {"query": None, "mode": "name"}
    try:
        with open(path) as f:
            cache = json.load(f)
        raw = cache.get(str(chat_id), {})
        if isinstance(raw, dict):
            return {"query": raw.get("query"), "mode": raw.get("mode", "name")}
        return {"query": raw, "mode": "name"}
    except Exception:
        return {"query": None, "mode": "name"}


def _persons_by_query(q, mode):
    from .models import Person
    if mode == "cedula":
        return Person.query.filter(Person.cedula.ilike(f"%{q}%")).order_by(Person.fecha_registro.desc()).all()
    elif mode == "fullname":
        parts = q.strip().split(None, 1)
        if len(parts) == 2:
            first, last = parts
            return Person.query.filter(
                Person.nombre.ilike(f"%{first}%"),
                Person.apellido.ilike(f"%{last}%"),
            ).order_by(Person.fecha_registro.desc()).all()
        like = f"%{q}%"
        return Person.query.filter(Person.nombre.ilike(like) | Person.apellido.ilike(like)).order_by(Person.fecha_registro.desc()).all()
    like = f"%{q}%"
    return Person.query.filter(Person.nombre.ilike(like) | Person.apellido.ilike(like)).order_by(Person.fecha_registro.desc()).all()


def _fmt_person(p):
    return f"{p.nombre or ''} {p.apellido or ''}".strip()


def _build_detail_text(p):
    from .models import display_name

    def sv(val):
        return str(val) if val and str(val).strip() else "—"

    sexo_icon = {"Masculino": "♂️", "Femenino": "♀️"}
    estatus_icon = {
        "Hospitalizado": "🏥", "Trasladado": "🚑", "Alta": "✅",
        "Fallecido": "💔", "No localizado": "❓",
    }

    lines = [
        f"👤 *{p.nombre or ''} {p.apellido or ''}*",
        f"🆔 Cédula: {sv(p.cedula)}",
        f"📋 Edad: {sv(p.edad)} · {sexo_icon.get(p.sexo, '')} {sv(p.sexo)}",
    ]
    loc = []
    if p.estado:
        loc.append(display_name(p.estado.nombre))
    if p.hospital:
        loc.append(display_name(p.hospital.nombre))
    if loc:
        lines.append(f"📍 {' — '.join(loc)}")
    if p.area:
        lines.append(f"🏥 Área: {display_name(p.area.nombre)}")
    lines.append(f"🩺 {estatus_icon.get(p.estatus, '')} {sv(p.estatus)}")
    lines.append(f"🩻 Estado de salud: {sv(p.estado_salud)}")
    lines.append(f"👨‍👩‍👧 Tiene familiar: {'Sí' if p.tiene_familiar else 'No'}")
    if p.nombre_familiar:
        fam = f"   Nombre: {sv(p.nombre_familiar)}"
        if p.telefono:
            fam += f" · 📞 {sv(p.telefono)}"
        lines.append(fam)
    if p.observaciones:
        lines.append(f"📝 Observaciones: {sv(p.observaciones)}")
    return "\n".join(lines)


def _send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _tg("sendMessage", payload)


def _edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _tg("editMessageText", payload)


def _answer_cb(callback_query_id):
    _tg("answerCallbackQuery", {"callback_query_id": callback_query_id})


def _mode_menu(chat_id, message_id=None):
    kb = {
        "inline_keyboard": [
            [{"text": "🆔 Por cédula", "callback_data": "mode_cedula"}],
            [{"text": "👤 Por nombre y apellido", "callback_data": "mode_fullname"}],
            [{"text": "🔍 Por nombre o apellido", "callback_data": "mode_name"}],
        ]
    }
    text = (
        "🏥 *Búsqueda Hospitalaria*\n\n"
        "Elegí cómo querés buscar:\n\n"
        "• *Por cédula* → Ej: V12345678\n"
        "• *Nombre y apellido* → Ej: Juan Pérez\n"
        "• *Nombre o apellido* → Ej: María"
    )
    if message_id:
        _edit_message(chat_id, message_id, text, reply_markup=kb)
    else:
        _send_message(chat_id, text, reply_markup=kb)


def _build_results_page_kb(chat_id, offset):
    data = _search_cache.get(chat_id)
    if not data:
        state = _load_state(chat_id)
        query = state["query"]
        mode = state["mode"]
        if not query:
            return None, None, 0
        results = _persons_by_query(query, mode)
        data = {"results": results, "total": len(results)}
        _search_cache[chat_id] = data

    results = data["results"]
    total = data["total"]
    page = results[offset:offset + RESULTS_PER_PAGE]

    kb = {"inline_keyboard": []}
    for p in page:
        name = _fmt_person(p)
        label = f"{name} · 🆔 {p.cedula}" if p.cedula else name
        kb["inline_keyboard"].append([{"text": label, "callback_data": f"det_{p.id}"}])

    nav = []
    if offset > 0:
        nav.append({"text": "◀️ Anterior", "callback_data": f"pag_{max(0, offset - RESULTS_PER_PAGE)}"})
    if offset + RESULTS_PER_PAGE < total:
        nav.append({"text": "Siguiente ▶️", "callback_data": f"pag_{offset + RESULTS_PER_PAGE}"})
    if nav:
        kb["inline_keyboard"].append(nav)
    kb["inline_keyboard"].append([{"text": "🔍 Nueva búsqueda", "callback_data": "srch"}])

    text = f"📋 *Resultados:* {total} encontrado{'s' if total != 1 else ''}"
    return kb, text, total


def _handle_start(chat_id):
    _mode_menu(chat_id)


def _handle_mode_select(chat_id, message_id, mode):
    _save_state(chat_id, "", mode)
    prompts = {
        "cedula": "✏️ Escribí la *cédula* del paciente\n\nEjemplo: V12345678",
        "fullname": "✏️ Escribí el *nombre y apellido* del paciente\n\nEjemplo: Juan Pérez",
        "name": "✏️ Escribí un *nombre o apellido*\n\nEjemplo: María",
    }
    text = prompts.get(mode, prompts["name"])
    kb = {"inline_keyboard": [[{"text": "🔙 Volver", "callback_data": "srch"}]]}
    _edit_message(chat_id, message_id, text, reply_markup=kb)


def _search(chat_id, raw_text):
    state = _load_state(chat_id)
    mode = state["mode"]
    query = raw_text.strip()

    _save_state(chat_id, query, mode)
    results = _persons_by_query(query, mode)

    if not results:
        kb = {"inline_keyboard": [[{"text": "🔍 Nueva búsqueda", "callback_data": "srch"}]]}
        _send_message(chat_id, "No se encontraron pacientes con ese criterio.", reply_markup=kb)
        return

    _search_cache[chat_id] = {"results": results, "total": len(results)}
    kb, text, _ = _build_results_page_kb(chat_id, 0)
    _send_message(chat_id, text, reply_markup=kb)


def _show_detail(chat_id, message_id, person_id):
    from .models import db, Person
    p = db.session.get(Person, person_id)
    if not p:
        _edit_message(chat_id, message_id, "Paciente no encontrado.")
        return

    kb = {"inline_keyboard": [[{"text": "🔍 Nueva búsqueda", "callback_data": "srch"}]]}
    _edit_message(chat_id, message_id, _build_detail_text(p), reply_markup=kb)


def _paginate(chat_id, message_id, offset):
    kb, text, _ = _build_results_page_kb(chat_id, offset)
    if kb:
        _edit_message(chat_id, message_id, text, reply_markup=kb)


@telegram_bp.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True)

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        if text == "/start":
            _handle_start(chat_id)
        elif text:
            _search(chat_id, text)

    elif "callback_query" in update:
        cq = update["callback_query"]
        cq_id = cq["id"]
        chat_id = cq["message"]["chat"]["id"]
        message_id = cq["message"]["message_id"]
        data = cq["data"]

        _answer_cb(cq_id)

        if data == "srch":
            _mode_menu(chat_id, message_id)
        elif data.startswith("mode_"):
            mode = data.split("_", 1)[1]
            _handle_mode_select(chat_id, message_id, mode)
        elif data.startswith("pag_"):
            offset = int(data.split("_")[1])
            _paginate(chat_id, message_id, offset)
        elif data.startswith("det_"):
            person_id = int(data.split("_")[1])
            _show_detail(chat_id, message_id, person_id)

    return "", 200


def init_telegram(app):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    app.config["TELEGRAM_BOT_TOKEN"] = token

    if not token:
        app.logger.info("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled")
        return

    webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL", "")
    webhook_flag = os.path.join(app.instance_path, ".webhook_set")
    if webhook_url and not os.path.exists(webhook_flag):
        try:
            r = requests.post(f"{API_BASE}{token}/setWebhook", json={"url": webhook_url}, timeout=10)
            if r.ok:
                with open(webhook_flag, "w") as f:
                    f.write("1")
                app.logger.info(f"Telegram webhook → {webhook_url}")
            else:
                app.logger.error(f"Failed to set webhook: {r.text}")
        except Exception as e:
            app.logger.error(f"Webhook request failed: {e}")

    app.register_blueprint(telegram_bp)
    app.logger.info("Telegram bot initialized")
