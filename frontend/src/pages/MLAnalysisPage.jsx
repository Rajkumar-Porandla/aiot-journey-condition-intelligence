import React, { useEffect, useState } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { api } from '../services/api';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

export default function MLAnalysisPage() {
  const [metrics, setMetrics] = useState(null);
  const [shipments, setShipments] = useState([]);
  const [selectedShipmentId, setSelectedShipmentId] = useState('');
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [predicting, setPredicting] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        const [metricRes, shipRes] = await Promise.all([api.getMLMetrics(), api.getShipments()]);
        setMetrics(metricRes.metrics);
        setShipments(shipRes.shipments);
        if (shipRes.shipments.length > 0) {
          setSelectedShipmentId(shipRes.shipments[0].id);
        }
      } catch (err) {
        console.error('Failed to load ML analysis data', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  useEffect(() => {
    if (!selectedShipmentId) return;
    async function loadPrediction() {
      try {
        const res = await api.getShipmentPredictions(selectedShipmentId);
        setPrediction(res.latest_prediction);
      } catch (err) {
        console.error('Failed to load predictions', err);
      }
    }
    loadPrediction();
  }, [selectedShipmentId]);

  const handleRunModel = async () => {
    if (!selectedShipmentId) return;
    setPredicting(true);
    try {
      const res = await api.predictShipment(selectedShipmentId);
      setPrediction(res.prediction);
    } catch (err) {
      alert(`Model execution failed: ${err.message}`);
    } finally {
      setPredicting(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading Machine Learning Engine...</div>;
  }

  // Feature Importance chart data from trained model metrics
  const importanceList = metrics?.permutation_importance?.regressor || [];
  const importanceChartData = {
    labels: importanceList.map((i) => i.label),
    datasets: [
      {
        label: 'Permutation Feature Importance (Drop in R² on Held-out Journeys)',
        data: importanceList.map((i) => i.importance),
        backgroundColor: '#0d9488',
        borderRadius: 4,
      },
    ],
  };

  // Local explanation contributions chart data for selected shipment
  const contributions = prediction?.explanation?.score_contributions || [];
  const localChartData = {
    labels: contributions.map((c) => c.label),
    datasets: [
      {
        label: 'Local Feature Impact on Risk Score (Points)',
        data: contributions.map((c) => c.contribution),
        backgroundColor: contributions.map((c) => (c.contribution > 0 ? '#ef4444' : '#22c55e')),
        borderRadius: 4,
      },
    ],
  };

  return (
    <div>
      {/* Module Banner */}
      <div className="card" style={{ borderLeft: '4px solid #0d9488', marginBottom: '24px' }}>
        <h2 className="card-title">Dual Machine Learning Prediction Engine</h2>
        <p style={{ fontSize: '13px', color: '#475569', marginTop: '4px', lineHeight: '1.5' }}>
          This system deploys two genuine, trained Random Forest models: a <b>Random Forest Classifier</b> for qualitative risk tiering
          (Low / Medium / High Risk) and a <b>Random Forest Regressor</b> for numerical risk score estimation (0–100).
          Trained on over 5,000 synthetic transportation journeys using grouped validation by journey ID to prevent data leakage.
        </p>
      </div>

      {/* Trained Model Performance KPIs */}
      {metrics && (
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">Classifier Accuracy</span>
            <span className="stat-value" style={{ color: '#16a34a' }}>
              {(metrics.classification.accuracy * 100).toFixed(1)}%
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Classifier Macro F1</span>
            <span className="stat-value" style={{ color: '#0d9488' }}>
              {metrics.classification.f1_macro.toFixed(3)}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Regressor R² Score</span>
            <span className="stat-value" style={{ color: '#0369a1' }}>
              {metrics.regression.r2.toFixed(3)}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Regressor MAE</span>
            <span className="stat-value" style={{ color: '#475569' }}>
              {metrics.regression.mae.toFixed(2)} pts
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Training Journeys</span>
            <span className="stat-value">{metrics.dataset.journeys.toLocaleString()}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Model Version</span>
            <span className="stat-value" style={{ fontSize: '15px', color: '#64748b', marginTop: '6px' }}>
              {metrics.model_version}
            </span>
          </div>
        </div>
      )}

      {/* Global Permutation Feature Importance */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Global Feature Importance (Permutation on Held-Out Test Journeys)</h3>
            <p style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
              Measures the loss in predictive performance when each input feature group is randomly permuted.
            </p>
          </div>
        </div>
        <div style={{ height: '280px' }}>
          <Bar
            data={importanceChartData}
            options={{
              indexAxis: 'y',
              maintainAspectRatio: false,
              plugins: { legend: { display: false } },
            }}
          />
        </div>
      </div>

      {/* Local Prediction Explanation Section */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Local Explainable ML Prediction (Single Shipment Inspection)</h3>
            <p style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
              Uses exact tree path decomposition (TreeInterpreter / Saabas method) to calculate every feature's contribution.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <select
              className="form-control"
              style={{ width: '280px' }}
              value={selectedShipmentId}
              onChange={(e) => setSelectedShipmentId(e.target.value)}
            >
              {shipments.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.shipment_code} – {s.product_name}
                </option>
              ))}
            </select>

            <button onClick={handleRunModel} className="btn btn-primary btn-sm" disabled={predicting}>
              {predicting ? 'Evaluating Model...' : 'Run Prediction'}
            </button>
          </div>
        </div>

        {prediction ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px', marginBottom: '24px' }}>
              <div style={{ backgroundColor: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div className="stat-label">Predicted Risk Category</div>
                <div style={{ marginTop: '8px' }}>
                  <span className={`badge ${prediction.risk_class === 'Low Risk' ? 'badge-low' : prediction.risk_class === 'Medium Risk' ? 'badge-medium' : 'badge-high'}`} style={{ fontSize: '14px', padding: '6px 12px' }}>
                    {prediction.risk_class}
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '10px' }}>
                  Class Probabilities:
                  {Object.entries(prediction.class_probabilities || {}).map(([k, v]) => (
                    <span key={k} style={{ marginLeft: '6px', fontWeight: '600' }}>
                      {k}: {(v * 100).toFixed(0)}%
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ backgroundColor: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div className="stat-label">Numerical Risk Score</div>
                <div style={{ fontSize: '28px', fontWeight: '700', color: prediction.risk_score > 50 ? '#dc2626' : '#0d9488', marginTop: '4px' }}>
                  {prediction.risk_score.toFixed(1)} <span style={{ fontSize: '14px', color: '#64748b' }}>/ 100</span>
                </div>
                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
                  Baseline Dataset Mean: <b>{prediction.explanation?.score_base?.toFixed(1) || '33.5'} pts</b>
                </div>
              </div>
            </div>

            {/* Tree Path Contributions Chart */}
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ fontSize: '14px', fontWeight: '700', color: '#1e293b', marginBottom: '8px' }}>
                Feature Contribution Breakdown (Tree Path Contributions)
              </h4>
              <div style={{ height: '240px' }}>
                <Bar
                  data={localChartData}
                  options={{
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { title: { display: true, text: 'Score Impact (Points)' } } },
                  }}
                />
              </div>
            </div>

            {/* Natural Language Explanations */}
            {prediction.explanation?.summary && (
              <div style={{ backgroundColor: '#f0fdfa', padding: '16px 20px', borderRadius: '8px', border: '1px solid #ccfbf1' }}>
                <h4 style={{ fontSize: '13px', fontWeight: '700', color: '#0f766e', marginBottom: '6px' }}>
                  Automated Journey Risk Summary:
                </h4>
                <ul style={{ paddingLeft: '18px', fontSize: '13px', color: '#134e4a', lineHeight: '1.6' }}>
                  {prediction.explanation.summary.map((line, idx) => (
                    <li key={idx}>{line}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
            No prediction recorded yet for this shipment. Click "Run Prediction" above to execute the trained models.
          </div>
        )}
      </div>
    </div>
  );
}

