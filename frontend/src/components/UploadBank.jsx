/**
 * components/UploadBank.jsx — Upload question bank + Schedule Now / Schedule Later.
 * "Schedule Now" = sends link to candidate immediately.
 * "Schedule Later" = pick date/time (30-min window after that time).
 */
import { useEffect, useRef, useState } from 'react';
import { listBanks, uploadQuestionBank } from '../services/api';

export default function UploadBank({ recruiter, onScheduleNow, onScheduleLater, onSignOut }) {
  const [banks, setBanks] = useState([]);
  const [selectedBankId, setSelectedBankId] = useState('');
  const [candidateName, setCandidateName] = useState('');
  const [candidateEmail, setCandidateEmail] = useState('');
  const [candidateRole, setCandidateRole] = useState('');
  const [bankName, setBankName] = useState('');
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef();

  useEffect(() => { listBanks().then(setBanks).catch(() => {}); }, []);

  async function handleUpload() {
    if (!file || !bankName.trim()) { setError('Provide a file and bank name.'); return; }
    setError(''); setUploading(true);
    try {
      const bank = await uploadQuestionBank(file, bankName.trim(), candidateRole.trim() || undefined);
      setBanks(p => [...p, bank]);
      setSelectedBankId(bank.id);
      setFile(null); setBankName('');
      if (fileRef.current) fileRef.current.value = '';
    } catch (e) { setError(e.message); }
    finally { setUploading(false); }
  }

  function validate() {
    if (!selectedBankId) { setError('Select a question bank.'); return false; }
    if (!candidateName.trim()) { setError('Enter candidate full name.'); return false; }
    if (!candidateEmail.trim() || !candidateEmail.includes('@')) { setError('Enter a valid candidate email.'); return false; }
    setError('');
    return { bankId: selectedBankId, candidateName: candidateName.trim(), candidateEmail: candidateEmail.trim(), candidateRole: candidateRole.trim() || undefined };
  }

  const selectedBank = banks.find(b => b.id === selectedBankId);

  return (
    <div style={S.page}>
      <div style={S.grid} />

      <div className="animate-fade-in" style={S.outer}>
        {/* Header */}
        <div style={S.header}>
          <div>
            <span className="gold-text" style={S.brand}>Pre-Interview AI</span>
            <span style={S.badge}>Recruiter Portal</span>
          </div>
          <div style={S.recruiterInfo}>
            <span style={S.recruiterName}>{recruiter?.full_name}</span>
            <button className="btn-ghost" style={S.signOutBtn} onClick={onSignOut}>Sign out</button>
          </div>
        </div>

        <div style={S.columns}>
          {/* Left: Upload */}
          <div className="card" style={S.leftCard}>
            <div className="label" style={{ marginBottom: 20 }}>Question Bank</div>

            {/* Upload new */}
            <div style={S.uploadSection}>
              <div className="label" style={{ fontSize: 10, marginBottom: 12, color: 'var(--text-dim)' }}>Upload New Bank</div>
              <input className="input-dark" placeholder="Bank name (e.g. Frontend Eng — Q3)" value={bankName}
                onChange={e => setBankName(e.target.value)} style={{ marginBottom: 10 }} />
              <input ref={fileRef} type="file" accept=".csv,.json,.txt,.docx" onChange={e => setFile(e.target.files[0] || null)}
                style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }} />
              <p style={S.hint}>CSV (question, topic, difficulty, keywords) or JSON array</p>
              <button className="btn-ghost" onClick={handleUpload} disabled={uploading} style={S.uploadBtn}>
                {uploading ? '⏳ Uploading…' : '↑ Upload Bank'}
              </button>
            </div>

            {/* Existing banks */}
            {banks.length > 0 && (
              <div style={{ marginTop: 24 }}>
                <div className="label" style={{ fontSize: 10, marginBottom: 12, color: 'var(--text-dim)' }}>Select Bank</div>
                {banks.map(b => (
                  <div key={b.id} onClick={() => setSelectedBankId(b.id)}
                    style={{ ...S.bankRow, ...(selectedBankId === b.id ? S.bankRowActive : {}) }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: selectedBankId === b.id ? 'var(--gold)' : 'var(--text)' }}>{b.name}</div>
                      {b.role && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{b.role}</div>}
                    </div>
                    <div style={S.bankCount}>{b.questions.length}q</div>
                  </div>
                ))}
              </div>
            )}

            {selectedBank && (
              <div style={S.bankPreview}>
                ✓ {selectedBank.questions.length} questions selected
                {selectedBank.role ? ` · ${selectedBank.role}` : ''}
              </div>
            )}
          </div>

          {/* Right: Candidate + Actions */}
          <div style={S.rightCol}>
            <div className="card" style={S.rightCard}>
              <div className="label" style={{ marginBottom: 20 }}>Candidate Details</div>

              <Field label="Full Name *" value={candidateName} onChange={e => setCandidateName(e.target.value)} placeholder="Jane Smith" />
              <Field label="Email Address *" type="email" value={candidateEmail} onChange={e => setCandidateEmail(e.target.value)} placeholder="jane@company.com" />
              <Field label="Role / Position" value={candidateRole} onChange={e => setCandidateRole(e.target.value)} placeholder="Senior Frontend Engineer" />
            </div>

            {error && <div style={S.error}>{error}</div>}

            {/* Actions */}
            <div style={S.actions}>
              {/* Schedule Now — primary action */}
              <div style={S.actionCard}>
                <div style={S.actionIcon}>⚡</div>
                <div style={{ flex: 1 }}>
                  <div style={S.actionTitle}>Schedule Now</div>
                  <div style={S.actionDesc}>Send interview link immediately via email</div>
                </div>
                <button className="btn-gold" style={S.actionBtn}
                  onClick={() => { const v = validate(); if (v) onScheduleNow(v); }}>
                  Send Link →
                </button>
              </div>

              {/* Schedule Later */}
              <div style={S.actionCard}>
                <div style={S.actionIcon}>📅</div>
                <div style={{ flex: 1 }}>
                  <div style={S.actionTitle}>Schedule Later</div>
                  <div style={S.actionDesc}>Set a future date & time — link activates then (30-min window)</div>
                </div>
                <button className="btn-ghost" style={S.actionBtn}
                  onClick={() => { const v = validate(); if (v) onScheduleLater(v); }}>
                  Pick Time →
                </button>
              </div>
            </div>

            <p style={S.footer}>
              The candidate receives a secure, single-use interview link via email.
              After completion, a detailed report is sent to your inbox.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, type = 'text', value, onChange, placeholder }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label className="label" style={{ display: 'block', marginBottom: 8, fontSize: 10, color: 'var(--text-dim)' }}>{label}</label>
      <input className="input-dark" type={type} value={value} onChange={onChange} placeholder={placeholder} />
    </div>
  );
}

