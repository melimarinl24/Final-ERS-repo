 # project/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
import os
from dotenv import load_dotenv

# ==========================================================
#  Initialize extensions
# ==========================================================
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

# Load env vars (for local dev; harmless on Heroku)
load_dotenv()

# ==========================================================
#  Application Factory
# ==========================================================
def create_app():
    app = Flask(__name__)

    # --------------------------
    # Basic Config
    # --------------------------
    # SECRET_KEY: use env first, fallback for dev
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

    # Debug controlled via env (FLASK_DEBUG=1 for dev)
    app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Local MySQL defaults (dev)
    app.config["MYSQL_HOST"] = os.getenv("MYSQL_HOST", "127.0.0.1")
    app.config["MYSQL_USER"] = os.getenv("MYSQL_USER", "root")
    app.config["MYSQL_PASSWORD"] = os.getenv("MYSQL_PASSWORD", "")
    app.config["MYSQL_DB"] = os.getenv("MYSQL_DB", "er_system")

    # Default DB URI (for local dev)
    default_uri = (
        f"mysql+pymysql://{app.config['MYSQL_USER']}:{app.config['MYSQL_PASSWORD']}"
        f"@{app.config['MYSQL_HOST']}/{app.config['MYSQL_DB']}?charset=utf8mb4"
    )

    # If Heroku provides DATABASE_URL, prefer that. Otherwise use local.
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", default_uri)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # --------------------------
    # Initialize extensions
    # --------------------------
    db.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # --------------------------
    # Login manager setup
    # --------------------------
    from .models import User  # Import here to avoid circular imports

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --------------------------
    # Create database tables
    # --------------------------
    with app.app_context():
        db.create_all()  # OK for dev; in “real” prod you’d normally use migrations only

    # --------------------------
    # Register Blueprints (active)
    # --------------------------
    from .views import bp as main
    from .auth import auth
    from .student_ui import student_ui
    from .faculty_ui import faculty_ui

    print("✅ Registering blueprints...")

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(student_ui, url_prefix="/student")
    app.register_blueprint(faculty_ui, url_prefix="/faculty")

    @app.shell_context_processor
    def make_shell_context():
        return {"db": db, "User": User}

    return app
