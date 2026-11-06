import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';

export default function Sidebar({ isOpen, onClose }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    if (onClose) onClose();
    navigate('/login');
  };

  const navItems = [
    { label: 'Dashboard', path: '/', icon: '📊' },
    { label: 'Shipments', path: '/shipments', icon: '📦' },
    { label: 'Create Shipment', path: '/shipments/create', icon: '➕' },
    { label: 'Live Monitoring', path: '/monitoring', icon: '🛰️' },
    { label: 'Exposure Alerts', path: '/alerts', icon: '⚠️' },
    { label: 'ML Risk Analysis', path: '/ml-analysis', icon: '🧠' },
    { label: 'What-If Simulator', path: '/what-if', icon: '🎛️' },
    { label: 'Shipment Comparison', path: '/compare', icon: '⚖️' },
    { label: 'Journey Reports', path: '/reports', icon: '📄' },
    { label: 'Product Profiles', path: '/products', icon: '🏷️' },
    { label: 'Settings', path: '/settings', icon: '⚙️' },
  ];

  return (
    <>
      {/* Mobile Backdrop Sheet */}
      <div
        className={`sidebar-backdrop ${isOpen ? 'active' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <NavLink to="/" className="sidebar-logo" onClick={onClose}>
              <div className="sidebar-logo-icon">AIoT</div>
              <div>
                <div className="sidebar-logo-title">Journey Intelligence</div>
              </div>
            </NavLink>
            <button
              type="button"
              className="sidebar-close-btn"
              onClick={onClose}
              aria-label="Close Navigation"
            >
              ✕
            </button>
          </div>
          <div className="sidebar-tagline">From Origin to Destination — Every Condition Matters.</div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              onClick={onClose}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-badge">
            <div className="user-info">
              <span className="user-name">{user ? user.full_name || user.username : 'Guest Operator'}</span>
              <span className="user-role">{user ? user.role : 'operator'}</span>
            </div>
            {user ? (
              <button
                onClick={handleLogout}
                className="btn btn-secondary btn-sm"
                title="Sign Out"
                style={{ padding: '6px 12px', fontSize: '11.5px' }}
              >
                Logout
              </button>
            ) : (
              <NavLink to="/login" onClick={onClose} className="btn btn-primary btn-sm" style={{ padding: '6px 12px', fontSize: '11.5px' }}>
                Login
              </NavLink>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
