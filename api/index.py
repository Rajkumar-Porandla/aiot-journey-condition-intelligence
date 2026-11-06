import os
import sys
from pathlib import Path

# Set up paths so app and ml packages can be imported
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

# In Vercel serverless environments, the filesystem is read-only except /tmp
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/aiot_journey.db")
os.environ.setdefault("MODEL_DIR", str(backend_dir / "ml" / "models"))
# Disable threaded background simulation in ephemeral serverless lambdas
os.environ["SIM_ENGINE_ENABLED"] = "0"

from app import create_app
from app.services.seed import seed_database

app = create_app()

with app.app_context():
    seed_database()
