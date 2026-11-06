import React, { useEffect, useState } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { api } from '../services/api';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

export default function WhatIfPage() {
  const [shipments, setShipments] = useState([]);
  const [selectedShipmentId, setSelectedShipmentId] = useState('');
  const [selectedShipment, setSelectedShipment] = useState(null);
  const [loading, setLoading] = useState(true);

  // Slider inputs
  const [avgTemp, setAvgTemp] = useState(4.0);
  const [maxTemp, setMaxTemp] = useState(6.0);
  const [avgHumidity, setAvgHumidity] = useState(70.0);
  const [tempExpHours, setTempExpHours] = useState(0.0);
  const [humExpHours, setHumExpHours] = useState(0.0);
  const [journeyDuration, setJourneyDuration] = useState(12.0);
  const [violationCount, setViolationCount] = useState(0);

  const [scenarioName, setScenarioName] = useState('Refrigeration Failure Scenario');
  const [result, setResult] = useState(null);
  const [simulating, setSimulating] = useState(false);
  const [savedScenarios, setSavedScenarios] = useState([]);

  useEffect(() => {
    async function loadShipmentsList() {
      try {
        const res = await api.getShipments();
        setShipments(res.shipments);
        if (res.shipments.length > 0) {
          setSelectedShipmentId(res.shipments[0].id);
        }
      } catch (err) {
        console.error('Failed to load shipments', err);
      } finally {
        setLoading(false);
      }
    }
    loadShipmentsList();
  }, []);

  useEffect(() => {
    if (!selectedShipmentId) return;

    async function fetchShipmentDetails() {
      try {
        const [shipRes, scenRes] = await Promise.all([
          api.getShipment(selectedShipmentId),
          api.getScenarios(selectedShipmentId),
        ]);
        const s = shipRes.shipment;
        setSelectedShipment(s);
        setSavedScenarios(scenRes.scenarios || []);

        const stats = s.stats || {};
        const p = s.product_profile;
        setAvgTemp(stats.avg_temp !== null && stats.avg_temp !== undefined ? stats.avg_temp : 4.0);
        setMaxTemp(stats.max_temp !== null && stats.max_temp !== undefined ? stats.max_temp : 6.0);
        setAvgHumidity(stats.avg_humidity !== null && stats.avg_humidity !== undefined ? stats.avg_humidity : 70.0);
        setTempExpHours(stats.temp_exposure_hours || 0.0);
        setHumExpHours(stats.humidity_exposure_hours || 0.0);
        setJourneyDuration(stats.journey_duration_hours || 12.0);
        setViolationCount(stats.violation_count || 0);

        // Run baseline comparison immediately
        runSimulation(s.id, {
          avg_temp: stats.avg_temp || 4.0,
          max_temp: stats.max_temp || 6.0,
          avg_humidity: stats.avg_humidity || 70.0,
          temp_exposure_hours: stats.temp_exposure_hours || 0.0,
          humidity_exposure_hours: stats.humidity_exposure_hours || 0.0,
          journey_duration_hours: stats.journey_duration_hours || 12.0,
          violation_count: stats.violation_count || 0,
        });
      } catch (err) {
        console.error('Error fetching details', err);
      }
    }
    fetchShipmentDetails();
  }, [selectedShipmentId]);

  const runSimulation = async (shipmentId, overrideParams = null, saveAs = null) => {
    setSimulating(true);
    const payload = overrideParams || {
      shipment_id: shipmentId || selectedShipmentId,
      avg_temp: avgTemp,
      max_temp: maxTemp,
      avg_humidity: avgHumidity,
      temp_exposure_hours: tempExpHours,
      humidity_exposure_hours: humExpHours,
      journey_duration_hours: journeyDuration,
      violation_count: violationCount,
      name: saveAs,
    };
    if (!payload.shipment_id) payload.shipment_id = selectedShipmentId;

    try {
      const res = await api.runWhatIf(payload);
      setResult(res);
      if (saveAs) {
        const scenRes = await api.getScenarios(selectedShipmentId);
        setSavedScenarios(scenRes.scenarios || []);
        alert(`Scenario "${saveAs}" saved successfully!`);
      }
    } catch (err) {
      alert(`Simulation error: ${err.message}`);
    } finally {
      setSimulating(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading What-If Simulator...</div>;
  }

  const comparisonChartData = result
    ? {
        labels: ['Baseline / Original', 'What-If Simulation'],
        datasets: [
          {
            label: 'Risk Score (0–100)',
            data: [result.original_prediction.risk_score, result.simulated_prediction.risk_score],
            backgroundColor: ['#0d9488', result.simulated_prediction.risk_score > 50 ? '#ef4444' : '#f59e0b'],
            borderRadius: 6,
          },
        ],
      }
    : null;

  return (
    <div>
      {/* Intro Banner */}
      <div className="card" style={{ borderLeft: '4px solid #0d9488', marginBottom: '24px' }}>
        <h2 className="card-title">What-If Journey Environmental Condition Simulator</h2>
        <p style={{ fontSize: '13px', color: '#475569', marginTop: '4px', lineHeight: '1.5' }}>
          Simulate counterfactual transportation conditions for any shipment without altering original stored sensor readings.
          Adjust temperature, humidity, delay duration, and violation counts to evaluate risk outcomes under hypothetical failure or optimization scenarios.
        </p>
      </div>

      {/* Select Shipment */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label className="form-label" style={{ margin: 0 }}>Select Target Shipment:</label>
          <select
            className="form-control"
            style={{ width: '320px' }}
            value={selectedShipmentId}
            onChange={(e) => setSelectedShipmentId(e.target.value)}
          >
            {shipments.map((s) => (
              <option key={s.id} value={s.id}>
                {s.shipment_code} – {s.product_name} ({s.category_label || s.category})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '24px' }}>
        {/* Controls Column */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: '16px' }}>Interactive Condition Sliders</h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <label className="form-label">Average Temperature: {avgTemp.toFixed(1)}°C</label>
                <span style={{ fontSize: '12px', color: '#64748b' }}>Original: {result?.original_features?.avg_temp?.toFixed(1) || '0'}°C</span>
              </div>
              <input
                type="range"
                min="-30"
                max="40"
                step="0.5"
                value={avgTemp}
                onChange={(e) => setAvgTemp(parseFloat(e.target.value))}
              />
            </div>

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <label className="form-label">Peak Temperature: {maxTemp.toFixed(1)}°C</label>
                <span style={{ fontSize: '12px', color: '#64748b' }}>Original: {result?.original_features?.max_temp?.toFixed(1) || '0'}°C</span>
              </div>
              <input
                type="range"
                min="-25"
                max="50"
                step="0.5"
                value={maxTemp}
                onChange={(e) => setMaxTemp(parseFloat(e.target.value))}
              />
            </div>

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <label className="form-label">Average Humidity: {avgHumidity.toFixed(0)}% RH</label>
                <span style={{ fontSize: '12px', color: '#64748b' }}>Original: {result?.original_features?.avg_humidity?.toFixed(0) || '0'}%</span>
              </div>
              <input
                type="range"
                min="10"
                max="100"
                step="1"
                value={avgHumidity}
                onChange={(e) => setAvgHumidity(parseFloat(e.target.value))}
              />
            </div>

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <label className="form-label">Temperature Exposure Duration: {tempExpHours.toFixed(1)} hrs</label>
                <span style={{ fontSize: '12px', color: '#64748b' }}>Original: {result?.original_features?.temp_exposure_hours?.toFixed(1) || '0'}h</span>
              </div>
              <input
                type="range"
                min="0"
                max={journeyDuration}
                step="0.5"
                value={tempExpHours}
                onChange={(e) => setTempExpHours(parseFloat(e.target.value))}
              />
            </div>

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <label className="form-label">Journey Duration (Including Delays): {journeyDuration.toFixed(1)} hrs</label>
                <span style={{ fontSize: '12px', color: '#64748b' }}>Original: {result?.original_features?.journey_duration_hours?.toFixed(1) || '0'}h</span>
              </div>
              <input
                type="range"
                min="2"
                max="120"
                step="1"
                value={journeyDuration}
                onChange={(e) => setJourneyDuration(parseFloat(e.target.value))}
              />
            </div>

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <label className="form-label">Environmental Violations: {violationCount}</label>
                <span style={{ fontSize: '12px', color: '#64748b' }}>Original: {result?.original_features?.violation_count || '0'}</span>
              </div>
              <input
                type="range"
                min="0"
                max="30"
                step="1"
                value={violationCount}
                onChange={(e) => setViolationCount(parseInt(e.target.value))}
              />
            </div>

            <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
              <button onClick={() => runSimulation()} className="btn btn-primary" style={{ flex: 1 }} disabled={simulating}>
                {simulating ? 'Evaluating...' : 'Re-Run Model Simulation'}
              </button>
            </div>

            <div style={{ display: 'flex', gap: '8px', paddingTop: '12px', borderTop: '1px solid #e2e8f0' }}>
              <input
                type="text"
                className="form-control"
                placeholder="Scenario Name (e.g. Compressor Outage)"
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => runSimulation(null, null, scenarioName)}
              >
                Save
              </button>
            </div>
          </div>
        </div>

        {/* Results & Comparison Column */}
        {result && (
          <div className="card">
            <h3 className="card-title" style={{ marginBottom: '16px' }}>What-If Predictive Risk Comparison</h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
              <div style={{ backgroundColor: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div className="stat-label">Original Baseline</div>
                <div style={{ marginTop: '6px' }}>
                  <span className={`badge ${result.original_prediction.risk_class === 'Low Risk' ? 'badge-low' : result.original_prediction.risk_class === 'Medium Risk' ? 'badge-medium' : 'badge-high'}`}>
                    {result.original_prediction.risk_class}
                  </span>
                </div>
                <div style={{ fontSize: '24px', fontWeight: '700', color: '#0d9488', marginTop: '8px' }}>
                  {result.original_prediction.risk_score.toFixed(1)} <span style={{ fontSize: '13px', color: '#64748b' }}>/ 100</span>
                </div>
              </div>

              <div style={{ backgroundColor: '#f0fdfa', padding: '16px', borderRadius: '8px', border: '1px solid #5eead4' }}>
                <div className="stat-label">Simulated Outcome</div>
                <div style={{ marginTop: '6px' }}>
                  <span className={`badge ${result.simulated_prediction.risk_class === 'Low Risk' ? 'badge-low' : result.simulated_prediction.risk_class === 'Medium Risk' ? 'badge-medium' : 'badge-high'}`}>
                    {result.simulated_prediction.risk_class}
                  </span>
                </div>
                <div style={{ fontSize: '24px', fontWeight: '700', color: result.simulated_prediction.risk_score > 50 ? '#dc2626' : '#0d9488', marginTop: '8px' }}>
                  {result.simulated_prediction.risk_score.toFixed(1)} <span style={{ fontSize: '13px', color: '#64748b' }}>/ 100</span>
                </div>
              </div>
            </div>

            {/* Delta Indicator */}
            <div style={{ padding: '12px 16px', borderRadius: '6px', backgroundColor: result.score_difference > 0 ? '#fee2e2' : '#dcfce7', color: result.score_difference > 0 ? '#991b1b' : '#15803d', fontWeight: '600', fontSize: '13px', marginBottom: '20px' }}>
              Predicted Risk Shift: {result.score_difference > 0 ? `+${result.score_difference.toFixed(1)} points (Higher Risk)` : `${result.score_difference.toFixed(1)} points (Lower Risk)`}
              {result.risk_class_changed && ' — Risk category transitioned!'}
            </div>

            {/* Comparison Bar Chart */}
            <div style={{ height: '200px', marginBottom: '20px' }}>
              <Bar data={comparisonChartData} options={{ maintainAspectRatio: false, scales: { y: { min: 0, max: 100 } } }} />
            </div>

            {/* Shift Factors */}
            <h4 style={{ fontSize: '13px', fontWeight: '700', color: '#1e293b', marginBottom: '8px' }}>
              Modified Input Parameters:
            </h4>
            <div className="table-responsive">
              <table className="data-table" style={{ fontSize: '12px' }}>
                <thead>
                  <tr>
                    <th>Feature</th>
                    <th>Original</th>
                    <th>Simulated</th>
                    <th>Difference</th>
                  </tr>
                </thead>
                <tbody>
                  {result.shift_factors.map((f) => (
                    <tr key={f.feature}>
                      <td><b>{f.label}</b></td>
                      <td>{f.original_value}</td>
                      <td>{f.modified_value}</td>
                      <td style={{ color: f.delta > 0 ? '#dc2626' : '#16a34a', fontWeight: '600' }}>
                        {f.delta > 0 ? `+${f.delta}` : f.delta}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Saved Scenarios Table */}
      {savedScenarios.length > 0 && (
        <div className="card" style={{ marginTop: '24px' }}>
          <div className="card-header">
            <h3 className="card-title">Saved What-If Journey Scenarios</h3>
          </div>
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Scenario Name</th>
                  <th>Simulated Class</th>
                  <th>Simulated Score</th>
                  <th>Created At</th>
                </tr>
              </thead>
              <tbody>
                {savedScenarios.map((sc) => (
                  <tr key={sc.id}>
                    <td style={{ fontWeight: '600' }}>{sc.name}</td>
                    <td>
                      <span className={`badge ${sc.simulated_prediction.risk_class === 'Low Risk' ? 'badge-low' : sc.simulated_prediction.risk_class === 'Medium Risk' ? 'badge-medium' : 'badge-high'}`}>
                        {sc.simulated_prediction.risk_class}
                      </span>
                    </td>
                    <td style={{ fontWeight: '700' }}>{sc.simulated_prediction.risk_score.toFixed(1)}/100</td>
                    <td>{new Date(sc.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

