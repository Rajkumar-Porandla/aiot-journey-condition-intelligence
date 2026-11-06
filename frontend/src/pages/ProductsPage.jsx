import React, { useEffect, useState } from 'react';
import { api } from '../services/api';

export default function ProductsPage() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingProduct, setEditingProduct] = useState(null);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    category: 'fruits_vegetables',
    min_temp: 4.0,
    max_temp: 12.0,
    min_humidity: 80.0,
    max_humidity: 95.0,
    sensitivity: 'Medium',
    description: '',
  });

  const loadProducts = async () => {
    try {
      const res = await api.getProducts();
      setProducts(res.products);
    } catch (err) {
      console.error('Failed to load profiles', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProducts();
  }, []);

  const handleEditClick = (p) => {
    setEditingProduct(p);
    setCreating(false);
    setFormData({
      name: p.name,
      category: p.category,
      min_temp: p.min_temp,
      max_temp: p.max_temp,
      min_humidity: p.min_humidity,
      max_humidity: p.max_humidity,
      sensitivity: p.sensitivity,
      description: p.description,
    });
  };

  const handleCreateClick = () => {
    setEditingProduct(null);
    setCreating(true);
    setFormData({
      name: '',
      category: 'fruits_vegetables',
      min_temp: 4.0,
      max_temp: 12.0,
      min_humidity: 80.0,
      max_humidity: 95.0,
      sensitivity: 'Medium',
      description: '',
    });
  };

  const handleFormSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingProduct) {
        await api.updateProduct(editingProduct.id, formData);
        alert('Product profile updated successfully.');
      } else {
        await api.createProduct(formData);
        alert('New product profile created successfully.');
      }
      setEditingProduct(null);
      setCreating(false);
      loadProducts();
    } catch (err) {
      alert(`Operation failed: ${err.message}`);
    }
  };

  if (loading) {
    return <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading product categories...</div>;
  }

  return (
    <div>
      {/* Intro Banner */}
      <div className="card" style={{ borderLeft: '4px solid #0d9488', marginBottom: '24px' }}>
        <h2 className="card-title">Product Category Environmental Condition Profiles</h2>
        <p style={{ fontSize: '13px', color: '#475569', marginTop: '4px', lineHeight: '1.5' }}>
          Configure safe storage bounds for the five primary cold-chain product categories: <b>Fruits and Vegetables</b>, <b>Dairy Products</b>,
          <b>Frozen Products</b>, <b>Pharmaceutical Products</b>, and <b>Flowers</b>.
          Exposure detection and Machine Learning risk models evaluate sensor readings against these profiles.
        </p>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '16px' }}>
        <button onClick={handleCreateClick} className="btn btn-primary">
          + Add Custom Product Profile
        </button>
      </div>

      {/* Profiles Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px', marginBottom: '24px' }}>
        {products.map((p) => (
          <div key={p.id} className="card" style={{ margin: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: '700', color: '#0f172a' }}>{p.name}</h3>
                <span className="badge badge-transit" style={{ marginTop: '4px' }}>
                  {p.category_label || p.category}
                </span>
              </div>
              {p.is_default && (
                <span className="badge badge-low" style={{ fontSize: '10px' }}>
                  Default
                </span>
              )}
            </div>

            <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '16px', minHeight: '36px' }}>
              {p.description || 'Configured transportation profile.'}
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px', borderTop: '1px solid #e2e8f0', paddingTop: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Safe Temp Range:</span>
                <span style={{ fontWeight: '700', color: '#0d9488' }}>
                  {p.min_temp}°C to {p.max_temp}°C
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Safe Humidity Range:</span>
                <span style={{ fontWeight: '700', color: '#3b82f6' }}>
                  {p.min_humidity}% to {p.max_humidity}%
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Sensitivity:</span>
                <span style={{ fontWeight: '600' }}>{p.sensitivity}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Associated Shipments:</span>
                <span>{p.shipment_count || 0} consignments</span>
              </div>
            </div>

            <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => handleEditClick(p)} className="btn btn-secondary btn-sm">
                Edit Thresholds
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Edit or Create Modal / Card */}
      {(editingProduct || creating) && (
        <div className="card" style={{ border: '2px solid #0d9488' }}>
          <h3 className="card-title" style={{ marginBottom: '16px' }}>
            {creating ? 'Create New Product Profile' : `Edit Profile: ${editingProduct.name}`}
          </h3>

          <form onSubmit={handleFormSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Profile Name *</label>
                <input
                  type="text"
                  className="form-control"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Product Category *</label>
                <select
                  className="form-control"
                  value={formData.category}
                  disabled={!!editingProduct}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                >
                  <option value="fruits_vegetables">Fruits and Vegetables</option>
                  <option value="dairy">Dairy Products</option>
                  <option value="frozen">Frozen Products</option>
                  <option value="pharmaceutical">Pharmaceutical Products</option>
                  <option value="flowers">Flowers</option>
                </select>
              </div>
            </div>

            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Minimum Safe Temperature (°C) *</label>
                <input
                  type="number"
                  step="0.5"
                  className="form-control"
                  value={formData.min_temp}
                  onChange={(e) => setFormData({ ...formData, min_temp: parseFloat(e.target.value) })}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Maximum Safe Temperature (°C) *</label>
                <input
                  type="number"
                  step="0.5"
                  className="form-control"
                  value={formData.max_temp}
                  onChange={(e) => setFormData({ ...formData, max_temp: parseFloat(e.target.value) })}
                  required
                />
              </div>
            </div>

            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Minimum Humidity (%) *</label>
                <input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  className="form-control"
                  value={formData.min_humidity}
                  onChange={(e) => setFormData({ ...formData, min_humidity: parseFloat(e.target.value) })}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Maximum Humidity (%) *</label>
                <input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  className="form-control"
                  value={formData.max_humidity}
                  onChange={(e) => setFormData({ ...formData, max_humidity: parseFloat(e.target.value) })}
                  required
                />
              </div>
            </div>

            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Sensitivity Rating *</label>
                <select
                  className="form-control"
                  value={formData.sensitivity}
                  onChange={(e) => setFormData({ ...formData, sensitivity: e.target.value })}
                >
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                  <option value="Very High">Very High</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Description / Handling Guidelines</label>
                <input
                  type="text"
                  className="form-control"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
              <button type="submit" className="btn btn-primary">
                Save Product Profile
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setEditingProduct(null);
                  setCreating(false);
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

