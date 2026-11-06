import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('Admin@1234');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('operator');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        await register({ username, password, email, full_name: fullName, role });
      } else {
        await login(username, password);
      }
      navigate('/');
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const setDemoCredentials = (u, p) => {
    setUsername(u);
    setPassword(p);
    setIsRegister(false);
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f1f5f9', padding: '20px' }}>
      <div className="card" style={{ maxWidth: '440px', width: '100%', padding: '36px 32px' }}>
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{ display: 'inline-flex', width: '48px', height: '48px', backgroundColor: '#0d9488', borderRadius: '12px', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '20px', marginBottom: '12px' }}>
            AIoT
          </div>
          <h2 style={{ fontSize: '22px', fontWeight: '700', color: '#0f172a' }}>Journey Condition Intelligence</h2>
          <p style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>
            {isRegister ? 'Register your individual platform account' : 'Sign in to access transportation condition telemetry'}
          </p>
        </div>

        {error && (
          <div className="alert-box" style={{ backgroundColor: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', marginBottom: '16px' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              type="text"
              className="form-control"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          {isRegister && (
            <>
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  type="text"
                  className="form-control"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. John Doe"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                  type="email"
                  className="form-control"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Role</label>
                <select className="form-control" value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="operator">Operator (Monitoring & Journeys)</option>
                  <option value="admin">Administrator (Full Access)</option>
                </select>
              </div>
            </>
          )}

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              type="password"
              className="form-control"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn btn-primary" style={{ marginTop: '8px', padding: '10px' }} disabled={loading}>
            {loading ? 'Authenticating...' : isRegister ? 'Create Account' : 'Sign In to Dashboard'}
          </button>
        </form>

        <div style={{ marginTop: '20px', textAlign: 'center', fontSize: '13px', color: '#64748b' }}>
          {isRegister ? (
            <span>
              Already have an account?{' '}
              <button
                type="button"
                onClick={() => setIsRegister(false)}
                style={{ background: 'none', border: 'none', color: '#0d9488', fontWeight: '600', cursor: 'pointer' }}
              >
                Sign In
              </button>
            </span>
          ) : (
            <span>
              Need a new account?{' '}
              <button
                type="button"
                onClick={() => setIsRegister(true)}
                style={{ background: 'none', border: 'none', color: '#0d9488', fontWeight: '600', cursor: 'pointer' }}
              >
                Register
              </button>
            </span>
          )}
        </div>

        {!isRegister && (
          <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid #e2e8f0', fontSize: '12px', color: '#64748b' }}>
            <div style={{ fontWeight: '600', marginBottom: '6px', color: '#334155' }}>Quick Demo Logins:</div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setDemoCredentials('admin', 'Admin@1234')}
              >
                Admin (Admin@1234)
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setDemoCredentials('operator', 'Operator@1234')}
              >
                Operator (Operator@1234)
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