const S = {
  page: { minHeight: '100vh', background: 'var(--bg)', padding: '32px 24px', fontFamily: "'Segoe UI', system-ui, sans-serif", position: 'relative' },
  grid: { position: 'fixed', inset: 0, opacity: 0.025, backgroundImage: 'linear-gradient(var(--gold) 1px, transparent 1px), linear-gradient(90deg, var(--gold) 1px, transparent 1px)', backgroundSize: '60px 60px', pointerEvents: 'none' },
  outer: { maxWidth: 1100, margin: '0 auto', position: 'relative', zIndex: 1 },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 36, padding: '0 4px' },
  brand: { fontSize: 22, fontWeight: 900, letterSpacing: -0.5, marginRight: 12 },
  badge: { fontSize: 11, background: 'var(--gold-glow)', border: '1px solid var(--border)', color: 'var(--gold)', padding: '3px 10px', borderRadius: 20, fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase' },
  recruiterInfo: { display: 'flex', alignItems: 'center', gap: 12 },
  recruiterName: { fontSize: 13, color: 'var(--text-muted)', fontWeight: 600 },
  signOutBtn: { padding: '6px 14px', fontSize: 12 },
  columns: { display: 'grid', gridTemplateColumns: '340px 1fr', gap: 24 },
  leftCard: { padding: 28, height: 'fit-content' },
  uploadSection: { paddingBottom: 20, borderBottom: '1px solid var(--border)' },
  hint: { fontSize: 11, color: 'var(--text-dim)', marginBottom: 10 },
  uploadBtn: { padding: '9px 18px', fontSize: 13, width: '100%' },
  bankRow: { display: 'flex', alignItems: 'center', padding: '12px 14px', borderRadius: 10, cursor: 'pointer', border: '1px solid transparent', marginBottom: 8, transition: 'all 0.2s' },
  bankRowActive: { border: '1px solid var(--border-med)', background: 'var(--gold-glow2)' },
  bankCount: { fontSize: 11, color: 'var(--gold)', background: 'var(--gold-glow)', padding: '2px 8px', borderRadius: 10, fontWeight: 700 },
  bankPreview: { marginTop: 16, fontSize: 12, color: 'var(--green)', background: 'var(--green-glow)', padding: '8px 14px', borderRadius: 8 },
  rightCol: { display: 'flex', flexDirection: 'column', gap: 20 },
  rightCard: { padding: 28 },
  error: { background: 'var(--red-glow)', border: '1px solid rgba(255,69,96,0.3)', borderRadius: 10, padding: '12px 16px', fontSize: 13, color: 'var(--red)' },
  actions: { display: 'flex', flexDirection: 'column', gap: 14 },
  actionCard: { display: 'flex', alignItems: 'center', gap: 16, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 16, padding: '20px 24px', transition: 'border-color 0.2s' },
  actionIcon: { fontSize: 28, flexShrink: 0 },
  actionTitle: { fontSize: 15, fontWeight: 800, color: 'var(--text)', marginBottom: 3 },
  actionDesc: { fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.4 },
  actionBtn: { padding: '10px 20px', fontSize: 13, flexShrink: 0 },
  footer: { fontSize: 12, color: 'var(--text-dim)', textAlign: 'center', lineHeight: 1.6, padding: '0 20px' },
};
