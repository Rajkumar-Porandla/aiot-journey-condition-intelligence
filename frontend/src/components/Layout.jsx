import React, { useState } from 'react';
import { Outlet, useLocation, NavLink } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function Layout() {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const getPageTitle = (path) => {
    if (path === '/') return 'Dashboard';
    if (path.startsWith('/shipments/create')) return 'Create Shipment';
    if (path.startsWith('/shipments')) return 'Shipments';
    if (path.startsWith('/monitoring')) return 'Live Telemetry';
    if (path.startsWith('/alerts')) return 'Exposure Alerts';
    if (path.startsWith('/ml-analysis')) return 'ML Risk Engine';
    if (path.startsWith('/what-if')) return 'What-If Simulator';
    if (path.startsWith('/compare')) return 'Shipment Comparison';
    if (path.startsWith('/reports')) return 'Journey Reports';
    if (path.startsWith('/products')) return 'Product Profiles';
    if (path.startsWith('/settings')) return 'Settings';
    return 'Journey Intelligence';
  };

  const navTabs = [
    { label: 'Overview', path: '/', icon: '📊' },
    { label: 'Shipments', path: '/shipments', icon: '📦' },
    { label: 'Monitor', path: '/monitoring', icon: '🛰️' },
    { label: 'Alerts', path: '/alerts', icon: '⚠️' },
    { label: 'ML Risk', path: '/ml-analysis', icon: '🧠' },
    { label: 'What-If', path: '/what-if', icon: '🎛️' },
  ];

  return (
    <div className="app-container">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="main-wrapper">
        <header className="top-navbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              type="button"
              className="mobile-menu-trigger"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open Navigation Menu"
            >
              <span className="hamburger-bar"></span>
              <span className="hamburger-bar"></span>
              <span className="hamburger-bar"></span>
            </button>
            <h1 className="page-title">{getPageTitle(location.pathname)}</h1>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="badge badge-transit badge-system-status">
              <span className="status-dot"></span>
              <span className="status-text">Simulated IoT Online</span>
            </span>
          </div>
        </header>

        <main className="content-body">
          <Outlet />
        </main>

        {/* Apple iOS-Style Bottom Navigation Bar for quick mobile access */}
        <nav className="mobile-tabbar" aria-label="Mobile Quick Navigation">
          {navTabs.map((tab) => (
            <NavLink
              key={tab.path}
              to={tab.path}
              end={tab.path === '/'}
              className={({ isActive }) => `tabbar-item ${isActive ? 'active' : ''}`}
            >
              <span className="tabbar-icon">{tab.icon}</span>
              <span className="tabbar-label">{tab.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
