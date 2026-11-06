import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, PointElement, LineElement, BarElement } from 'chart.js';
import { Doughnut, Bar } from 'react-chartjs-2';
import { api } from '../services/api';

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, PointElement, LineElement, BarElement);

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchStats = async () => {
    try {
      const res = await api.getDashboardStats();
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 5000); // 5-second polling for active simulation data
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading executive dashboard metrics...</div>;
  }

  if (error && !data) {
    return <div className="alert-box alert-warning">Error: {error}</div>;
  }

  const { summary, risk_distribution, status_distribution, recent_shipments, recent_alerts } = data;

  const riskChartData = {
    labels: ['Low Risk', 'Medium Risk', 'High Risk', 'Unpredicted'],
    datasets: [
      {
        data: [
          risk_distribution['Low Risk'] || 0,
          risk_distribution['Medium Risk'] || 0,
          risk_distribution['High Risk'] || 0,
          risk_distribution['Unpredicted'] || 0,
        ],
        backgroundColor: ['#22c55e', '#f59e0b', '#ef4444', '#cbd5e1'],
        borderWidth: 1,
      },
    ],
  };

  const statusChartData = {
    labels: ['Pending', 'In Transit', 'Paused', 'Stopped', 'Completed'],
    datasets: [
      {
        label: 'Shipment Count',
        data: [
          status_distribution['Pending'] || 0,
          status_distribution['In Transit'] || 0,
          status_distribution['Paused'] || 0,
          status_distribution['Stopped'] || 0,
          status_distribution['Completed'] || 0,
        ],
        backgroundColor: '#0d9488',
        borderRadius: 4,
      },
    ],
  };

  return (
    <div>
      {/* Summary Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">Total Shipments</span>
          <span className="stat-value">{summary.total_shipments}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Active Journeys</span>
          <span className="stat-value" style={{ color: '#0369a1' }}>{summary.active_shipments}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Completed Journeys</span>
          <span className="stat-value" style={{ color: '#16a34a' }}>{summary.completed_shipments}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">High-Risk Shipments</span>
          <span className="stat-value" style={{ color: '#dc2626' }}>{summary.high_risk_shipments}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Exposure Alerts</span>
          <span className="stat-value" style={{ color: '#d97706' }}>{summary.total_exposure_alerts}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Average ML Risk Score</span>
          <span className="stat-value" style={{ color: summary.average_risk_score > 50 ? '#dc2626' : '#0d9488' }}>
            {summary.average_risk_score} <span style={{ fontSize: '14px', color: '#64748b' }}>/ 100</span>
          </span>
        </div>
      </div>

      {/* Visual Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '24px', marginBottom: '24px' }}>
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">ML Quality Risk Distribution</h3>
          </div>
          <div style={{ height: '240px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Doughnut data={riskChartData} options={{ maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }} />
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Shipment Journey Status Overview</h3>
          </div>
          <div style={{ height: '240px' }}>
            <Bar data={statusChartData} options={{ maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }} />
          </div>
        </div>
      </div>

      {/* Tables: Recent Activity & Recent Alerts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: '24px' }}>
        {/* Recent Shipments */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Recent Shipment Activity</h3>
            <NavLink to="/shipments" className="btn btn-secondary btn-sm">View All</NavLink>
          </div>
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Product</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>ML Risk</th>
                </tr>
              </thead>
              <tbody>
                {recent_shipments.map((s) => {
                  const pred = s.latest_prediction;
                  return (
                    <tr key={s.id}>
                      <td>
                        <NavLink to={`/monitoring?shipment=${s.id}`} style={{ fontWeight: '600', color: '#0d9488', textDecoration: 'none' }}>
                          {s.shipment_code}
                        </NavLink>
                      </td>
                      <td>{s.product_name}</td>
                      <td>
                        <span className={`badge ${s.status === 'In Transit' ? 'badge-transit' : s.status === 'Completed' ? 'badge-completed' : 'badge-medium'}`}>
                          {s.status}
                        </span>
                      </td>
                      <td>{(s.simulation.progress * 100).toFixed(0)}%</td>
                      <td>
                        {pred ? (
                          <span className={`badge ${pred.risk_class === 'Low Risk' ? 'badge-low' : pred.risk_class === 'Medium Risk' ? 'badge-medium' : 'badge-high'}`}>
                            {pred.risk_class} ({pred.risk_score.toFixed(0)})
                          </span>
                        ) : (
                          <span style={{ color: '#94a3b8', fontSize: '12px' }}>Pending</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Alerts */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Recent Exposure Alerts</h3>
            <NavLink to="/alerts" className="btn btn-secondary btn-sm">View All</NavLink>
          </div>
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Alert Code</th>
                  <th>Shipment</th>
                  <th>Type</th>
                  <th>Severity</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {recent_alerts.length === 0 ? (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', color: '#94a3b8', padding: '24px' }}>
                      No active environmental exposure alerts.
                    </td>
                  </tr>
                ) : (
                  recent_alerts.map((a) => (
                    <tr key={a.id}>
                      <td style={{ fontWeight: '600' }}>{a.alert_code}</td>
                      <td>{a.shipment_code}</td>
                      <td>{a.alert_type.replace('_', ' ')}</td>
                      <td>
                        <span className={`badge badge-${a.severity.toLowerCase()}`}>
                          {a.severity}
                        </span>
                      </td>
                      <td>{a.exposure_duration_minutes.toFixed(0)} min</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

