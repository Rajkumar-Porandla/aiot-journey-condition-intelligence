import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navItems = [
    { label: 'Dashboard', path: '/' },
    { label: 'Shipments', path: '/shipments' },
    { label: 'Create Shipment', path: '/shipments/create' },
    { label: 'Live Monitoring', path: '/monitoring' },
    { label: 'Exposure Alerts', path: '/alerts' },
    { label: 'ML Risk Analysis', path: '/ml-analysis' },
    { label: 'What-If Simulator', path: '/what-if' },
    { label: 'Shipment Comparison', path: '/compare' },
    { label: 'Journey Reports', path: '/reports' },
    { label: 'Product Profiles', path: '/products' },
    { label: 'Settings', path: '/settings' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <NavLink to="/" className="sidebar-logo">
          <div className="sidebar-logo-icon">AIoT</div>
          <div>
            <div className="sidebar-logo-title">Journey Intelligence</div>
          </div>
        </NavLink>
        <div className="sidebar-tagline">Every Condition Matters.</div>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
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
              style={{ padding: '4px 8px', fontSize: '11px' }}
            >
              Logout
            </button>
          ) : (
            <NavLink to="/login" className="btn btn-primary btn-sm" style={{ padding: '4px 8px', fontSize: '11px' }}>
              Login
            </NavLink>
          )}
        </div>
      </div>
    </aside>
  );
}

