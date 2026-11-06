"""Backend application entrypoint for development and production."""
import os

from app import create_app
from app.services.seed import seed_database

app = create_app()

with app.app_context():
    seed_database()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"Starting AIoT Journey Intelligence Server on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

