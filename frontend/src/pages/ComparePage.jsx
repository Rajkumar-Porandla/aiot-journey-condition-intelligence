import React, { useEffect, useState, useCallback } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { api } from '../services/api';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

export default function ComparePage() {
  const [shipments, setShipments] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState('');

  // Defined BEFORE any useEffect referencing it
  const runComparison = useCallback(async (ids) => {
    if (ids.length < 2) {
      alert('Please select at least 2 shipments to compare.');
      return;
    }
    setComparing(true);
    setError('');
    try {
      const res = await api.compareShipments(ids);
      setComparison(res);
    } catch (err) {
      setError(err.message || 'Comparison request failed');
    } finally {
      setComparing(false);
    }
  }, []);

  useEffect(() => {
    async function loadShipmentsList() {
      try {
        const res = await api.getShipments();
        setShipments(res.shipments);
        if (res.shipments.length >= 2) {
          const initial = [res.shipments[0].id, res.shipments[1].id];
          setSelectedIds(initial);
          runComparison(initial);
        }
      } catch (err) {
        setError(err.message || 'Failed to fetch shipments list');
      } finally {
        setLoading(false);
      }
    }
    loadShipmentsList();
  }, [runComparison]);

  const toggleSelect = (id) => {
    if (comparing) return;
    let next;
    if (selectedIds.includes(id)) {
      next = selectedIds.filter((x) => x !== id);
    } else {
      next = [...selectedIds, id];
    }
    setSelectedIds(next);
    if (next.length >= 2) {
      runComparison(next);
    }
  };

  if (loading) {
    return <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading comparison suite...</div>;
  }

  const comparedList = comparison?.shipments || [];

  // Comparison Bar Chart
  const riskChartData = {
    labels: comparedList.map((s) => s.shipment_code),
    datasets: [
      {
        label: 'ML Risk Score (0-100)',
        data: comparedList.map((s) => s.ml_risk.risk_score || 0),
        backgroundColor: comparedList.map((s) =>
          (s.ml_risk.risk_score || 0) > 50 ? '#ef4444' : '#0d9488'
        ),
        borderRadius: 6,
      },
      {
        label: 'Temp Exposure Duration (Hours)',
        data: comparedList.map((s) => s.stats.temp_exposure_hours || 0),
        backgroundColor: '#3b82f6',
        borderRadius: 6,
      },
    ],
  };

  return (
    <div>
      {/* Intro Banner */}
      <div className="card" style={{ borderLeft: '4px solid #0d9488', marginBottom: '24px' }}>
        <h2 className="card-title">Multi-Shipment Risk & Journey Comparison</h2>
        <p style={{ fontSize: '13px', color: '#475569', marginTop: '4px', lineHeight: '1.5' }}>
          Evaluate multiple transportation consignments side-by-side. Inspect temperature and humidity violation durations,
          ML quality risk predictions, and automatically identify the safest transportation route or carrier.
        </p>
      </div>

      {/* Shipment Selection Checklist */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
          <h3 className="card-title" style={{ margin: 0 }}>
            Select Shipments for Side-by-Side Analysis (Minimum 2):
          </h3>
          {comparing && (
            <span className="badge badge-transit" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              <span className="status-dot" /> Analyzing Consignments...
            </span>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
          {shipments.map((s) => {
            const isChecked = selectedIds.includes(s.id);
            return (
              <label
                key={s.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '10px 14px',
                  borderRadius: '6px',
                  border: isChecked ? '1px solid #0d9488' : '1px solid #cbd5e1',
                  backgroundColor: isChecked ? '#f0fdfa' : 'white',
                  cursor: comparing ? 'not-allowed' : 'pointer',
                  opacity: comparing ? 0.7 : 1,
                  fontSize: '13px',
                  transition: 'opacity 0.15s ease',
                }}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  disabled={comparing}
                  onChange={() => toggleSelect(s.id)}
                />
                <div>
                  <div style={{ fontWeight: '600', color: '#0f172a' }}>{s.shipment_code}</div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>
                    {s.product_name} ({s.category_label || s.category})
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      </div>

      {/* Loading feedback banner when comparing */}
      {comparing && (
        <div className="alert-box alert-info" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span>🔄</span>
          <span><b>Computing Multi-Shipment Comparative Analysis:</b> Aggregating telemetry exposures, cross-category variance, and ML safety scores...</span>
        </div>
      )}

      {error && <div className="alert-box alert-warning">{error}</div>}

      {/* Cross-Category Warning if applicable */}
      {comparison?.category_warning && (
        <div className="alert-box" style={{ backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fde68a' }}>
          ⚠️ <b>Cross-Category Notice:</b> {comparison.category_warning}
        </div>
      )}

      {/* Safest Shipment Identified Banner */}
      {comparison?.safest_shipment && (
        <div
          className="card"
          style={{
            backgroundColor: '#ecfdf5',
            border: '1px solid #a7f3d0',
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            padding: '20px',
          }}
        >
          <div style={{ fontSize: '32px' }}>🏆</div>
          <div>
            <div style={{ fontSize: '12px', fontWeight: '700', color: '#047857', textTransform: 'uppercase' }}>
              Safest Transportation Journey Identified
            </div>
            <div style={{ fontSize: '18px', fontWeight: '700', color: '#065f46', marginTop: '2px' }}>
              {comparison.safest_shipment.shipment_code} – Predicted Risk Score: {comparison.safest_shipment.risk_score.toFixed(1)}/100 ({comparison.safest_shipment.risk_class})
            </div>
            <div style={{ fontSize: '13px', color: '#047857', marginTop: '4px' }}>
              {comparison.safest_shipment.reason}
            </div>
          </div>
        </div>
      )}

      {/* Side-by-Side Comparison Cards */}
      {comparedList.length > 0 && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fit, minmax(280px, 1fr))`, gap: '20px', marginBottom: '24px' }}>
            {comparedList.map((item) => (
              <div key={item.shipment_id} className="card" style={{ margin: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                  <div>
                    <h4 style={{ fontSize: '16px', fontWeight: '700', color: '#0f172a' }}>{item.shipment_code}</h4>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>{item.product_name}</div>
                  </div>
                  <span className={`badge ${item.ml_risk.risk_class === 'Low Risk' ? 'badge-low' : item.ml_risk.risk_class === 'Medium Risk' ? 'badge-medium' : 'badge-high'}`}>
                    {item.ml_risk.risk_class}
                  </span>
                </div>

                <div style={{ fontSize: '24px', fontWeight: '700', color: (item.ml_risk.risk_score || 0) > 50 ? '#dc2626' : '#0d9488', marginBottom: '16px' }}>
                  {item.ml_risk.risk_score !== null ? `${item.ml_risk.risk_score.toFixed(1)} / 100` : 'Awaiting Run'}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12.5px', borderTop: '1px solid #e2e8f0', paddingTop: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Category:</span>
                    <span style={{ fontWeight: '600' }}>{item.category}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Route:</span>
                    <span style={{ fontWeight: '500' }}>{item.source_location} → {item.destination_location}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Carrier:</span>
                    <span>{item.transport_type}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Avg / Peak Temp:</span>
                    <span style={{ fontWeight: '600' }}>{item.stats.avg_temp ?? 'N/A'}°C / {item.stats.max_temp ?? 'N/A'}°C</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Temp Exposure:</span>
                    <span style={{ fontWeight: '600', color: item.stats.temp_exposure_hours > 0 ? '#dc2626' : '#16a34a' }}>
                      {item.stats.temp_exposure_hours} hrs
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Total Violations:</span>
                    <span style={{ fontWeight: '600' }}>{item.stats.violation_count}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Alerts Triggered:</span>
                    <span style={{ fontWeight: '600' }}>{item.stats.alert_count}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Comparison Visual Chart */}
          <div className="card">
            <h3 className="card-title" style={{ marginBottom: '16px' }}>Comparative Risk & Environmental Stress</h3>
            <div style={{ height: '280px' }}>
              <Bar data={riskChartData} options={{ maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
