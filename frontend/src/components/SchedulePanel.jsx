/**
 * components/SchedulePanel.jsx — Recruiter dashboard for scheduling interviews.
 *
 * "Schedule Now"  → sends invite email immediately, link valid 30 min
 * "Schedule Later"→ pick date/time, link activates then, valid 30 min
 *
 * Both flows require candidate email. No in-person "start now" mode.
 */
import { useEffect, useRef, useState } from 'react';
import { listBanks, scheduleInterview, uploadQuestionBank } from '../services/api';

export default function SchedulePanel({ recruiter, onLogout }) {
  const [banks, setBanks]           = useState([]);
  const [selectedBank, setSelectedBank] = useState('');
  const [mode, setMode]             = useState('now'); // 'now' | 'later'
  const [form, setForm]             = useState({
    candidate_name: '', candidate_email: '', candidate_role: '',
    scheduled_date: '', scheduled_time: '09:00',
    company_name: recruiter?.company || '',
    notes: '',
  });
  const [uploadName, setUploadName] = useState('');
  const [file, setFile]             = useState(null);
  const [uploading, setUploading]   = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const [result, setResult]         = useState(null);
  const [error, setError]           = useState('');
  const fileRef = useRef();

  useEffect(() => { listBanks().then(setBanks).catch(() => {}); }, []);

  function set(f) { return (e) => setForm(p => ({ ...p, [f]: e.target.value })); }

  async function handleUpload() {
    if (!file || !uploadName.trim()) { setError('Provide a file and bank name.'); return; }
    setError(''); setUploading(true);
    try {
      const bank = await uploadQuestionBank(file, uploadName.trim());
      setBanks(p => [...p, bank]);
      setSelectedBank(bank.id);
      setFile(null); setUploadName('');
      if (fileRef.current) fileRef.current.value = '';
    } catch (e) { setError(`Upload failed: ${e.message}`); }
    finally { setUploading(false); }
  }

  async function handleSchedule() {
    if (!selectedBank)              return setError('Select a question bank.');
    if (!form.candidate_name.trim()) return setError('Candidate name is required.');
    if (!form.candidate_email.trim()) return setError('Candidate email is required.');
    if (mode === 'later' && !form.scheduled_date) return setError('Select interview date.');
    setError(''); setScheduling(true);

    const scheduledAt = mode === 'now'
      ? new Date().toISOString()
      : new Date(`${form.scheduled_date}T${form.scheduled_time}:00`).toISOString();

    try {
      const res = await scheduleInterview({
        bank_id: selectedBank,
        candidate_name: form.candidate_name.trim(),
        candidate_email: form.candidate_email.trim(),
        candidate_role: form.candidate_role.trim() || undefined,
        scheduled_at: scheduledAt,
        send_now: mode === 'now',
        company_name: form.company_name.trim() || undefined,
        interviewer_name: recruiter?.name,
        notes: form.notes.trim() || undefined,
      });
      setResult(res);
    } catch (e) { setError(`Failed: ${e.message}`); }
    finally { setScheduling(false); }
  }

  const bank = banks.find(b => b.id === selectedBank);

  // ── Success screen ──────────────────────────────────────────────────────────

  if (result) {
    const si = result.scheduled_interview;
    return (
      <div style={S.page}>
        <div style={S.gridOverlay} />
        <div style={S.wrap}>
          <Logo />
          <div style={S.card}>
            <div style={{ padding: '40px 40px 36px' }}>
              <div style={{ textAlign: 'center', marginBottom: 28 }}>
                <div style={{ fontSize: 48, marginBottom: 8 }}>✅</div>
                <div style={S.cardTitle}>Interview Scheduled</div>
                <p style={S.cardSub}>
                  {result.email_sent
                    ? `Invite sent to ${si.candidate_email}`
                    : '⚠ Email not sent — SMTP not configured. Share the link manually.'}
                </p>
              </div>

              <div style={S.linkCard}>
                <div style={S.fieldLabel}>CANDIDATE INTERVIEW LINK</div>
                <div style={{ fontSize: 12, color: '#4A8FE8', wordBreak: 'break-all', marginBottom: 10, fontFamily: 'var(--font-mono)' }}>{result.interview_link}</div>
                <button style={S.copyBtn} onClick={() => navigator.clipboard.writeText(result.interview_link)}>
                  📋 Copy Link
                </button>
              </div>

              <div style={S.summaryGrid}>
                <SummaryRow label="Candidate"  value={si.candidate_name} />
                <SummaryRow label="Email"      value={si.candidate_email} />
                {si.candidate_role && <SummaryRow label="Role" value={si.candidate_role} />}
                <SummaryRow label="Scheduled"  value={si.send_now ? 'Immediately' : new Date(si.scheduled_at).toLocaleString()} />
                <SummaryRow label="Link Expires" value={si.expires_at ? new Date(si.expires_at).toLocaleString() : '30 min after start'} />
                {si.company_name && <SummaryRow label="Company" value={si.company_name} />}
              </div>

              {!result.email_sent && (
                <div style={S.smtpNote}>
                  Set SMTP_USERNAME and SMTP_PASSWORD in your .env to enable automatic email delivery.
                </div>
              )}

              <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
                <button style={{ ...S.btnOutline, flex: 1 }} onClick={() => { setResult(null); setForm({ candidate_name: '', candidate_email: '', candidate_role: '', scheduled_date: '', scheduled_time: '09:00', company_name: recruiter?.company || '', notes: '' }); }}>
                  + Schedule Another
                </button>
                <button style={{ ...S.btnGold, flex: 1 }} onClick={() => setResult(null)}>
                  ← Dashboard
                </button>
              </div>
            </div>
          </div>
          <RecruiterBar recruiter={recruiter} onLogout={onLogout} />
        </div>
      </div>
    );
  }

  // ── Main form ───────────────────────────────────────────────────────────────

  return (
    <div style={S.page}>
      <div style={S.gridOverlay} />
      <div style={S.wrapWide}>
        <Logo />

        <div style={S.twoColLayout}>
          {/* ── LEFT: Bank management ── */}
          <div style={S.card}>
            <div style={{ padding: '28px 28px 24px' }}>
              <div style={S.sectionTag}>Question Banks</div>

              <div style={{ marginBottom: 20 }}>
                <div style={S.fieldLabel}>UPLOAD NEW BANK</div>
                <Input placeholder="Bank name (e.g. React Engineer – Q1)" value={uploadName} onChange={e => setUploadName(e.target.value)} />
                <input ref={fileRef} type="file" accept=".csv,.json" style={{ display: 'block', marginTop: 8, fontSize: 12, color: 'var(--silver)' }} onChange={e => setFile(e.target.files[0] || null)} />
                <button style={{ ...S.btnOutline, marginTop: 10, fontSize: 13 }} onClick={handleUpload} disabled={uploading}>
                  {uploading ? 'Uploading…' : '↑ Upload CSV / JSON'}
                </button>
              </div>

              {banks.length > 0 && (
                <div>
                  <div style={S.fieldLabel}>SELECT BANK</div>
                  {banks.map(b => (
                    <div key={b.id} onClick={() => setSelectedBank(b.id)}
                      style={{
                        ...S.bankRow,
                        borderColor: selectedBank === b.id ? 'rgba(201,168,76,0.4)' : 'var(--border)',
                        background: selectedBank === b.id ? 'var(--gold-glow)' : 'transparent',
                      }}>
                      <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--platinum)' }}>{b.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--silver)', marginTop: 2 }}>
                        {b.questions.length} questions{b.role ? ` · ${b.role}` : ''}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ── RIGHT: Schedule form ── */}
          <div style={S.card}>
            <div style={{ padding: '28px 28px 24px' }}>
              <div style={S.sectionTag}>New Interview</div>

              {/* Mode toggle */}
              <div style={S.modeToggle}>
                <button style={{ ...S.modeBtn, ...(mode === 'now' ? S.modeBtnActive : {}) }} onClick={() => setMode('now')}>
                  ⚡ Schedule Now
                </button>
                <button style={{ ...S.modeBtn, ...(mode === 'later' ? S.modeBtnActive : {}) }} onClick={() => setMode('later')}>
                  📅 Schedule Later
                </button>
              </div>

              {mode === 'now' && (
                <div style={S.infoNote}>
                  Interview link sent immediately. Candidate has <strong>30 minutes</strong> to start.
                </div>
              )}

              <div style={S.fieldLabel}>CANDIDATE NAME *</div>
              <Input placeholder="Jane Smith" value={form.candidate_name} onChange={set('candidate_name')} />

              <div style={S.fieldLabel}>CANDIDATE EMAIL *</div>
              <Input type="email" placeholder="jane@email.com" value={form.candidate_email} onChange={set('candidate_email')} />

              <div style={S.fieldLabel}>ROLE / POSITION</div>
              <Input placeholder="Senior Frontend Engineer" value={form.candidate_role} onChange={set('candidate_role')} />

              {mode === 'later' && (
                <>
                  <div style={S.fieldLabel}>INTERVIEW DATE & TIME *</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    <Input type="date" value={form.scheduled_date} onChange={set('scheduled_date')} min={new Date().toISOString().split('T')[0]} />
                    <Input type="time" value={form.scheduled_time} onChange={set('scheduled_time')} />
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6 }}>
                    Link activates at this time. Expires 30 min after.
                  </div>
                </>
              )}

              <div style={S.fieldLabel}>COMPANY (OPTIONAL)</div>
              <Input placeholder="Acme Corp" value={form.company_name} onChange={set('company_name')} />

              <div style={S.fieldLabel}>NOTES FOR CANDIDATE</div>
              <textarea style={{ ...S.inputBase, minHeight: 72, resize: 'vertical', lineHeight: 1.5 }}
                placeholder="Preparation tips or context…"
                value={form.notes} onChange={set('notes')} />

              {error && <div style={S.error}>{error}</div>}

              {bank && (
                <div style={{ fontSize: 12, color: 'var(--gold)', marginBottom: 12 }}>
                  📋 {bank.name} · {bank.questions.length} questions
                </div>
              )}

              <button style={{ ...S.btnGold, width: '100%', fontSize: 14 }} onClick={handleSchedule} disabled={scheduling}>
                {scheduling ? 'Sending invite…' : mode === 'now' ? '📧 Send Interview Now' : '📅 Schedule & Send Invite'}
              </button>
            </div>
          </div>
        </div>

        <RecruiterBar recruiter={recruiter} onLogout={onLogout} />
      </div>
    </div>
  );
}

