import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { api } from '../services/api';

export default function ShipmentsPage() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  const loadShipments = async () => {
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      if (categoryFilter) params.append('category', categoryFilter);
      const res = await api.getShipments(params.toString());
      setShipments(res.shipments);
    } catch (err) {
      setError(err.message || 'Failed to fetch shipments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadShipments();
  }, [statusFilter, categoryFilter]);

  const handleDelete = async (id, code) => {
    if (!window.confirm(`Are you sure you want to delete shipment ${code}? All associated telemetry and alerts will be permanently removed.`)) {
      return;
    }
    try {
      await api.deleteShipment(id);
      loadShipments();
    } catch (err) {
      alert(`Error deleting shipment: ${err.message}`);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ display: 'flex', gap: '12px' }}>
          <select
            className="form-control"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ width: '160px' }}
          >
            <option value="">All Statuses</option>
            <option value="Pending">Pending</option>
            <option value="In Transit">In Transit</option>
            <option value="Paused">Paused</option>
            <option value="Stopped">Stopped</option>
            <option value="Completed">Completed</option>
          </select>

          <select
            className="form-control"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            style={{ width: '180px' }}
          >
            <option value="">All Categories</option>
            <option value="fruits_vegetables">Fruits & Vegetables</option>
            <option value="dairy">Dairy Products</option>
            <option value="frozen">Frozen Goods</option>
            <option value="pharmaceutical">Pharmaceuticals</option>
            <option value="flowers">Flowers</option>
          </select>
        </div>

        <NavLink to="/shipments/create" className="btn btn-primary">
          + Create New Shipment
        </NavLink>
      </div>

      {error && <div className="alert-box alert-warning">{error}</div>}

      <div className="card">
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Shipment ID</th>
                <th>Product & Category</th>
                <th>Origin & Destination</th>
                <th>Transport</th>
                <th>Status</th>
                <th>Telemetry</th>
                <th>ML Quality Risk</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                    Loading transportation shipments...
                  </td>
                </tr>
              ) : shipments.length === 0 ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                    No shipments match the selected filters.
                  </td>
                </tr>
              ) : (
                shipments.map((s) => {
                  const pred = s.latest_prediction;
                  return (
                    <tr key={s.id}>
                      <td>
                        <NavLink
                          to={`/monitoring?shipment=${s.id}`}
                          style={{ fontWeight: '700', color: '#0d9488', textDecoration: 'none' }}
                        >
                          {s.shipment_code}
                        </NavLink>
                        <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                          Mode: {s.simulation.mode || 'NORMAL'}
                        </div>
                      </td>
                      <td>
                        <div style={{ fontWeight: '600', color: '#1e293b' }}>{s.product_name}</div>
                        <div style={{ fontSize: '12px', color: '#64748b' }}>{s.category_label || s.product_profile}</div>
                      </td>
                      <td>
                        <div>{s.source_location}</div>
                        <div style={{ fontSize: '12px', color: '#64748b' }}>→ {s.destination_location}</div>
                      </td>
                      <td>{s.transport_type}</td>
                      <td>
                        <span
                          className={`badge ${
                            s.status === 'In Transit'
                              ? 'badge-transit'
                              : s.status === 'Completed'
                              ? 'badge-completed'
                              : 'badge-medium'
                          }`}
                        >
                          {s.status}
                        </span>
                        {s.status === 'In Transit' && (
                          <div style={{ fontSize: '11px', color: '#0369a1', marginTop: '2px' }}>
                            Progress: {(s.simulation.progress * 100).toFixed(0)}%
                          </div>
                        )}
                      </td>
                      <td>
                        <div>{s.reading_count || 0} readings</div>
                        <div style={{ fontSize: '11px', color: s.alert_count > 0 ? '#dc2626' : '#64748b' }}>
                          {s.alert_count || 0} alerts
                        </div>
                      </td>
                      <td>
                        {pred ? (
                          <div>
                            <span
                              className={`badge ${
                                pred.risk_class === 'Low Risk'
                                  ? 'badge-low'
                                  : pred.risk_class === 'Medium Risk'
                                  ? 'badge-medium'
                                  : 'badge-high'
                              }`}
                            >
                              {pred.risk_class}
                            </span>
                            <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                              Score: {pred.risk_score.toFixed(1)}/100
                            </div>
                          </div>
                        ) : (
                          <span style={{ color: '#94a3b8', fontSize: '12px' }}>Awaiting Data</span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <NavLink to={`/monitoring?shipment=${s.id}`} className="btn btn-secondary btn-sm" title="Virtual Telemetry Monitoring">
                            Monitor
                          </NavLink>
                          <NavLink to={`/reports`} className="btn btn-secondary btn-sm" title="View Reports">
                            Report
                          </NavLink>
                          {s.status !== 'In Transit' && (
                            <button
                              type="button"
                              onClick={() => handleDelete(s.id, s.shipment_code)}
                              className="btn btn-danger btn-sm"
                              title="Delete Shipment"
                              style={{ padding: '4px 8px' }}
                            >
                              ✕
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

