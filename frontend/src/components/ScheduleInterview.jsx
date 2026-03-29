/**
 * components/ScheduleInterview.jsx — Schedule Later flow.
 * Link activates at scheduled_at, expires 30 mins after.
 */
import { useState } from 'react';
import { scheduleInterview } from '../services/api';

export default function ScheduleInterview({ candidateInfo, recruiter, onBack, onDone }) {
  const [form, setForm] = useState({
    scheduled_date: '',
    scheduled_time: '10:00',
    company_name: recruiter?.company_name || '',
    notes: '',
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const set = f => e => setForm(p => ({ ...p, [f]: e.target.value }));

  async function handleSubmit() {
    if (!form.scheduled_date) { setError('Please select a date.'); return; }
    setError(''); setLoading(true);
    const scheduledAt = new Date(`${form.scheduled_date}T${form.scheduled_time}:00`).toISOString();
    try {
      const res = await scheduleInterview({
        bank_id: candidateInfo.bankId,
        candidate_name: candidateInfo.candidateName,
        candidate_email: candidateInfo.candidateEmail,
        candidate_role: candidateInfo.candidateRole,
        scheduled_at: scheduledAt,
        recruiter_email: recruiter.email,
        interviewer_name: recruiter.full_name,
        company_name: form.company_name || recruiter.company_name,
        notes: form.notes || undefined,
        is_immediate: false,
      });
      setResult(res);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  if (result) {
    const sched = result.scheduled_interview;
    const scheduledStr = new Date(sched.scheduled_at).toLocaleString();
    const expiresStr = sched.link_expires_at ? new Date(sched.link_expires_at).toLocaleString() : null;

    return (
      <div style={S.page}>
        <div style={S.grid} />
        <div className="animate-slide-up card-glow" style={S.successCard}>
          <div style={{ fontSize: 56, textAlign: 'center', marginBottom: 16 }}>✅</div>
          <h2 style={S.successTitle}>Interview Scheduled!</h2>
          <p style={S.successSub}>
            {result.email_sent
              ? `Invitation sent to ${sched.candidate_email}`
              : `Email not sent — SMTP not configured. Share the link below.`}
          </p>

          {/* Link box */}
          <div style={S.linkBox}>
            <div className="label" style={{ marginBottom: 10, fontSize: 10 }}>Candidate Interview Link</div>
            <div style={S.linkText}>{result.interview_link}</div>
            <button className="btn-ghost" style={{ padding: '8px 16px', fontSize: 12, marginTop: 10 }}
              onClick={() => navigator.clipboard.writeText(result.interview_link)}>
              📋 Copy Link
            </button>
          </div>

          {/* Time window */}
          <div style={S.timeWindow}>
            <div style={S.timeRow}>
              <span style={{ color: 'var(--text-muted)' }}>🕐 Interview starts</span>
              <span style={{ color: 'var(--text)', fontWeight: 700 }}>{scheduledStr}</span>
            </div>
            {expiresStr && (
              <div style={S.timeRow}>
                <span style={{ color: 'var(--text-muted)' }}>⏰ Link expires</span>
                <span style={{ color: 'var(--gold)', fontWeight: 700 }}>{expiresStr}</span>
              </div>
            )}
            <p style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 10, textAlign: 'center' }}>
              Candidate has 30 minutes after the scheduled time to start. Link expires after that.
            </p>
          </div>

          {/* Details */}
          <div style={S.detailGrid}>
            <Detail label="Candidate" value={sched.candidate_name} />
            <Detail label="Email" value={sched.candidate_email} />
            {sched.candidate_role && <Detail label="Role" value={sched.candidate_role} />}
            {sched.company_name && <Detail label="Company" value={sched.company_name} />}
          </div>

          {!result.email_sent && (
            <div style={S.smtpWarn}>⚠ Set SMTP_USERNAME and SMTP_PASSWORD in your .env to enable email sending.</div>
          )}

          <div style={S.btnRow}>
            <button className="btn-ghost" style={S.btn} onClick={onBack}>← Dashboard</button>
            <button className="btn-gold" style={S.btn} onClick={onDone}>+ New Interview</button>
          </div>
        </div>
      </div>
    );
  }

  const minDate = new Date().toISOString().split('T')[0];

  return (
    <div style={S.page}>
      <div style={S.grid} />
      <div className="animate-slide-up" style={S.wrapper}>
        <button className="btn-ghost" style={S.backBtn} onClick={onBack}>← Back</button>

        <div style={S.topSection}>
          <div style={S.iconBig}>📅</div>
          <h1 style={S.title}>Schedule Interview</h1>
          <p style={S.sub}>Set a date and time. The candidate's link becomes active then and expires after 30 minutes.</p>
        </div>

        {/* Candidate summary */}
        <div className="card" style={S.candidateSummary}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={S.csName}>{candidateInfo.candidateName}</div>
              <div style={S.csEmail}>{candidateInfo.candidateEmail}</div>
              {candidateInfo.candidateRole && <div style={S.csRole}>{candidateInfo.candidateRole}</div>}
            </div>
            <div style={S.csBadge}>Interview Candidate</div>
          </div>
        </div>

        <div className="card" style={S.formCard}>
          {/* Date & Time */}
          <div className="label" style={{ marginBottom: 16 }}>Interview Date & Time</div>
          <div style={S.dateGrid}>
            <div>
              <label style={S.fieldLabel}>Date *</label>
              <input className="input-dark" type="date" value={form.scheduled_date}
                onChange={set('scheduled_date')} min={minDate} />
            </div>
            <div>
              <label style={S.fieldLabel}>Time</label>
              <input className="input-dark" type="time" value={form.scheduled_time} onChange={set('scheduled_time')} />
            </div>
          </div>
          <p style={S.hint}>Local timezone · Candidate gets a 30-min window from this time</p>

          {form.scheduled_date && form.scheduled_time && (
            <div style={S.previewBox}>
              <div style={S.previewRow}>
                <span>🔓 Link activates</span>
                <strong>{new Date(`${form.scheduled_date}T${form.scheduled_time}:00`).toLocaleString()}</strong>
              </div>
              <div style={S.previewRow}>
                <span>⏰ Link expires</span>
                <strong style={{ color: 'var(--gold)' }}>
                  {new Date(new Date(`${form.scheduled_date}T${form.scheduled_time}:00`).getTime() + 30 * 60000).toLocaleString()}
                </strong>
              </div>
            </div>
          )}

          {/* Optional */}
          <div className="label" style={{ margin: '24px 0 16px' }}>Additional Details</div>
          <div style={{ marginBottom: 14 }}>
            <label style={S.fieldLabel}>Company Name</label>
            <input className="input-dark" placeholder={recruiter?.company_name || 'Acme Corp'} value={form.company_name} onChange={set('company_name')} />
          </div>
          <div>
            <label style={S.fieldLabel}>Notes for Candidate</label>
            <textarea className="input-dark" placeholder="Any prep tips or context…"
              value={form.notes} onChange={set('notes')}
              style={{ resize: 'vertical', minHeight: 80, lineHeight: 1.6 }} />
          </div>

          {error && <div style={S.error}>{error}</div>}

          <button className="btn-gold" style={S.submit} onClick={handleSubmit} disabled={loading}>
            {loading ? '⏳ Scheduling…' : '📧 Schedule & Send Invite'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ color: 'var(--text)', fontWeight: 600 }}>{value}</span>
    </div>
  );
}

const S = {
  page: { minHeight: '100vh', background: 'var(--bg)', padding: '40px 24px', fontFamily: "'Segoe UI', system-ui, sans-serif", position: 'relative' },
  grid: { position: 'fixed', inset: 0, opacity: 0.025, backgroundImage: 'linear-gradient(var(--gold) 1px, transparent 1px), linear-gradient(90deg, var(--gold) 1px, transparent 1px)', backgroundSize: '60px 60px', pointerEvents: 'none' },
  wrapper: { maxWidth: 600, margin: '0 auto', position: 'relative', zIndex: 1 },
  backBtn: { padding: '8px 16px', fontSize: 13, marginBottom: 24 },
  topSection: { textAlign: 'center', marginBottom: 28 },
  iconBig: { fontSize: 44, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: 900, color: 'var(--text)', letterSpacing: -0.5, marginBottom: 8 },
  sub: { fontSize: 14, color: 'var(--text-muted)', lineHeight: 1.6 },
  candidateSummary: { padding: '18px 22px', marginBottom: 20 },
  csName: { fontSize: 17, fontWeight: 800, color: 'var(--text)' },
  csEmail: { fontSize: 13, color: 'var(--text-muted)', marginTop: 3 },
  csRole: { fontSize: 12, color: 'var(--gold)', marginTop: 4 },
  csBadge: { fontSize: 11, color: 'var(--gold)', background: 'var(--gold-glow)', border: '1px solid var(--border)', padding: '4px 12px', borderRadius: 20, fontWeight: 600 },
  formCard: { padding: 28 },
  dateGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 8 },
  fieldLabel: { display: 'block', fontSize: 11, color: 'var(--text-dim)', marginBottom: 7, fontWeight: 600, letterSpacing: 0.5 },
  hint: { fontSize: 11, color: 'var(--text-dim)', marginBottom: 16 },
  previewBox: { background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', marginBottom: 8 },
  previewRow: { display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 8, color: 'var(--text-muted)' },
  error: { background: 'var(--red-glow)', border: '1px solid rgba(255,69,96,0.3)', borderRadius: 10, padding: '12px 16px', fontSize: 13, color: 'var(--red)', marginTop: 16 },
  submit: { width: '100%', padding: '14px', fontSize: 15, marginTop: 20 },
  // Success screen
  successCard: { maxWidth: 520, margin: '60px auto', padding: 40, position: 'relative', zIndex: 1 },
  successTitle: { fontSize: 26, fontWeight: 900, color: 'var(--text)', textAlign: 'center', marginBottom: 8 },
  successSub: { fontSize: 14, color: 'var(--text-muted)', textAlign: 'center', marginBottom: 28, lineHeight: 1.6 },
  linkBox: { background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 12, padding: 18, marginBottom: 20 },
  linkText: { fontSize: 12, color: 'var(--blue)', wordBreak: 'break-all', fontFamily: 'monospace', lineHeight: 1.5 },
  timeWindow: { background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 12, padding: '16px 20px', marginBottom: 20 },
  timeRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13, marginBottom: 10 },
  detailGrid: { marginBottom: 16 },
  smtpWarn: { fontSize: 12, color: 'var(--gold)', background: 'var(--gold-glow)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', marginBottom: 20 },
  btnRow: { display: 'flex', gap: 12, justifyContent: 'center', marginTop: 8 },
  btn: { padding: '12px 24px', fontSize: 14 },
};