// ── Small helpers ─────────────────────────────────────────────────────────────

function Logo() {
  return (
    <div style={{ textAlign: 'center', marginBottom: 32 }}>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, letterSpacing: '5px', color: 'var(--gold)' }}>PRE-INTERVIEW AI</div>
      <div style={{ width: 36, height: 1, background: 'linear-gradient(90deg,transparent,var(--gold),transparent)', margin: '10px auto 0' }} />
    </div>
  );
}

function Input({ type = 'text', placeholder, value, onChange, min }) {
  const [focused, setFocused] = useState(false);
  return (
    <input type={type} placeholder={placeholder} value={value} onChange={onChange} min={min}
      onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
      style={{ ...S.inputBase, borderColor: focused ? 'rgba(201,168,76,0.4)' : 'rgba(255,255,255,0.06)', boxShadow: focused ? '0 0 0 3px rgba(201,168,76,0.07)' : 'none', marginBottom: 12 }} />
  );
}

function SummaryRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
      <span style={{ color: 'var(--silver)' }}>{label}</span>
      <span style={{ color: 'var(--platinum)', fontWeight: 500, textAlign: 'right', maxWidth: '55%' }}>{value}</span>
    </div>
  );
}

function RecruiterBar({ recruiter, onLogout }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 20, padding: '10px 0', borderTop: '1px solid var(--border)' }}>
      <span style={{ fontSize: 12, color: 'var(--muted)' }}>{recruiter?.name} · {recruiter?.email}</span>
      <button style={{ background: 'none', border: '1px solid var(--border)', color: 'var(--silver)', fontSize: 12, padding: '5px 12px', borderRadius: 6, cursor: 'pointer' }} onClick={onLogout}>Sign Out</button>
    </div>
  );
}

