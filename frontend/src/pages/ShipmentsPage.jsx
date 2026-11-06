import React, { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../context/useAuth';

const TRANSPORT_TYPES = [
  'Refrigerated Truck',
  'Insulated Van',
  'Air Cargo',
  'Rail Reefer',
  'Sea Container',
];

export default function ShipmentsPage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  // Modals state
  const [detailsShipment, setDetailsShipment] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [fullShipmentDetails, setFullShipmentDetails] = useState(null);

  const [editShipment, setEditShipment] = useState(null);
  const [editCarrier, setEditCarrier] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [editDeliveryTime, setEditDeliveryTime] = useState('');
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState('');

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadShipments = () => {
    const params = new URLSearchParams();
    if (statusFilter) params.append('status', statusFilter);
    if (categoryFilter) params.append('category', categoryFilter);
    return api.getShipments(params.toString())
      .then((res) => {
        setShipments(res.shipments || []);
        setError('');
      })
      .catch((err) => {
        setError(err.message || 'Failed to fetch shipments');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    let ignore = false;
    const params = new URLSearchParams();
    if (statusFilter) params.append('status', statusFilter);
    if (categoryFilter) params.append('category', categoryFilter);

    api.getShipments(params.toString())
      .then((res) => {
        if (!ignore) {
          setShipments(res.shipments || []);
          setError('');
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err.message || 'Failed to fetch shipments');
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [statusFilter, categoryFilter]);

  // Open Details Modal & fetch full metadata
  const handleOpenDetails = async (s) => {
    setDetailsShipment(s);
    setDetailsLoading(true);
    setFullShipmentDetails(null);
    try {
      const res = await api.getShipment(s.id);
      setFullShipmentDetails(res.shipment);
    } catch {
      // Fallback to table data if details endpoint fails
      setFullShipmentDetails(s);
    } finally {
      setDetailsLoading(false);
    }
  };

  // Open Edit Modal
  const handleOpenEdit = (s) => {
    setEditShipment(s);
    setEditCarrier(s.transport_type || 'Refrigerated Truck');
    setEditNotes(s.notes || '');
    setEditError('');

    if (s.expected_delivery_time) {
      try {
        const d = new Date(s.expected_delivery_time);
        const pad = (n) => String(n).padStart(2, '0');
        const formatted = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        setEditDeliveryTime(formatted);
      } catch {
        setEditDeliveryTime('');
      }
    } else {
      setEditDeliveryTime('');
    }
  };

  // Save Edit Shipment
  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editShipment) return;
    setEditSubmitting(true);
    setEditError('');

    const payload = {
      transport_type: editCarrier,
      carrier: editCarrier,
      notes: editNotes,
    };
    if (editDeliveryTime) {
      payload.expected_delivery_time = new Date(editDeliveryTime).toISOString();
    }

    try {
      await api.updateShipment(editShipment.id, payload);
      setEditShipment(null);
      await loadShipments();
    } catch (err) {
      setEditError(err.message || 'Failed to update shipment');
    } finally {
      setEditSubmitting(false);
    }
  };

  // Confirm Delete
  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.deleteShipment(deleteTarget.id);
      setDeleteTarget(null);
      await loadShipments();
    } catch (err) {
      alert(`Error deleting shipment: ${err.message}`);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div>
      {/* Header Filters & Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
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

      {/* Shipments Table */}
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
                  const canEdit = s.status !== 'In Transit' && s.status !== 'Completed';
                  return (
                    <tr key={s.id}>
                      <td>
                        <button
                          type="button"
                          onClick={() => handleOpenDetails(s)}
                          style={{
                            background: 'none',
                            border: 'none',
                            padding: 0,
                            cursor: 'pointer',
                            fontWeight: '700',
                            color: '#0d9488',
                            textAlign: 'left',
                            fontSize: '13.5px',
                            display: 'inline-block',
                          }}
                          title="Click to view full consignment details"
                        >
                          {s.shipment_code} 🔍
                        </button>
                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>
                          Mode: {s.simulation?.mode || 'NORMAL'}
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
                            Progress: {((s.simulation?.progress || 0) * 100).toFixed(0)}%
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
                        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                          <NavLink
                            to={`/monitoring?shipment=${s.id}`}
                            className="btn btn-secondary btn-sm"
                            title="Virtual Telemetry Monitoring"
                          >
                            Monitor
                          </NavLink>

                          <button
                            type="button"
                            onClick={() => handleOpenEdit(s)}
                            className="btn btn-secondary btn-sm"
                            title={canEdit ? 'Edit Shipment' : `Cannot edit while ${s.status}`}
                            style={{ opacity: canEdit ? 1 : 0.6 }}
                          >
                            Edit
                          </button>

                          <NavLink to={`/reports`} className="btn btn-secondary btn-sm" title="View Reports">
                            Report
                          </NavLink>

                          {isAdmin ? (
                            <button
                              type="button"
                              onClick={() => setDeleteTarget(s)}
                              className="btn btn-danger btn-sm"
                              title={s.status === 'In Transit' ? 'Cannot delete an active In-Transit shipment' : 'Delete Shipment (Admin)'}
                              disabled={s.status === 'In Transit'}
                              style={{ padding: '4px 8px' }}
                            >
                              ✕
                            </button>
                          ) : (
                            <span
                              className="badge badge-medium"
                              style={{ fontSize: '10px', opacity: 0.65, cursor: 'not-allowed' }}
                              title="Operator Mode: Admin required to delete consignments"
                            >
                              🔒
                            </span>
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

      {/* =========================================================================
          MODAL 1: Shipment Details Modal
          ========================================================================= */}
      {detailsShipment && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="details-title"
          onClick={() => setDetailsShipment(null)}
        >
          <div
            className="modal-dialog modal-dialog-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3 id="details-title" className="modal-title">
                <span>📦 Consignment Details: {detailsShipment.shipment_code}</span>
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setDetailsShipment(null)}
                aria-label="Close details"
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              {detailsLoading && !fullShipmentDetails ? (
                <div style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                  Loading consignment specifications...
                </div>
              ) : (
                (() => {
                  const d = fullShipmentDetails || detailsShipment;
                  const profile = d.stats?.profile || {};
                  return (
                    <>
                      <div className="detail-grid">
                        <div className="detail-item">
                          <span className="detail-label">Product Name</span>
                          <span className="detail-value">{d.product_name}</span>
                        </div>
                        <div className="detail-item">
                          <span className="detail-label">Product Category</span>
                          <span className="detail-value">{d.category_label || d.category || 'N/A'}</span>
                        </div>
                        <div className="detail-item">
                          <span className="detail-label">Journey Status</span>
                          <span className="detail-value">
                            <span className={`badge ${d.status === 'In Transit' ? 'badge-transit' : d.status === 'Completed' ? 'badge-completed' : 'badge-medium'}`}>
                              {d.status}
                            </span>
                          </span>
                        </div>
                        <div className="detail-item">
                          <span className="detail-label">Transport Carrier</span>
                          <span className="detail-value">{d.transport_type}</span>
                        </div>
                      </div>

                      <div className="detail-grid" style={{ marginTop: '4px' }}>
                        <div className="detail-item">
                          <span className="detail-label">Origin Location & Coordinates</span>
                          <span className="detail-value">
                            {d.source_location}
                            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 400 }}>
                              Lat: {d.source_lat?.toFixed(4)}, Lon: {d.source_lon?.toFixed(4)}
                            </div>
                          </span>
                        </div>
                        <div className="detail-item">
                          <span className="detail-label">Destination Location & Coordinates</span>
                          <span className="detail-value">
                            {d.destination_location}
                            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 400 }}>
                              Lat: {d.destination_lat?.toFixed(4)}, Lon: {d.destination_lon?.toFixed(4)}
                            </div>
                          </span>
                        </div>
                      </div>

                      <div className="detail-grid" style={{ marginTop: '4px' }}>
                        <div className="detail-item">
                          <span className="detail-label">Start Time</span>
                          <span className="detail-value">
                            {d.start_time ? new Date(d.start_time).toLocaleString() : 'Not started'}
                          </span>
                        </div>
                        <div className="detail-item">
                          <span className="detail-label">Expected Delivery Time</span>
                          <span className="detail-value">
                            {d.expected_delivery_time ? new Date(d.expected_delivery_time).toLocaleString() : 'Unspecified'}
                          </span>
                        </div>
                      </div>

                      {/* Profile Safe Storage Bounds */}
                      <div className="card" style={{ padding: '16px', margin: '4px 0 0 0', backgroundColor: '#f8fafc' }}>
                        <h4 style={{ fontSize: '13px', fontWeight: '700', color: '#0f172a', marginBottom: '10px' }}>
                          Product Cold-Chain Safe Thresholds
                        </h4>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                          <div>
                            <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Safe Temperature Range:</span>
                            <span style={{ fontWeight: '700', color: '#0d9488' }}>
                              {profile.min_temp !== undefined ? `${profile.min_temp}°C to ${profile.max_temp}°C` : 'Standard Cold-Chain'}
                            </span>
                          </div>
                          <div>
                            <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Safe Humidity Range:</span>
                            <span style={{ fontWeight: '700', color: '#3b82f6' }}>
                              {profile.min_humidity !== undefined ? `${profile.min_humidity}% to ${profile.max_humidity}%` : 'Controlled RH'}
                            </span>
                          </div>
                          <div>
                            <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Telemetry & Alerts Logged:</span>
                            <span style={{ fontWeight: '600' }}>
                              {d.reading_count || 0} readings · <span style={{ color: d.alert_count > 0 ? '#dc2626' : '#16a34a' }}>{d.alert_count || 0} alerts</span>
                            </span>
                          </div>
                        </div>
                      </div>

                      {d.notes && (
                        <div className="detail-item">
                          <span className="detail-label">Handling & Consignment Notes</span>
                          <span className="detail-value" style={{ fontWeight: 400, whiteSpace: 'pre-wrap' }}>{d.notes}</span>
                        </div>
                      )}
                    </>
                  );
                })()
              )}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDetailsShipment(null)}
              >
                Close
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  const id = detailsShipment.id;
                  setDetailsShipment(null);
                  navigate(`/monitoring?shipment=${id}`);
                }}
              >
                📡 Open Live Monitoring
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 2: Edit Shipment Modal
          ========================================================================= */}
      {editShipment && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="edit-title"
          onClick={() => setEditShipment(null)}
        >
          <div
            className="modal-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3 id="edit-title" className="modal-title">
                ✏️ Edit Shipment {editShipment.shipment_code}
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setEditShipment(null)}
                aria-label="Close edit modal"
              >
                ✕
              </button>
            </div>

            {editError && <div className="alert-box alert-warning">{editError}</div>}

            {editShipment.status === 'In Transit' || editShipment.status === 'Completed' ? (
              <div className="alert-box alert-info">
                ℹ️ This shipment is currently <b>{editShipment.status}</b>. Shipments that are actively in transit or completed cannot have their transportation parameters modified.
              </div>
            ) : null}

            <form onSubmit={handleSaveEdit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Transport Carrier / Vehicle</label>
                  <select
                    className="form-control"
                    value={editCarrier}
                    onChange={(e) => setEditCarrier(e.target.value)}
                    disabled={editShipment.status === 'In Transit' || editShipment.status === 'Completed'}
                    required
                  >
                    {TRANSPORT_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Expected Delivery Time</label>
                  <input
                    type="datetime-local"
                    className="form-control"
                    value={editDeliveryTime}
                    onChange={(e) => setEditDeliveryTime(e.target.value)}
                    disabled={editShipment.status === 'In Transit' || editShipment.status === 'Completed'}
                  />
                  <span style={{ fontSize: '11px', color: '#64748b' }}>
                    Adjust anticipated arrival window for duration compliance monitoring.
                  </span>
                </div>

                <div className="form-group">
                  <label className="form-label">Special Handling & Journey Notes</label>
                  <textarea
                    className="form-control"
                    rows={4}
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    placeholder="Enter temperature sensitivity instructions, cargo handling notes, or route deviations..."
                    disabled={editShipment.status === 'In Transit' || editShipment.status === 'Completed'}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setEditShipment(null)}
                  disabled={editSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={editSubmitting || editShipment.status === 'In Transit' || editShipment.status === 'Completed'}
                >
                  {editSubmitting ? 'Saving Changes...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 3: Styled In-App Delete Confirmation Modal (Replaces window.confirm)
          ========================================================================= */}
      {deleteTarget && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
          onClick={() => setDeleteTarget(null)}
        >
          <div
            className="modal-dialog"
            style={{ maxWidth: '480px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3 id="delete-dialog-title" className="modal-title" style={{ color: '#dc2626' }}>
                ⚠️ Confirm Permanent Deletion
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setDeleteTarget(null)}
                aria-label="Close delete modal"
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <p style={{ fontSize: '14px', color: '#334155', lineHeight: '1.5' }}>
                Are you sure you want to permanently delete consignment{' '}
                <strong style={{ color: '#0f172a' }}>{deleteTarget.shipment_code}</strong> (
                {deleteTarget.product_name})?
              </p>
              <div
                style={{
                  backgroundColor: '#fef2f2',
                  border: '1px solid #fee2e2',
                  borderRadius: '8px',
                  padding: '12px',
                  fontSize: '12.5px',
                  color: '#991b1b',
                  lineHeight: '1.4',
                }}
              >
                <b>Irreversible Action:</b> All associated sensor readings ({deleteTarget.reading_count || 0} telemetry points),
                exposure incident alerts ({deleteTarget.alert_count || 0} alerts), and historical ML risk predictions will be deleted immediately.
              </div>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
                autoFocus
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleConfirmDelete}
                disabled={deleting}
              >
                {deleting ? 'Deleting Consignment...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
