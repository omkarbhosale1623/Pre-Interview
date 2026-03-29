/**
 * components/Auth.jsx — Recruiter sign-up / sign-in.
 * Premium dark UI matching Pre-Interview AI brand.
 */
import { useState } from 'react';
import { recruiterSignin, recruiterSignup } from '../services/api';

export default function Auth({ onAuth }) {
  const [mode, setMode] = useState('signin'); // signin | signup
  const [form, setForm] = useState({ email: '', password: '', full_name: '', company_name: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (f) => (e) => setForm(p => ({ ...p, [f]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const res = mode === 'signin'
        ? await recruiterSignin(form.email, form.password)
        : await recruiterSignup(form.email, form.password, form.full_name, form.company_name);
      localStorage.setItem('pia_token', res.token);
      localStorage.setItem('pia_recruiter', JSON.stringify(res.recruiter));
      onAuth(res.token, res.recruiter);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={S.page}>
      {/* Background grid */}
      <div style={S.grid} />

      <div className="animate-slide-up" style={S.wrapper}>
        {/* Logo */}
        <div style={S.logoArea}>
          <div style={S.logoIcon}>🎙</div>
          <h1 className="gold-text" style={S.logo}>Pre-Interview AI</h1>
          <p style={S.tagline}>AI-powered voice interviews for modern recruiters</p>
        </div>

        {/* Card */}
        <div className="card-glow" style={S.card}>
          {/* Tabs */}
          <div style={S.tabs}>
            {['signin', 'signup'].map(m => (
              <button key={m} onClick={() => { setMode(m); setError(''); }}
                style={{ ...S.tab, ...(mode === m ? S.tabActive : {}) }}>
                {m === 'signin' ? 'Sign In' : 'Create Account'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} style={S.form}>
            {mode === 'signup' && (
              <>
                <Field label="Full Name" value={form.full_name} onChange={set('full_name')} placeholder="Alex Johnson" required />
                <Field label="Company Name" value={form.company_name} onChange={set('company_name')} placeholder="Acme Corp (optional)" />
              </>
            )}
            <Field label="Work Email" type="email" value={form.email} onChange={set('email')} placeholder="you@company.com" required />
            <Field label="Password" type="password" value={form.password} onChange={set('password')}
              placeholder={mode === 'signup' ? 'Min 6 characters' : '••••••••'} required />

            {error && <div style={S.error}>{error}</div>}

            <button type="submit" className="btn-gold" style={S.submit} disabled={loading}>
              {loading ? <span className="spin" style={{ display: 'inline-block', marginRight: 8 }}>⏳</span> : null}
              {loading ? 'Please wait…' : mode === 'signin' ? 'Sign In →' : 'Create Account →'}
            </button>
          </form>

          <p style={S.switchText}>
            {mode === 'signin' ? "Don't have an account? " : "Already have an account? "}
            <button onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setError(''); }} style={S.switchBtn}>
              {mode === 'signin' ? 'Create one' : 'Sign in'}
            </button>
          </p>
        </div>

        <p style={S.footer}>
          Recruiter access only · Candidates join via email link
        </p>
      </div>
    </div>
  );
}

function Field({ label, type = 'text', value, onChange, placeholder, required }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label className="label" style={{ display: 'block', marginBottom: 8 }}>{label}</label>
      <input className="input-dark" type={type} value={value} onChange={onChange}
        placeholder={placeholder} required={required} />
    </div>
  );
}

const S = {
  page: {
    minHeight: '100vh', background: 'var(--bg)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    padding: 24, fontFamily: "'Segoe UI', system-ui, sans-serif",
    position: 'relative', overflow: 'hidden',
  },
  grid: {
    position: 'absolute', inset: 0, opacity: 0.03,
    backgroundImage: 'linear-gradient(var(--gold) 1px, transparent 1px), linear-gradient(90deg, var(--gold) 1px, transparent 1px)',
    backgroundSize: '60px 60px',
    pointerEvents: 'none',
  },
  wrapper: { width: '100%', maxWidth: 440, position: 'relative', zIndex: 1 },
  logoArea: { textAlign: 'center', marginBottom: 36 },
  logoIcon: { fontSize: 48, marginBottom: 12 },
  logo: { fontSize: 32, fontWeight: 900, letterSpacing: -1, margin: '0 0 8px' },
  tagline: { fontSize: 14, color: 'var(--text-muted)', lineHeight: 1.5 },
  card: { padding: 36 },
  tabs: { display: 'flex', background: 'var(--bg)', borderRadius: 10, padding: 4, marginBottom: 28 },
  tab: {
    flex: 1, padding: '10px', border: 'none', background: 'transparent',
    color: 'var(--text-muted)', cursor: 'pointer', borderRadius: 8,
    fontSize: 14, fontWeight: 600, transition: 'all 0.2s',
  },
  tabActive: {
    background: 'var(--surface2)', color: 'var(--gold)',
    boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
  },
  form: { display: 'flex', flexDirection: 'column' },
  error: {
    background: 'var(--red-glow)', border: '1px solid rgba(255,69,96,0.3)',
    borderRadius: 10, padding: '12px 16px',
    fontSize: 13, color: 'var(--red)', marginBottom: 16,
  },
  submit: { padding: '14px', fontSize: 15, marginTop: 8, width: '100%' },
  switchText: { textAlign: 'center', marginTop: 20, fontSize: 13, color: 'var(--text-muted)' },
  switchBtn: {
    background: 'none', border: 'none', color: 'var(--gold)',
    cursor: 'pointer', fontSize: 13, fontWeight: 600,
  },
  footer: { textAlign: 'center', marginTop: 24, fontSize: 12, color: 'var(--text-dim)' },
};
