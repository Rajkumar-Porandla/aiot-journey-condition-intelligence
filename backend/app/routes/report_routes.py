"""PDF Journey Condition Report generator using ReportLab."""
import io
from datetime import datetime, timezone

from flask import Blueprint, make_response, send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..extensions import db
from ..models import ExposureAlert, MLPrediction, Shipment
from ..services.analytics import shipment_readings, shipment_stats
from ..utils import ApiError, error_response

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.errorhandler(ApiError)
def _handle_api_error(err):
    return error_response(err)


def build_pdf_report(shipment, stats, prediction, alerts, readings):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
    )
    tagline_style = ParagraphStyle(
        "Tagline",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0d9488"),
    )
    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
    )

    story = []

    # Header Banner
    story.append(Paragraph("AIoT-Based Product Journey Condition Intelligence", title_style))
    story.append(Paragraph("From Origin to Destination – Every Condition Matters.", tagline_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Official Journey Condition Audit Report</b> | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}", disclaimer_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0d9488"), spaceBefore=2, spaceAfter=10))

    # Shipment Summary Table
    story.append(Paragraph("1. Shipment Overview & Route Profile", h2_style))
    shipment_info = [
        [
            Paragraph("<b>Shipment ID:</b>", body_style), Paragraph(shipment.shipment_code, body_style),
            Paragraph("<b>Product:</b>", body_style), Paragraph(shipment.product_name, body_style)
        ],
        [
            Paragraph("<b>Category:</b>", body_style), Paragraph(shipment.product_profile.name, body_style),
            Paragraph("<b>Transport Mode:</b>", body_style), Paragraph(shipment.transport_type, body_style)
        ],
        [
            Paragraph("<b>Origin:</b>", body_style), Paragraph(shipment.source_location, body_style),
            Paragraph("<b>Destination:</b>", body_style), Paragraph(shipment.destination_location, body_style)
        ],
        [
            Paragraph("<b>Status:</b>", body_style), Paragraph(f"<b>{shipment.status.upper()}</b>", body_style),
            Paragraph("<b>Simulation Mode:</b>", body_style), Paragraph(shipment.sim_mode or "NORMAL", body_style)
        ],
        [
            Paragraph("<b>Journey Started:</b>", body_style), Paragraph(shipment.start_time.strftime('%Y-%m-%d %H:%M'), body_style),
            Paragraph("<b>Telemetry Points:</b>", body_style), Paragraph(f"{len(readings)} simulated readings", body_style)
        ],
    ]
    t1 = Table(shipment_info, colWidths=[1.3*inch, 2.2*inch, 1.3*inch, 2.2*inch])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t1)
    story.append(Spacer(1, 10))

    # Environmental Limits & Thresholds
    prof = shipment.product_profile
    story.append(Paragraph("2. Configured Environmental Thresholds", h2_style))
    thresh_data = [
        ["Parameter", "Configured Safe Range", "Recorded Average", "Recorded Extremes", "Exposure Violations"],
        ["Temperature", f"{prof.min_temp}°C to {prof.max_temp}°C", f"{stats['avg_temp']:.1f}°C" if stats['avg_temp'] is not None else "N/A", f"{stats['min_temp']:.1f}°C / {stats['max_temp']:.1f}°C" if stats['max_temp'] is not None else "N/A", f"{stats['temp_exposure_hours']:.1f} hrs"],
        ["Humidity", f"{prof.min_humidity}% to {prof.max_humidity}%", f"{stats['avg_humidity']:.1f}%" if stats['avg_humidity'] is not None else "N/A", f"{stats['min_humidity']:.1f}% / {stats['max_humidity']:.1f}%" if stats['max_humidity'] is not None else "N/A", f"{stats['humidity_exposure_hours']:.1f} hrs"],
    ]
    t2 = Table(thresh_data, colWidths=[1.3*inch, 1.8*inch, 1.3*inch, 1.5*inch, 1.1*inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t2)
    story.append(Spacer(1, 10))

    # Machine Learning Assessment
    story.append(Paragraph("3. Machine Learning Product Quality Risk Assessment", h2_style))
    if prediction:
        r_class = prediction.risk_class
        r_score = prediction.risk_score
        color_map = {"Low Risk": colors.HexColor("#16a34a"), "Medium Risk": colors.HexColor("#d97706"), "High Risk": colors.HexColor("#dc2626")}
        badge_color = color_map.get(r_class, colors.HexColor("#0d9488"))

        ml_summary = [
            [
                Paragraph("<b>Predicted Risk Classification:</b>", body_style),
                Paragraph(f"<font color='{badge_color.hexval()}'><b>{r_class.upper()}</b></font>", body_style),
                Paragraph("<b>Numerical Risk Score:</b>", body_style),
                Paragraph(f"<b>{r_score:.1f} / 100</b>", body_style),
            ],
            [
                Paragraph("<b>Model Architecture:</b>", body_style),
                Paragraph("Random Forest Classifier & Regressor (Trained)", body_style),
                Paragraph("<b>Model Version:</b>", body_style),
                Paragraph(prediction.model_version, body_style),
            ]
        ]
        t_ml = Table(ml_summary, colWidths=[1.8*inch, 1.8*inch, 1.7*inch, 1.7*inch])
        t_ml.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f0fdfa")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#5eead4")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#99f6e4")),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_ml)
        story.append(Spacer(1, 6))

        # Explainable ML Highlights
        expl = prediction.explanation or {}
        contribs = expl.get("score_contributions", [])
        if contribs:
            story.append(Paragraph("<b>Top Risk Contributing Factors (Tree Path Contribution):</b>", body_style))
            top_factors = []
            for item in contribs[:4]:
                direction = "Increased Risk" if item["contribution"] > 0 else "Decreased Risk"
                top_factors.append([
                    Paragraph(f"• <b>{item['label']}</b>", body_style),
                    Paragraph(f"Value: {item['value']} {item['unit']}", body_style),
                    Paragraph(f"Impact: {item['contribution']:+.2f} pts ({direction})", body_style),
                ])
            t_factors = Table(top_factors, colWidths=[2.5*inch, 2.0*inch, 2.5*inch])
            t_factors.setStyle(TableStyle([
                ('PADDING', (0,0), (-1,-1), 2),
            ]))
            story.append(t_factors)
    else:
        story.append(Paragraph("<i>No ML prediction has been recorded yet for this journey.</i>", body_style))

    story.append(Spacer(1, 10))

    # Harmful Exposure Alerts Table
    story.append(Paragraph(f"4. Environmental Exposure Incidents ({len(alerts)} Recorded Alerts)", h2_style))
    if alerts:
        alert_rows = [["Alert ID", "Severity", "Incident Type", "Recorded Peak", "Duration", "Trigger Time"]]
        for a in alerts[:8]:  # Limit to 8 rows for clean letter page fit
            alert_rows.append([
                a.alert_code,
                a.severity,
                a.alert_type.replace("_", " "),
                f"{a.recorded_value:.1f}",
                f"{a.exposure_duration_minutes:.0f}m",
                a.timestamp.strftime('%H:%M:%S'),
            ])
        t_alerts = Table(alert_rows, colWidths=[1.2*inch, 1.0*inch, 2.0*inch, 1.0*inch, 0.9*inch, 0.9*inch])
        t_alerts.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#334155")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
            ('PADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(t_alerts)
    else:
        story.append(Paragraph("No harmful environmental exposure alerts were recorded during this journey.", body_style))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=4, spaceAfter=6))
    story.append(Paragraph("<b>Notice & Course Project Disclaimer:</b> This report is generated programmatically by the AIoT-Based Product Journey Condition Intelligence course project platform. Sensor telemetry is simulated programmatically. Machine Learning predictions reflect simulated environmental quality risk estimates and must not be used as certified food or pharmaceutical safety release certifications.", disclaimer_style))

    doc.build(story)
    buf.seek(0)
    return buf


@reports_bp.get("/<int:shipment_id>/pdf")
def download_pdf_report(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)

    readings = shipment_readings(shipment)
    stats = shipment_stats(shipment, readings)
    prediction = shipment.latest_prediction()
    alerts = shipment.alerts.order_by(ExposureAlert.timestamp.desc()).all()

    pdf_buffer = build_pdf_report(shipment, stats, prediction, alerts, readings)

    filename = f"Journey_Report_{shipment.shipment_code}.pdf"
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )

