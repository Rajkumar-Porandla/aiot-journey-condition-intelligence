import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams, NavLink } from 'react-router-dom';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import { Line } from 'react-chartjs-2';
import L from 'leaflet';
import { api } from '../services/api';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

export default function MonitoringPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedShipmentId = searchParams.get('shipment');

  const [shipments, setShipments] = useState([]);
  const [currentShipment, setCurrentShipment] = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [simMode, setSimMode] = useState('NORMAL');
  const [intervalSec, setIntervalSec] = useState(2);
  const [stepMin, setStepMin] = useState(15);
  const [actionLoading, setActionLoading] = useState(false);

  const mapContainerRef = useRef(null);
  const leafletMapRef = useRef(null);
  const routePolylineRef = useRef(null);
  const truckMarkerRef = useRef(null);

  // Load shipments dropdown
  useEffect(() => {
    async function loadShipmentsList() {
      try {
        const res = await api.getShipments();
        setShipments(res.shipments);
        if (res.shipments.length > 0) {
          const targetId = selectedShipmentId || res.shipments[0].id;
          if (!selectedShipmentId) {
            setSearchParams({ shipment: targetId });
          }
        }
      } catch (err) {
        console.error('Failed to load shipments list', err);
      } finally {
        setLoading(false);
      }
    }
    loadShipmentsList();
  }, []);

  // Poll current shipment telemetry & alerts
  useEffect(() => {
    if (!selectedShipmentId) return;

    let isMounted = true;

    async function fetchTelemetryData() {
      try {
        const [shipmentRes, readingsRes, alertsRes, predRes] = await Promise.all([
          api.getShipment(selectedShipmentId),
          api.getReadings(selectedShipmentId, 'limit=100'),
          api.getShipmentAlerts(selectedShipmentId),
          api.getShipmentPredictions(selectedShipmentId),
        ]);

        if (!isMounted) return;
        setCurrentShipment(shipmentRes.shipment);
        setTelemetry(readingsRes);
        setAlerts(alertsRes.alerts);
        setPrediction(predRes.latest_prediction);
        setSimMode(shipmentRes.shipment.simulation?.mode || 'NORMAL');
      } catch (err) {
        console.error('Error fetching telemetry', err);
      }
    }

    fetchTelemetryData();
    const timer = setInterval(fetchTelemetryData, 2000); // 2-sec real-time refresh
    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, [selectedShipmentId]);

  // Leaflet Map Initialization & Real-Time Marker Updates
  useEffect(() => {
    if (!currentShipment || !mapContainerRef.current) return;

    if (!leafletMapRef.current) {
      const map = L.map(mapContainerRef.current).setView(
        [currentShipment.source_lat, currentShipment.source_lon],
        6
      );

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(map);

      leafletMapRef.current = map;
    }

    const map = leafletMapRef.current;

    // Draw Source and Destination markers
    L.circleMarker([currentShipment.source_lat, currentShipment.source_lon], {
      color: '#16a34a',
      radius: 8,
      fillOpacity: 0.9,
    })
      .addTo(map)
      .bindPopup(`<b>Origin:</b> ${currentShipment.source_location}`);

    L.circleMarker([currentShipment.destination_lat, currentShipment.destination_lon], {
      color: '#dc2626',
      radius: 8,
      fillOpacity: 0.9,
    })
      .addTo(map)
      .bindPopup(`<b>Destination:</b> ${currentShipment.destination_location}`);

    // Update Truck / Current Position Marker
    const latest = telemetry?.latest_reading;
    const currentLat = latest ? latest.latitude : currentShipment.source_lat;
    const currentLon = latest ? latest.longitude : currentShipment.source_lon;

    if (!truckMarkerRef.current) {
      const icon = L.divIcon({
        className: 'truck-icon',
        html: `<div style="background:#0d9488;color:white;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 0 10px rgba(13,148,136,0.6);font-size:14px;border:2px solid white;">🚚</div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15],
      });
      truckMarkerRef.current = L.marker([currentLat, currentLon], { icon }).addTo(map);
    } else {
      truckMarkerRef.current.setLatLng([currentLat, currentLon]);
    }

    // Polyline of route history
    if (telemetry?.readings?.length > 1) {
      const latlngs = telemetry.readings.map((r) => [r.latitude, r.longitude]);
      if (routePolylineRef.current) {
        routePolylineRef.current.setLatLngs(latlngs);
      } else {
        routePolylineRef.current = L.polyline(latlngs, { color: '#0d9488', weight: 4, opacity: 0.8 }).addTo(map);
      }
    }
  }, [currentShipment, telemetry]);

  const handleControl = async (action) => {
    if (!currentShipment) return;
    setActionLoading(true);
    try {
      if (action === 'start') {
        await api.startSimulation(currentShipment.id, {
          mode: simMode,
          interval_seconds: intervalSec,
          step_minutes: stepMin,
        });
      } else if (action === 'pause') {
        await api.pauseSimulation(currentShipment.id);
      } else if (action === 'resume') {
        await api.resumeSimulation(currentShipment.id);
      } else if (action === 'stop') {
        await api.stopSimulation(currentShipment.id);
      } else if (action === 'complete') {
        await api.completeSimulation(currentShipment.id);
      }
    } catch (err) {
      alert(`Simulation action error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handlePredictNow = async () => {
    if (!currentShipment) return;
    try {
      const res = await api.predictShipment(currentShipment.id);
      setPrediction(res.prediction);
      alert(`ML Quality Assessment completed: ${res.prediction.risk_class} (${res.prediction.risk_score.toFixed(1)}/100)`);
    } catch (err) {
      alert(`Prediction failed: ${err.message}`);
    }
  };

  if (loading) {
    return <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading monitoring center...</div>;
  }

  const readingsList = telemetry?.readings || [];
  const profile = currentShipment?.product_profile;
  const thresholds = currentShipment?.stats ? currentShipment.stats : {};

  // Temperature chart config
  const tempChartData = {
    labels: readingsList.map((r) => `T+${r.sequence * 15}m`),
    datasets: [
      {
        label: 'Recorded Temp (°C)',
        data: readingsList.map((r) => r.temperature),
        borderColor: '#0d9488',
        backgroundColor: 'rgba(13, 148, 136, 0.1)',
        tension: 0.2,
        pointRadius: 2,
      },
      ...(telemetry?.profile
        ? [
            {
              label: 'Max Safe Temp (°C)',
              data: readingsList.map(() => telemetry.profile.max_temp),
              borderColor: '#ef4444',
              borderDash: [5, 5],
              pointRadius: 0,
            },
            {
              label: 'Min Safe Temp (°C)',
              data: readingsList.map(() => telemetry.profile.min_temp),
              borderColor: '#3b82f6',
              borderDash: [5, 5],
              pointRadius: 0,
            },
          ]
        : []),
    ],
  };

  // Humidity chart config
  const humChartData = {
    labels: readingsList.map((r) => `T+${r.sequence * 15}m`),
    datasets: [
      {
        label: 'Recorded Humidity (%)',
        data: readingsList.map((r) => r.humidity),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.2,
        pointRadius: 2,
      },
      ...(telemetry?.profile
        ? [
            {
              label: 'Max Safe Humidity (%)',
              data: readingsList.map(() => telemetry.profile.max_humidity),
              borderColor: '#f59e0b',
              borderDash: [5, 5],
              pointRadius: 0,
            },
            {
              label: 'Min Safe Humidity (%)',
              data: readingsList.map(() => telemetry.profile.min_humidity),
              borderColor: '#64748b',
              borderDash: [5, 5],
              pointRadius: 0,
            },
          ]
        : []),
    ],
  };

  return (
    <div>
      {/* Top Selector Bar */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <label className="form-label" style={{ margin: 0 }}>Select Shipment:</label>
            <select
              className="form-control"
              style={{ width: '280px' }}
              value={selectedShipmentId || ''}
              onChange={(e) => setSearchParams({ shipment: e.target.value })}
            >
              {shipments.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.shipment_code} – {s.product_name} ({s.status})
                </option>
              ))}
            </select>
          </div>

          {currentShipment && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className={`badge ${currentShipment.status === 'In Transit' ? 'badge-transit' : currentShipment.status === 'Completed' ? 'badge-completed' : 'badge-medium'}`}>
                Status: {currentShipment.status}
              </span>
              <span className="badge badge-low" style={{ background: '#f1f5f9', color: '#334155' }}>
                Progress: {(currentShipment.simulation.progress * 100).toFixed(1)}%
              </span>
              <button onClick={handlePredictNow} className="btn btn-primary btn-sm">
                ⚡ Run ML Assessment Now
              </button>
            </div>
          )}
        </div>
      </div>

      {currentShipment && (
        <>
          {/* Virtual IoT Simulator Controls */}
          <div className="card" style={{ borderLeft: '4px solid #0d9488' }}>
            <div className="card-header" style={{ marginBottom: '14px' }}>
              <div>
                <h3 className="card-title">IoT Telemetry Simulation Engine</h3>
                <p style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                  Programmatically generates realistic IoT environmental readings, temperature excursions, and GPS progression.
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                {currentShipment.status === 'In Transit' ? (
                  <>
                    <button onClick={() => handleControl('pause')} className="btn btn-secondary btn-sm" disabled={actionLoading}>
                      ⏸ Pause Simulation
                    </button>
                    <button onClick={() => handleControl('stop')} className="btn btn-danger btn-sm" disabled={actionLoading}>
                      ⏹ Stop Journey
                    </button>
                    <button onClick={() => handleControl('complete')} className="btn btn-primary btn-sm" disabled={actionLoading}>
                      ✓ Mark Completed
                    </button>
                  </>
                ) : currentShipment.status === 'Paused' ? (
                  <>
                    <button onClick={() => handleControl('resume')} className="btn btn-primary btn-sm" disabled={actionLoading}>
                      ▶ Resume Simulation
                    </button>
                    <button onClick={() => handleControl('stop')} className="btn btn-danger btn-sm" disabled={actionLoading}>
                      ⏹ Stop
                    </button>
                  </>
                ) : (
                  <button onClick={() => handleControl('start')} className="btn btn-primary btn-sm" disabled={actionLoading}>
                    🚀 Start Virtual Journey
                  </button>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'center', backgroundColor: '#f8fafc', padding: '12px 16px', borderRadius: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '13px', fontWeight: '600' }}>Simulation Mode:</span>
                <select
                  className="form-control"
                  style={{ width: '130px', padding: '5px 8px', fontSize: '12.5px' }}
                  value={simMode}
                  onChange={(e) => setSimMode(e.target.value)}
                  disabled={currentShipment.status === 'In Transit'}
                >
                  <option value="NORMAL">NORMAL</option>
                  <option value="WARNING">WARNING</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '13px', fontWeight: '600' }}>Tick Rate:</span>
                <select
                  className="form-control"
                  style={{ width: '120px', padding: '5px 8px', fontSize: '12.5px' }}
                  value={intervalSec}
                  onChange={(e) => setIntervalSec(parseFloat(e.target.value))}
                  disabled={currentShipment.status === 'In Transit'}
                >
                  <option value={1}>1 sec / reading</option>
                  <option value={2}>2 sec / reading</option>
                  <option value={5}>5 sec / reading</option>
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '13px', fontWeight: '600' }}>Step Jump:</span>
                <select
                  className="form-control"
                  style={{ width: '120px', padding: '5px 8px', fontSize: '12.5px' }}
                  value={stepMin}
                  onChange={(e) => setStepMin(parseFloat(e.target.value))}
                  disabled={currentShipment.status === 'In Transit'}
                >
                  <option value={5}>+5 min virtual</option>
                  <option value={15}>+15 min virtual</option>
                  <option value={30}>+30 min virtual</option>
                </select>
              </div>

              <div style={{ fontSize: '12px', color: '#64748b', marginLeft: 'auto' }}>
                Total Points: <b>{telemetry?.total_readings || 0}</b> | Elapsed Time: <b>{currentShipment.simulation.elapsed_minutes?.toFixed(0)} min</b>
              </div>
            </div>
          </div>

          {/* Current Reading & ML Risk Banner */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '20px' }}>
            <div className="card" style={{ padding: '16px' }}>
              <div className="stat-label">Current Temperature</div>
              <div className="stat-value" style={{ color: '#0d9488' }}>
                {telemetry?.latest_reading ? `${telemetry.latest_reading.temperature.toFixed(1)}°C` : 'N/A'}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                Target: {telemetry?.profile?.min_temp}°C to {telemetry?.profile?.max_temp}°C
              </div>
            </div>

            <div className="card" style={{ padding: '16px' }}>
              <div className="stat-label">Current Humidity</div>
              <div className="stat-value" style={{ color: '#3b82f6' }}>
                {telemetry?.latest_reading ? `${telemetry.latest_reading.humidity.toFixed(1)}%` : 'N/A'}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                Target: {telemetry?.profile?.min_humidity}% to {telemetry?.profile?.max_humidity}%
              </div>
            </div>

            <div className="card" style={{ padding: '16px' }}>
              <div className="stat-label">Predicted Risk Class</div>
              <div className="stat-value" style={{ fontSize: '20px', marginTop: '4px' }}>
                {prediction ? (
                  <span className={`badge ${prediction.risk_class === 'Low Risk' ? 'badge-low' : prediction.risk_class === 'Medium Risk' ? 'badge-medium' : 'badge-high'}`}>
                    {prediction.risk_class}
                  </span>
                ) : (
                  <span style={{ color: '#94a3b8' }}>Awaiting Run</span>
                )}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b', marginTop: '6px' }}>
                ML Score: <b>{prediction ? `${prediction.risk_score.toFixed(1)} / 100` : 'N/A'}</b>
              </div>
            </div>

            <div className="card" style={{ padding: '16px' }}>
              <div className="stat-label">Active Exposure Alerts</div>
              <div className="stat-value" style={{ color: alerts.some((a) => a.is_active) ? '#dc2626' : '#16a34a' }}>
                {alerts.filter((a) => a.is_active).length}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                Total Alerts Triggered: {alerts.length}
              </div>
            </div>
          </div>

          {/* Interactive Map */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Live Geographic Journey Progression</h3>
              <span style={{ fontSize: '12px', color: '#64748b' }}>
                Route: {currentShipment.source_location} → {currentShipment.destination_location}
              </span>
            </div>
            <div ref={mapContainerRef} style={{ height: '320px', width: '100%', borderRadius: '8px', zIndex: 1 }} />
          </div>

          {/* Dual Real-Time Telemetry Charts */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '20px', marginBottom: '20px' }}>
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Temperature Telemetry History</h3>
              </div>
              <div style={{ height: '260px' }}>
                <Line
                  data={tempChartData}
                  options={{
                    maintainAspectRatio: false,
                    scales: { y: { title: { display: true, text: 'Temperature (°C)' } } },
                  }}
                />
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Relative Humidity History</h3>
              </div>
              <div style={{ height: '260px' }}>
                <Line
                  data={humChartData}
                  options={{
                    maintainAspectRatio: false,
                    scales: { y: { title: { display: true, text: 'Humidity (% RH)' }, min: 0, max: 100 } },
                  }}
                />
              </div>
            </div>
          </div>

          {/* Active Exposure Incidents */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Harmful Exposure Incidents & Active Alerts</h3>
              <NavLink to="/alerts" className="btn btn-secondary btn-sm">Full Alert Logs</NavLink>
            </div>
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Alert ID</th>
                    <th>Violation Type</th>
                    <th>Severity</th>
                    <th>Peak Recorded</th>
                    <th>Threshold Limit</th>
                    <th>Exposure Duration</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.length === 0 ? (
                    <tr>
                      <td colSpan="7" style={{ textAlign: 'center', padding: '24px', color: '#16a34a' }}>
                        ✓ Environmental conditions have remained within configured safety thresholds.
                      </td>
                    </tr>
                  ) : (
                    alerts.map((a) => (
                      <tr key={a.id}>
                        <td style={{ fontWeight: '600' }}>{a.alert_code}</td>
                        <td>{a.alert_type.replace('_', ' ')}</td>
                        <td>
                          <span className={`badge badge-${a.severity.toLowerCase()}`}>
                            {a.severity}
                          </span>
                        </td>
                        <td>{a.recorded_value.toFixed(1)}</td>
                        <td>{a.threshold_value}</td>
                        <td>{a.exposure_duration_minutes.toFixed(0)} min</td>
                        <td style={{ fontSize: '12px', maxWidth: '300px' }}>{a.description}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

