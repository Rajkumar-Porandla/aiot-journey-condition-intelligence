"""Register all API route blueprints."""
from .alert_routes import alerts_bp
from .auth_routes import auth_bp
from .dashboard_routes import dashboard_bp
from .ml_routes import ml_bp
from .product_routes import products_bp
from .report_routes import reports_bp
from .shipment_routes import shipments_bp
from .simulation_routes import sim_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(shipments_bp)
    app.register_blueprint(sim_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(dashboard_bp)

