import React, { useState } from 'react';
import { FiGrid, FiLogIn, FiUserPlus } from 'react-icons/fi';
import { authAPI } from '../services/api';
import '../styles/AuthScreen.css';

const AuthScreen = ({ onAuthenticated }) => {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [capacity, setCapacity] = useState(40);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const response = mode === 'login'
        ? await authAPI.login({ email, password })
        : await authAPI.register({ email, password, fridge_capacity: Number(capacity) });
      localStorage.setItem('frise_token', response.data.access_token);
      onAuthenticated(response.data.user);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not authenticate. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-screen">
      <section className="auth-panel">
        <div className="auth-brand"><FiGrid size={22} /><span>Frise</span></div>
        <h1>{mode === 'login' ? 'Welcome back' : 'Set up your fridge'}</h1>
        <p className="auth-subtitle">
          {mode === 'login' ? 'Sign in to access your personal food shelf.' : 'Create your private inventory and choose its capacity.'}
        </p>
        <form onSubmit={handleSubmit} className="auth-form">
          <label>Email<input type="email" value={email} onChange={event => setEmail(event.target.value)} required autoComplete="email" /></label>
          <label>Password<input type="password" value={password} onChange={event => setPassword(event.target.value)} required minLength={8} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>
          {mode === 'register' && (
            <label>Fridge capacity (space units)<input type="number" min="1" max="1000" value={capacity} onChange={event => setCapacity(event.target.value)} required /></label>
          )}
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" className="auth-submit" disabled={busy}>
            {mode === 'login' ? <FiLogIn size={18} /> : <FiUserPlus size={18} />}
            {busy ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        <button type="button" className="auth-switch" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>
          {mode === 'login' ? 'New here? Create an account' : 'Already have an account? Sign in'}
        </button>
      </section>
    </main>
  );
};

export default AuthScreen;
