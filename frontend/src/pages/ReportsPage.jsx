import React, { useEffect, useState } from 'react';
import { api } from '../services/api';

export default function ReportsPage() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadShipments() {
      try {
        const res = await api.getShipments();
        setShipments(res.shipments);
      } catch (err) {
        console.error('Failed to load shipments for reports', err);
      } finally {
        setLoading(false);
      }
    }
    loadShipments();
  }, []);

  if (loading) {
    return <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading journey condition reports...</div>;
  }

  return (
    <div>
      {/* Intro Banner */}
      <div className="card" style={{ borderLeft: '4px solid #0d9488', marginBottom: '24px' }}>
        <h2 className="card-title">Downloadable Official Journey Condition Audit Reports</h2>
        <p style={{ fontSize: '13px', color: '#475569', marginTop: '4px', lineHeight: '1.5' }}>
          Generate professional, publication-quality PDF audit reports for any consignment using ReportLab.
          Each downloadable document contains complete journey metadata, configured environmental thresholds,
          recorded telemetry averages & extremes, harmful exposure alerts log, and explainable Machine Learning risk scores.
        </p>
      </div>

      <div className="card">
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Shipment ID</th>
                <th>Product Name</th>
                <th>Route</th>
                <th>Status</th>
                <th>Telemetry Readings</th>
                <th>Alerts Logged</th>
                <th>Predicted Risk</th>
                <th>Download PDF</th>
              </tr>
            </thead>
            <tbody>
              {shipments.map((s) => {
                const pred = s.latest_prediction;
                const pdfUrl = api.getPdfReportUrl(s.id);
                return (
                  <tr key={s.id}>
                    <td style={{ fontWeight: '700', color: '#0f172a' }}>{s.shipment_code}</td>
                    <td>
                      <div style={{ fontWeight: '600' }}>{s.product_name}</div>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>{s.category_label || s.category}</div>
                    </td>
                    <td>
                      {s.source_location} → {s.destination_location}
                    </td>
                    <td>
                      <span className={`badge ${s.status === 'In Transit' ? 'badge-transit' : s.status === 'Completed' ? 'badge-completed' : 'badge-medium'}`}>
                        {s.status}
                      </span>
                    </td>
                    <td>{s.reading_count || 0}</td>
                    <td>
                      <span style={{ fontWeight: '600', color: s.alert_count > 0 ? '#dc2626' : '#16a34a' }}>
                        {s.alert_count || 0}
                      </span>
                    </td>
                    <td>
                      {pred ? (
                        <span className={`badge ${pred.risk_class === 'Low Risk' ? 'badge-low' : pred.risk_class === 'Medium Risk' ? 'badge-medium' : 'badge-high'}`}>
                          {pred.risk_class} ({pred.risk_score.toFixed(1)})
                        </span>
                      ) : (
                        <span style={{ color: '#94a3b8', fontSize: '12px' }}>Awaiting</span>
                      )}
                    </td>
                    <td>
                      <a
                        href={pdfUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-primary btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                      >
                        📄 Download PDF
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

