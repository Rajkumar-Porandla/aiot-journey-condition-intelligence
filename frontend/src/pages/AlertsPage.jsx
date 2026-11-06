import React, { useEffect, useState } from 'react';
import { api } from '../services/api';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [activeCount, setActiveCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');

  const loadAlerts = async () => {
    try {
      const params = new URLSearchParams();
      if (severityFilter) params.append('severity', severityFilter);
      if (activeFilter) params.append('is_active', activeFilter);
      const res = await api.getAllAlerts(params.toString());
      setAlerts(res.alerts);
      setTotalCount(res.total);
      setActiveCount(res.active_count);
    } catch (err) {
      console.error('Failed to load alerts', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts();
    const timer = setInterval(loadAlerts, 5000);
    return () => clearInterval(timer);
  }, [severityFilter, activeFilter]);

  return (
    <div>
      {/* Alert KPI Summary */}
      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">Total Exposure Incidents</span>
          <span className="stat-value">{totalCount}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Active Critical Episodes</span>
          <span className="stat-value" style={{ color: activeCount > 0 ? '#dc2626' : '#16a34a' }}>
            {activeCount}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Critical Alerts</span>
          <span className="stat-value" style={{ color: '#7f1d1d' }}>
            {alerts.filter((a) => a.severity === 'Critical').length}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">High Severity</span>
          <span className="stat-value" style={{ color: '#dc2626' }}>
            {alerts.filter((a) => a.severity === 'High').length}
          </span>
        </div>
      </div>

      {/* Filter Controls */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: '600' }}>Filter Severity:</span>
            <select
              className="form-control"
              style={{ width: '150px' }}
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
            >
              <option value="">All Severities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: '600' }}>Status:</span>
            <select
              className="form-control"
              style={{ width: '150px' }}
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="true">Active Only</option>
              <option value="false">Resolved Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Detailed Incidents Table */}
      <div className="card">
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Alert ID</th>
                <th>Shipment Code</th>
                <th>Product</th>
                <th>Violation Type</th>
                <th>Severity</th>
                <th>Peak Value</th>
                <th>Threshold Limit</th>
                <th>Duration</th>
                <th>State</th>
                <th>Detailed Description</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="10" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                    Loading exposure incidents...
                  </td>
                </tr>
              ) : alerts.length === 0 ? (
                <tr>
                  <td colSpan="10" style={{ textAlign: 'center', padding: '30px', color: '#16a34a' }}>
                    No exposure alerts match the selected criteria.
                  </td>
                </tr>
              ) : (
                alerts.map((a) => (
                  <tr key={a.id}>
                    <td style={{ fontWeight: '700', color: '#0f172a' }}>{a.alert_code}</td>
                    <td style={{ fontWeight: '600', color: '#0d9488' }}>{a.shipment_code}</td>
                    <td>{a.product_name}</td>
                    <td>{a.alert_type.replace('_', ' ')}</td>
                    <td>
                      <span className={`badge badge-${a.severity.toLowerCase()}`}>{a.severity}</span>
                    </td>
                    <td style={{ fontWeight: '600' }}>{a.recorded_value.toFixed(1)}</td>
                    <td>{a.threshold_value}</td>
                    <td>{a.exposure_duration_minutes.toFixed(0)} min</td>
                    <td>
                      <span className={`badge ${a.is_active ? 'badge-high' : 'badge-low'}`}>
                        {a.is_active ? 'Active' : 'Ended'}
                      </span>
                    </td>
                    <td style={{ fontSize: '12px', maxWidth: '340px' }}>{a.description}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

