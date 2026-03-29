/**
 * components/ThankYou.jsx — Shown to candidate after interview completion.
 * Does NOT show scores or report — that goes to recruiter only.
 */
export default function ThankYou({ candidateName }) {
  return (
    <div style={S.page}>
      <div style={S.gridOverlay} />
      <div style={S.wrap}>
        <div style={S.brand}>PRE-INTERVIEW AI</div>
        <div style={S.brandLine} />

        <div style={S.card}>
          <div style={S.iconWrap}>
            <div style={S.iconOuter}>
              <div style={S.iconInner}>✓</div>
            </div>
          </div>

          <h1 style={S.title}>Interview Complete</h1>

          {candidateName && (
            <p style={S.name}>Thank you, {candidateName}</p>
          )}

          <p style={S.body}>
            Your responses have been successfully recorded and submitted for review.
            Our team will evaluate your interview and be in touch with the next steps.
          </p>

          <div style={S.divider} />

          <div style={S.steps}>
            <Step n="1" label="Responses submitted" done />
            <Step n="2" label="AI evaluation in progress" active />
            <Step n="3" label="Recruiter review & decision" />
            <Step n="4" label="We'll reach out to you" />
          </div>

          <div style={S.footer}>
            You may close this window. · Pre-Interview AI
          </div>
        </div>
      </div>
    </div>
  );
}

function Step({ n, label, done, active }) {
  const color = done ? 'var(--success)' : active ? 'var(--gold)' : 'var(--muted)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ width: 24, height: 24, borderRadius: '50%', border: `1px solid ${color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color, flexShrink: 0, fontFamily: 'var(--font-mono)' }}>
        {done ? '✓' : n}
      </div>
      <span style={{ fontSize: 13, color }}>{label}</span>
    </div>
  );
}

const S = {
  page: { minHeight: '100vh', background: 'var(--bg-void)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 20px', position: 'relative' },
  gridOverlay: { position: 'fixed', inset: 0, zIndex: 0, backgroundImage: 'linear-gradient(rgba(201,168,76,0.025) 1px,transparent 1px),linear-gradient(90deg,rgba(201,168,76,0.025) 1px,transparent 1px)', backgroundSize: '60px 60px', pointerEvents: 'none' },
  wrap: { width: '100%', maxWidth: 440, position: 'relative', zIndex: 1, textAlign: 'center' },
  brand: { fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 700, letterSpacing: '5px', color: 'var(--gold)', marginBottom: 10 },
  brandLine: { width: 36, height: 1, background: 'linear-gradient(90deg,transparent,var(--gold),transparent)', margin: '0 auto 28px' },
  card: { background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 16, padding: '40px 36px', boxShadow: '0 32px 80px rgba(0,0,0,0.5)', animation: 'fadeUp 0.5s ease' },
  iconWrap: { marginBottom: 24, display: 'flex', justifyContent: 'center' },
  iconOuter: { width: 80, height: 80, borderRadius: '50%', border: '2px solid rgba(46,204,113,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(46,204,113,0.06)' },
  iconInner: { fontSize: 32, color: 'var(--success)' },
  title: { fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 600, color: 'var(--platinum)', marginBottom: 8 },
  name: { fontSize: 15, color: 'var(--gold)', marginBottom: 16, fontStyle: 'italic', fontFamily: 'var(--font-display)' },
  body: { fontSize: 14, color: 'var(--silver)', lineHeight: 1.7, marginBottom: 24 },
  divider: { height: 1, background: 'var(--border)', marginBottom: 20 },
  steps: { textAlign: 'left', marginBottom: 28 },
  footer: { fontSize: 11, color: 'var(--muted)' },
};
