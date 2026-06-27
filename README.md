# 🏥 Búsqueda Hospitalaria

Aplicación web para buscar y gestionar información de pacientes hospitalizados durante emergencias o desastres. Cuenta con búsqueda pública, panel administrativo, sincronización con Google Sheets y bot de Telegram.

## 🌐 Uso

### Búsqueda pública (`/public/search`)
Cualquier persona puede buscar pacientes por nombre, apellido, cédula, estado, hospital o área. Los resultados se muestran en una tabla responsive con vista móvil.

### Panel administrativo (`/admin/`)
Acceso con roles:

| Rol     | Permisos                                                              |
|---------|-----------------------------------------------------------------------|
| Admin   | Todo: CRUD personas, usuarios, catálogos, subir Excel, sincronizar   |
| Helper  | CRUD personas + catálogos                                             |
| Viewer  | Solo lectura (dashboard + lista de personas)                          |

### Bot de Telegram (@vnzlbusquedabot)
- Buscar pacientes por cédula, nombre y apellido, o nombre/apellido suelto
- Resultados con paginación y detalle completo
- Sin necesidad de login — cualquiera puede usar el bot

## ✨ Funcionalidades

- Búsqueda en tiempo real con filtros por estado, hospital, área
- Subida de Excel con normalización de datos (sexo, deduplicación por cédula o nombre+apellido)
- Sincronización bidireccional con Google Sheets
- Exportar a CSV
- Dashboard con estadísticas
- Diseño responsive + vista móvil tipo cards
- Bot de Telegram con menú interactivo

## 🛠 Stack

- **Backend:** Python 3.11, Flask, SQLAlchemy, Flask-Login
- **Base de datos:** SQLite (producción en Railway)
- **Frontend:** Bootstrap 5, DataTables, Chart.js
- **Tareas programadas:** APScheduler
- **Externo:** Google Sheets API (gspread), Telegram Bot API
- **Despliegue:** Docker, Gunicorn, Railway

## 🚀 Inicio rápido local

```bash
git clone <repo-url>
cd busqueda_hostipal
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
flask run --host=0.0.0.0 --port=5000
```

Visitar `http://localhost:5000/public/search`

## 📦 Variables de entorno

| Variable                                       | Descripción                           |
|------------------------------------------------|---------------------------------------|
| `SECRET_KEY`                                   | Clave secreta de Flask                |
| `GOOGLE_SHEET_ID`                              | ID del Google Sheet                   |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL`                 | Email de cuenta de servicio           |
| `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY`           | Clave privada RSA                     |
| `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY_JSON`      | JSON completo de cuenta de servicio   |
| `TELEGRAM_BOT_TOKEN`                           | Token del bot de Telegram             |
| `TELEGRAM_WEBHOOK_URL`                         | URL del webhook del bot               |

## 📄 Licencia

MIT
