from flask import Flask, redirect, url_for, render_template

from flask_sqlalchemy import SQLAlchemy

from flask_login import LoginManager

from flask_migrate import Migrate

db = SQLAlchemy()

login_manager = LoginManager()

migrate = Migrate()


def create_app(config_obj=None):

    app = Flask(__name__, instance_relative_config=True)

    app.config.from_object(config_obj or "app.config.Config")

    db.init_app(app)

    login_manager.init_app(app)

    migrate.init_app(app, db)

    # Root redirect
    @app.route("/")
    def root():
        return redirect("/public/search")
        #return redirect(url_for("public.search"))

    # Register blueprints
    from .public import public_bp
    from .auth import auth_bp
    from .admin import admin_bp

    # Ensure models are imported so migrations see them
    from .models import display_name

    if not app.config.get("TESTING"):
        from .scheduler import init_scheduler
        init_scheduler(app)

    app.register_blueprint(public_bp)

    app.register_blueprint(auth_bp)

    app.register_blueprint(admin_bp)

    login_manager.login_view = "auth.login"

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

# Seeding moved to CLI commands; no seeding at startup to avoid missing tables

    @app.template_global()
    def fmt(s):
        return display_name(s)

    @app.template_global()
    def info(val):
        return val if val and str(val).strip() else "sin información"

    if not app.config.get("TESTING"):
        from .telegram_bot import init_telegram
        init_telegram(app)

    @app.cli.command("create-admin")
    def create_admin():
        """Create the initial admin user (run once on a fresh database)."""
        from .models import User, seed_estatuses

        db.create_all()
        seed_estatuses()
        if User.query.filter_by(username="admin").first():
            print("Admin user already exists.")
            return
        import click

        password = click.prompt(
            "Password for admin user", hide_input=True, default="admin123"
        )
        u = User(
            username="admin", role="admin", nombre="Admin", apellido="", active=True
        )
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        print(
            f"Admin user created (username=admin). Change the password after first login."
        )

    return app
