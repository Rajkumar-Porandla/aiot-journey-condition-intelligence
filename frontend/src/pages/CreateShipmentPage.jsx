import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';

export default function CreateShipmentPage() {
  const navigate = useNavigate();

  const [products, setProducts] = useState([]);
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [productName, setProductName] = useState('');
  const [productProfileId, setProductProfileId] = useState('');
  const [sourceLoc, setSourceLoc] = useState('');
  const [destLoc, setDestLoc] = useState('');
  const [transportType, setTransportType] = useState('Refrigerated Truck');
  const [durationHours, setDurationHours] = useState(12);
  const [notes, setNotes] = useState('');

  useEffect(() => {
    async function loadFormMetadata() {
      try {
        const [prodRes, locRes] = await Promise.all([api.getProducts(), api.getLocations()]);
        setProducts(prodRes.products);
        setLocations(locRes.locations);
        if (prodRes.products.length > 0) {
          setProductProfileId(prodRes.products[0].id);
          setProductName(`Sample ${prodRes.products[0].name}`);
        }
        if (locRes.locations.length >= 2) {
          setSourceLoc(locRes.locations[0].name);
          setDestLoc(locRes.locations[1].name);
        }
      } catch (err) {
        setError('Failed to load product profiles or locations.');
      } finally {
        setLoading(false);
      }
    }
    loadFormMetadata();
  }, []);

  const handleProfileChange = (id) => {
    setProductProfileId(id);
    const selected = products.find((p) => p.id === parseInt(id));
    if (selected) {
      setProductName(`Consignment - ${selected.name}`);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    const src = locations.find((l) => l.name === sourceLoc) || { lat: 17.385, lon: 78.4867 };
    const dst = locations.find((l) => l.name === destLoc) || { lat: 19.076, lon: 72.8777 };

    const startTime = new Date();
    const expectedTime = new Date(startTime.getTime() + durationHours * 3600 * 1000);

    const payload = {
      product_name: productName,
      product_profile_id: parseInt(productProfileId),
      source_location: sourceLoc,
      source_lat: src.lat,
      source_lon: src.lon,
      destination_location: destLoc,
      destination_lat: dst.lat,
      destination_lon: dst.lon,
      start_time: startTime.toISOString(),
      expected_delivery_time: expectedTime.toISOString(),
      transport_type: transportType,
      notes: notes,
    };

    try {
      const res = await api.createShipment(payload);
      navigate(`/monitoring?shipment=${res.shipment.id}`);
    } catch (err) {
      setError(err.message || 'Failed to create shipment.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading creation form...</div>;
  }

  const selectedProfile = products.find((p) => p.id === parseInt(productProfileId));

  return (
    <div style={{ maxWidth: '800px' }}>
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Initiate New Transportation Journey</h2>
        </div>

        {error && <div className="alert-box alert-warning">{error}</div>}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Product Profile / Category *</label>
              <select
                className="form-control"
                value={productProfileId}
                onChange={(e) => handleProfileChange(e.target.value)}
                required
              >
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.category_label || p.category})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Consignment / Product Name *</label>
              <input
                type="text"
                className="form-control"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                required
              />
            </div>
          </div>

          {selectedProfile && (
            <div style={{ backgroundColor: '#f8fafc', padding: '14px 18px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '13px' }}>
              <div style={{ fontWeight: '600', color: '#0f766e', marginBottom: '4px' }}>
                Profile Safe Condition Bounds:
              </div>
              <div style={{ color: '#475569' }}>
                Temperature Range: <b>{selectedProfile.min_temp}°C</b> to <b>{selectedProfile.max_temp}°C</b> |
                Humidity Range: <b>{selectedProfile.min_humidity}%</b> to <b>{selectedProfile.max_humidity}%</b> |
                Sensitivity: <b>{selectedProfile.sensitivity}</b>
              </div>
            </div>
          )}

          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Origin Location *</label>
              <select
                className="form-control"
                value={sourceLoc}
                onChange={(e) => setSourceLoc(e.target.value)}
                required
              >
                {locations.map((loc) => (
                  <option key={loc.name} value={loc.name}>
                    {loc.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Destination Location *</label>
              <select
                className="form-control"
                value={destLoc}
                onChange={(e) => setDestLoc(e.target.value)}
                required
              >
                {locations.map((loc) => (
                  <option key={loc.name} value={loc.name}>
                    {loc.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Transport Vehicle / Carrier *</label>
              <select
                className="form-control"
                value={transportType}
                onChange={(e) => setTransportType(e.target.value)}
                required
              >
                <option value="Refrigerated Truck">Refrigerated Truck (Standard Cold-Chain)</option>
                <option value="Insulated Van">Insulated Van</option>
                <option value="Air Cargo">Air Cargo Reefer</option>
                <option value="Rail Reefer">Rail Reefer Container</option>
                <option value="Sea Container">Sea Reefer Container</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Planned Journey Duration (Hours) *</label>
              <input
                type="number"
                className="form-control"
                min="1"
                max="240"
                value={durationHours}
                onChange={(e) => setDurationHours(parseFloat(e.target.value) || 1)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Shipment Notes / Special Handling</label>
            <textarea
              className="form-control"
              rows="3"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Critical vaccine batch requiring continuous active refrigeration."
            />
          </div>

          <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Creating Shipment...' : 'Save & Proceed to Monitoring'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/shipments')}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

