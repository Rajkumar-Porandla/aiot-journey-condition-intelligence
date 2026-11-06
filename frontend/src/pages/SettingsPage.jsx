import React from 'react';
import { useAuth } from '../context/useAuth';

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div style={{ maxWidth: '800px' }}>
      <div className="card">
        <h2 className="card-title" style={{ marginBottom: '16px' }}>AIoT Platform & Operational Settings</h2>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ backgroundColor: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '700', color: '#1e293b', marginBottom: '8px' }}>User Session & Identity</h3>
            <div style={{ fontSize: '13px', color: '#475569', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div>Signed In As: <b>{user ? user.username : 'Anonymous'}</b></div>
              <div>Account Role: <b>{user ? user.role.toUpperCase() : 'OPERATOR'}</b></div>
              <div>Email: <b>{user ? user.email : 'N/A'}</b></div>
            </div>
          </div>

          <div style={{ backgroundColor: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '700', color: '#1e293b', marginBottom: '8px' }}>Course Project Architecture</h3>
            <div style={{ fontSize: '13px', color: '#475569', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div>System Model: <b>100% Software-Only AIoT Simulation Platform</b></div>
              <div>Backend Engine: <b>Python Flask REST API + SQLAlchemy ORM</b></div>
              <div>Database: <b>SQLite (WAL Mode Enabled)</b></div>
              <div>Machine Learning: <b>Scikit-learn Random Forest Classifier & Regressor</b></div>
              <div>Report Generation: <b>ReportLab PDF Rendering Engine</b></div>
              <div>Mapping: <b>Leaflet with OpenStreetMap Tiles (Zero Paid APIs)</b></div>
            </div>
          </div>

          <div style={{ backgroundColor: '#f0fdfa', padding: '16px', borderRadius: '8px', border: '1px solid #ccfbf1', fontSize: '12.5px', color: '#0f766e' }}>
            <b>Notice & Academic Transparency:</b> All IoT sensor telemetry (temperature, humidity, GPS tracking)
            is synthesized programmatically by an Ornstein-Uhlenbeck stochastic sensor model.
            Predictions represent simulated environmental quality risk estimates for academic demonstration.
          </div>
        </div>
      </div>
    </div>
  );
}

