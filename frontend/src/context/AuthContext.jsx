import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, getSavedUser, setAuthToken, setSavedUser } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getSavedUser());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Validate current session with server
    api.getMe()
      .then((res) => {
        setUser(res.user);
        setSavedUser(res.user);
      })
      .catch(() => {
        setUser(null);
        setSavedUser(null);
        setAuthToken(null);
      })
      .finally(() => setLoading(false));

    const handleUnauthorized = () => {
      setUser(null);
      setSavedUser(null);
    };

    window.addEventListener('aiot:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('aiot:unauthorized', handleUnauthorized);
  }, []);

  const login = async (username, password) => {
    const res = await api.login({ username, password });
    setAuthToken(res.token);
    setUser(res.user);
    setSavedUser(res.user);
    return res.user;
  };

  const register = async (userData) => {
    const res = await api.register(userData);
    setAuthToken(res.token);
    setUser(res.user);
    setSavedUser(res.user);
    return res.user;
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch (e) {
      // Ignore logout errors
    } finally {
      setAuthToken(null);
      setUser(null);
      setSavedUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, isAdmin: user?.role === 'admin' }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

