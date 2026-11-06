import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function Layout() {
  const location = useLocation();

  const getPageTitle = (path) => {
    if (path === '/') return 'Executive Intelligence Dashboard';
    if (path.startsWith('/shipments/create')) return 'Create New Shipment Journey';
    if (path.startsWith('/shipments')) return 'Shipment Fleet Management';
    if (path.startsWith('/monitoring')) return 'Real-Time IoT Virtual Telemetry & Simulator';
    if (path.startsWith('/alerts')) return 'Harmful Exposure Incidents & Alerts';
    if (path.startsWith('/ml-analysis')) return 'Machine Learning Product Quality Risk Engine';
    if (path.startsWith('/what-if')) return 'What-If Environmental Journey Simulator';
    if (path.startsWith('/compare')) return 'Multi-Shipment Risk Comparison & Analysis';
    if (path.startsWith('/reports')) return 'Downloadable Journey Condition Reports';
    if (path.startsWith('/products')) return 'Product Category Profiles & Thresholds';
    if (path.startsWith('/settings')) return 'Platform System Settings';
    return 'Journey Condition Intelligence';
  };

  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-wrapper">
        <header className="top-navbar">
          <h1 className="page-title">{getPageTitle(location.pathname)}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="badge badge-transit" style={{ background: '#f0fdfa', color: '#0d9488', border: '1px solid #ccfbf1' }}>
              System: Online (Simulated IoT Active)
            </span>
          </div>
        </header>
        <main className="content-body">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