const S = {
  page: { minHeight: '100vh', background: 'var(--bg-void)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px', position: 'relative' },
  gridOverlay: { position: 'fixed', inset: 0, zIndex: 0, backgroundImage: 'linear-gradient(rgba(201,168,76,0.025) 1px, transparent 1px),linear-gradient(90deg, rgba(201,168,76,0.025) 1px, transparent 1px)', backgroundSize: '60px 60px', pointerEvents: 'none' },
  wrap: { width: '100%', maxWidth: 480, position: 'relative', zIndex: 1 },
  wrapWide: { width: '100%', maxWidth: 900, position: 'relative', zIndex: 1 },
  card: { background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 14, boxShadow: '0 24px 60px rgba(0,0,0,0.4)', marginBottom: 16 },
  twoColLayout: { display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 16, marginBottom: 0 },
  cardTitle: { fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 600, color: 'var(--platinum)', marginBottom: 6 },
  cardSub: { fontSize: 13, color: 'var(--silver)', lineHeight: 1.6 },
  sectionTag: { fontSize: 10, letterSpacing: '3px', color: 'var(--gold)', textTransform: 'uppercase', marginBottom: 18, fontWeight: 500 },
  fieldLabel: { fontSize: 10, letterSpacing: '2px', color: 'var(--silver)', textTransform: 'uppercase', marginBottom: 7, marginTop: 14, fontWeight: 500 },
  inputBase: { display: 'block', width: '100%', boxSizing: 'border-box', background: 'var(--bg-deep)', border: '1px solid', borderRadius: 8, padding: '10px 13px', color: 'var(--platinum)', fontSize: 13, outline: 'none', transition: 'all 0.2s', fontFamily: 'var(--font-body)' },
  bankRow: { border: '1px solid', borderRadius: 8, padding: '10px 14px', marginBottom: 8, cursor: 'pointer', transition: 'all 0.15s' },
  modeToggle: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16, marginTop: 4 },
  modeBtn: { padding: '10px 0', borderRadius: 8, border: '1px solid var(--border)', background: 'transparent', color: 'var(--silver)', fontSize: 13, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s' },
  modeBtnActive: { borderColor: 'rgba(201,168,76,0.4)', background: 'var(--gold-glow)', color: 'var(--gold)' },
  infoNote: { fontSize: 12, color: 'var(--muted)', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: 7, padding: '8px 12px', marginBottom: 4 },
  btnGold: { background: 'linear-gradient(135deg,var(--gold-dim),var(--gold),var(--gold-bright))', backgroundSize: '200% auto', border: 'none', borderRadius: 8, color: '#0a0c12', fontWeight: 600, cursor: 'pointer', padding: '12px 20px', fontSize: 13, transition: 'all 0.2s', fontFamily: 'var(--font-body)' },
  btnOutline: { background: 'transparent', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--silver)', cursor: 'pointer', padding: '10px 18px', fontSize: 13, transition: 'border-color 0.2s', fontFamily: 'var(--font-body)' },
  copyBtn: { background: 'var(--bg-raised)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--silver)', padding: '6px 14px', cursor: 'pointer', fontSize: 12 },
  linkCard: { background: 'var(--bg-deep)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 16 },
  summaryGrid: { marginBottom: 4 },
  smtpNote: { fontSize: 11, color: 'var(--gold)', background: 'var(--gold-glow)', border: '1px solid var(--border-gold)', borderRadius: 8, padding: '10px 14px', marginTop: 12 },
  error: { fontSize: 13, color: '#E74C3C', background: 'rgba(231,76,60,0.08)', border: '1px solid rgba(231,76,60,0.2)', borderRadius: 8, padding: '10px 14px', marginBottom: 14 },
};
