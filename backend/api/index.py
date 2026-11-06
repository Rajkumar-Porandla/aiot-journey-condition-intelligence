import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Serverless environment adaptations
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/aiot_journey.db")
os.environ.setdefault("MODEL_DIR", str(backend_dir / "ml" / "models"))
os.environ["SIM_ENGINE_ENABLED"] = "0"

from app import create_app
from app.services.seed import seed_database

app = create_app()

with app.app_context():
    seed_database()
