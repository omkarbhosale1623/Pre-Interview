/**
 * components/Report.jsx — Post-interview screen.
 *
 * For CANDIDATES (joined via link): Shows "Thank You" screen — no report.
 * For RECRUITERS (in dashboard):    Shows full detailed evaluation report.
 */
import { useEffect, useState, useRef } from 'react';
import { getEvaluation, runEvaluation, textReportUrl } from '../services/api';

export default function Report({ sessionId, isCandidate = false, onRestart }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const hasTriggered = useRef(false);

  useEffect(() => {
    if (!sessionId) { setLoading(false); return; }
    if (hasTriggered.current) return;
    hasTriggered.current = true;
    let cancelled = false;
    (async () => {
      try {
        // Always run evaluation when report screen loads (so recruiter gets email
        // even when candidate is the one who completed the interview).
        let r;
        try {
          r = await getEvaluation(sessionId);
        } catch {
          // Evaluation not yet run — trigger it
          try {
            r = await runEvaluation(sessionId);
          } catch (evalErr) {
            // If candidate, silently ignore — they see thank-you regardless
            if (isCandidate) { if (!cancelled) setLoading(false); return; }
            throw evalErr;
          }
        }
        if (!cancelled) setReport(r);
      } catch (e) {
        if (!cancelled) setError(`Evaluation failed: ${e.message}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [sessionId, isCandidate]);

  // ── Candidate thank-you screen ────────────────────────────────────────────
  if (isCandidate) {
    return (
      <div style={S.page}>
        <div style={S.grid} />
        <div className="animate-slide-up" style={S.thankYouCard}>
          <div style={S.tyIcon}>🎉</div>
          <h1 style={S.tyTitle}>Interview Complete!</h1>
          <p style={S.tySub}>
            Thank you for completing the Pre-Interview AI screening.
            Your responses have been submitted and the hiring team will be in touch shortly.
          </p>
          <div style={S.tyChecks}>
            {['Your interview has been recorded and submitted', 'Your responses are being AI-evaluated', 'The recruiter will review and reach out with next steps'].map((t, i) => (
              <div key={i} style={S.tyCheck}>
                <span style={{ color: 'var(--green)', fontSize: 16 }}>✓</span>
                <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>{t}</span>
              </div>
            ))}
          </div>
          <div style={S.tyBranding}>
            <span className="gold-text" style={{ fontSize: 16, fontWeight: 800 }}>Pre-Interview AI</span>
            <span style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>AI-powered voice interviews</span>
          </div>
        </div>
      </div>
    );
  }

  // ── Recruiter loading / error ─────────────────────────────────────────────
  if (loading) return (
    <div style={S.fullscreen}>
      <div style={{ fontSize: 40, animation: 'spin 1.5s linear infinite' }}>⏳</div>
      <p style={{ color: 'var(--text-muted)', marginTop: 16, fontSize: 14 }}>Evaluating responses with AI…</p>
    </div>
  );
  if (error) return (
    <div style={S.fullscreen}>
      <div style={{ fontSize: 36 }}>⚠️</div>
      <p style={{ color: 'var(--red)', marginTop: 12 }}>{error}</p>
      <button className="btn-ghost" style={{ marginTop: 20, padding: '10px 24px' }} onClick={onRestart}>← Try Again</button>
    </div>
  );
  if (!report) return null;

  // ── Full recruiter report ─────────────────────────────────────────────────
  const scoreColor = report.overall_score >= 75 ? 'var(--green)' : report.overall_score >= 55 ? 'var(--gold)' : 'var(--red)';
  const recCfg = {
    'Strong Hire': { color: 'var(--green)', icon: '🌟', bg: 'var(--green-glow)' },
    'Hire':        { color: 'var(--green)', icon: '✅', bg: 'var(--green-glow)' },
    'Consider':    { color: 'var(--gold)',  icon: '🤔', bg: 'var(--gold-glow)' },
    'No Hire':     { color: 'var(--red)',   icon: '❌', bg: 'var(--red-glow)' },
  }[report.recommendation] || { color: 'var(--gold)', icon: '🤔', bg: 'var(--gold-glow)' };

  return (
    <div style={S.reportPage}>
      <div style={S.grid} />
      <div style={S.reportInner}>

        {/* Hero */}
        <div className="card-glow animate-fade-in" style={S.hero}>
          <div>
            <div style={S.heroName}>{report.candidate_name}</div>
            {report.candidate_role && <div style={S.heroRole}>{report.candidate_role}</div>}
            <div style={S.heroMeta}>{new Date(report.generated_at).toLocaleString()} · {report.question_evaluations.length} questions</div>
          </div>
          <ScoreRing score={report.overall_score} color={scoreColor} />
        </div>

        {/* Recommendation */}
        <div style={{ ...S.recBanner, background: recCfg.bg, borderColor: recCfg.color + '40' }}>
          <span style={{ fontSize: 36 }}>{recCfg.icon}</span>
          <div>
            <div style={{ ...S.recTitle, color: recCfg.color }}>{report.recommendation}</div>
            <div style={S.recSub}>Rating: <strong style={{ color: recCfg.color }}>{report.overall_rating.toUpperCase()}</strong></div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
            <a href={textReportUrl(sessionId)} target="_blank" rel="noreferrer"
              className="btn-ghost" style={{ padding: '10px 18px', fontSize: 12, textDecoration: 'none', display: 'inline-block' }}>
              ↓ Download
            </a>
            <button className="btn-gold" style={{ padding: '10px 18px', fontSize: 12 }} onClick={onRestart}>+ New</button>
          </div>
        </div>

        {/* Executive Summary */}
        <div className="card" style={S.section}>
          <div className="label" style={S.sectionTitle}>Executive Summary</div>
          <p style={S.bodyText}>{report.executive_summary || report.summary}</p>
        </div>

        {/* Risk Flags */}
        {report.risk_flags?.length > 0 && (
          <div style={{ ...S.section, background: 'rgba(255,69,96,0.06)', border: '1px solid rgba(255,69,96,0.25)', borderRadius: 16, padding: '20px 24px' }}>
            <div className="label" style={{ ...S.sectionTitle, color: 'var(--red)' }}>⚠ Risk Flags</div>
            {report.risk_flags.map((f, i) => <div key={i} style={{ fontSize: 13, color: 'var(--red)', marginBottom: 6 }}>• {f}</div>)}
          </div>
        )}

        {/* Hiring Notes */}
        {report.hiring_notes && (
          <div style={{ ...S.section, background: 'rgba(201,168,76,0.05)', border: '1px solid var(--border)', borderRadius: 16, padding: '20px 24px' }}>
            <div className="label" style={S.sectionTitle}>🔒 Private Hiring Notes</div>
            <p style={S.bodyText}>{report.hiring_notes}</p>
          </div>
        )}

        {/* Strengths + Improvements */}
        <div style={S.twoCol}>
          <div className="card" style={{ ...S.section }}>
            <div className="label" style={{ ...S.sectionTitle, color: 'var(--green)' }}>✓ Key Strengths</div>
            {report.strengths.map((s, i) => <div key={i} style={{ ...S.bullet, color: 'var(--green)' }}>• <span style={{ color: 'var(--text)' }}>{s}</span></div>)}
          </div>
          <div className="card" style={{ ...S.section }}>
            <div className="label" style={{ ...S.sectionTitle, color: 'var(--gold)' }}>↑ Areas to Improve</div>
            {report.improvements.map((s, i) => <div key={i} style={{ ...S.bullet, color: 'var(--gold)' }}>• <span style={{ color: 'var(--text)' }}>{s}</span></div>)}
          </div>
        </div>

        {/* Q&A Breakdown */}
        <div className="label" style={{ ...S.sectionTitle, margin: '8px 0 16px' }}>Question-by-Question Breakdown</div>
        {report.question_evaluations.map((qe, i) => (
          <QuestionCard key={qe.question_id} qe={qe} index={i + 1} />
        ))}

        <div style={{ paddingBottom: 48 }} />
      </div>
    </div>
  );
}

function ScoreRing({ score, color }) {
  const r = 48, cx = 56, cy = 56, circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  return (
    <div style={{ position: 'relative', width: 112, height: 112, flexShrink: 0 }}>
      <svg width={112} height={112} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--surface2)" strokeWidth={10} />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth={10}
          strokeDasharray={`${fill} ${circ}`} strokeLinecap="round" />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: 28, fontWeight: 900, color }}>{score}</span>
        <span style={{ fontSize: 9, color: 'var(--text-dim)', letterSpacing: 2 }}>/ 100</span>
      </div>
    </div>
  );
}

function QuestionCard({ qe, index }) {
  const [expanded, setExpanded] = useState(false);
  const sc = qe.score >= 75 ? 'var(--green)' : qe.score >= 55 ? 'var(--gold)' : 'var(--red)';
  return (
    <div className="card animate-fade-in" style={S.qCard}>
      <div style={S.qHeader} onClick={() => setExpanded(e => !e)}>
        <div style={{ flex: 1 }}>
          <div style={S.qLabel}>
            Q{index}{qe.topic ? ` · ${qe.topic}` : ''}
            {qe.was_skipped && <span style={S.skipTag}>SKIPPED</span>}
          </div>
          <p style={S.qText}>{qe.question_text}</p>
        </div>
        <div style={{ textAlign: 'center', marginLeft: 20 }}>
          <div style={{ fontSize: 32, fontWeight: 900, color: sc, lineHeight: 1 }}>{qe.score}</div>
          <div style={{ fontSize: 10, color: sc, letterSpacing: 1 }}>{qe.rating.toUpperCase()}</div>
        </div>
        <span style={{ color: 'var(--text-dim)', marginLeft: 12, fontSize: 14 }}>{expanded ? '▲' : '▼'}</span>
      </div>

      {/* Answer */}
      <div style={S.answerBox}>
        <div style={S.answerLabel}>Candidate's Answer</div>
        <p style={S.answerText}>{qe.answer_transcript || '(No response)'}</p>
      </div>

      {/* Quick feedback */}
      <p style={S.feedback}>{qe.feedback}</p>

      {/* Expanded detail */}
      {expanded && (
        <div className="animate-fade-in" style={S.expandedArea}>
          {qe.detailed_feedback && (
            <div style={{ marginBottom: 16 }}>
              <div className="label" style={{ fontSize: 10, marginBottom: 10, color: 'var(--text-dim)' }}>Detailed Analysis</div>
              <p style={{ ...S.bodyText, fontSize: 13 }}>{qe.detailed_feedback}</p>
            </div>
          )}

          {qe.communication && (
            <div style={{ marginBottom: 16 }}>
              <div className="label" style={{ fontSize: 10, marginBottom: 12, color: 'var(--text-dim)' }}>Communication Assessment</div>
              <div style={S.commGrid}>
                {Object.entries(qe.communication).map(([k, v]) => (
                  <CommBar key={k} label={k} value={v} />
                ))}
              </div>
            </div>
          )}

          <div style={S.twoCol}>
            {qe.strengths.length > 0 && (
              <div>
                <div style={{ fontSize: 10, color: 'var(--green)', fontWeight: 700, marginBottom: 8, letterSpacing: 1, textTransform: 'uppercase' }}>Strengths</div>
                {qe.strengths.map((s, i) => <div key={i} style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 5 }}>✓ {s}</div>)}
              </div>
            )}
            {qe.improvements.length > 0 && (
              <div>
                <div style={{ fontSize: 10, color: 'var(--gold)', fontWeight: 700, marginBottom: 8, letterSpacing: 1, textTransform: 'uppercase' }}>Improve</div>
                {qe.improvements.map((s, i) => <div key={i} style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 5 }}>↑ {s}</div>)}
              </div>
            )}
          </div>

          {qe.keywords_hit.length > 0 && (
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {qe.keywords_hit.map(k => (
                <span key={k} style={S.keyword}>{k}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CommBar({ label, value }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 5, color: 'var(--text-muted)' }}>
        <span style={{ textTransform: 'capitalize' }}>{label}</span>
        <span style={{ color: value >= 7 ? 'var(--green)' : value >= 5 ? 'var(--gold)' : 'var(--red)', fontWeight: 700 }}>{value}/10</span>
      </div>
      <div style={{ height: 4, background: 'var(--surface2)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${value * 10}%`, background: value >= 7 ? 'var(--green)' : value >= 5 ? 'var(--gold)' : 'var(--red)', borderRadius: 2, transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
}

const S = {
  page: { minHeight: '100vh', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "'Segoe UI', system-ui, sans-serif", position: 'relative' },
  grid: { position: 'fixed', inset: 0, opacity: 0.02, backgroundImage: 'linear-gradient(var(--gold) 1px, transparent 1px), linear-gradient(90deg, var(--gold) 1px, transparent 1px)', backgroundSize: '60px 60px', pointerEvents: 'none' },
  // Thank you
  thankYouCard: { maxWidth: 480, width: '100%', background: 'var(--surface)', border: '1px solid var(--border-med)', borderRadius: 24, padding: '48px 40px', textAlign: 'center', position: 'relative', zIndex: 1, boxShadow: '0 0 60px var(--gold-glow2)' },
  tyIcon: { fontSize: 64, marginBottom: 20 },
  tyTitle: { fontSize: 30, fontWeight: 900, color: 'var(--text)', marginBottom: 16, letterSpacing: -0.5 },
  tySub: { fontSize: 15, color: 'var(--text-muted)', lineHeight: 1.7, marginBottom: 28 },
  tyChecks: { display: 'flex', flexDirection: 'column', gap: 12, textAlign: 'left', background: 'var(--surface2)', borderRadius: 14, padding: '20px 22px', marginBottom: 28 },
  tyCheck: { display: 'flex', gap: 12, alignItems: 'flex-start' },
  tyBranding: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 },
  fullscreen: { minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontFamily: 'system-ui', gap: 12 },
  // Report
  reportPage: { minHeight: '100vh', background: 'var(--bg)', padding: '36px 24px', fontFamily: "'Segoe UI', system-ui, sans-serif", position: 'relative' },
  reportInner: { maxWidth: 820, margin: '0 auto', position: 'relative', zIndex: 1 },
  hero: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '28px 32px', marginBottom: 20 },
  heroName: { fontSize: 26, fontWeight: 900, color: 'var(--text)' },
  heroRole: { fontSize: 13, color: 'var(--text-muted)', marginTop: 4 },
  heroMeta: { fontSize: 11, color: 'var(--text-dim)', marginTop: 8, fontFamily: 'monospace' },
  recBanner: { display: 'flex', alignItems: 'center', gap: 18, border: '1px solid', borderRadius: 16, padding: '18px 24px', marginBottom: 20 },
  recTitle: { fontSize: 22, fontWeight: 900 },
  recSub: { fontSize: 13, color: 'var(--text-muted)', marginTop: 3 },
  section: { padding: '22px 26px', marginBottom: 16 },
  sectionTitle: { marginBottom: 14 },
  bodyText: { fontSize: 14, color: 'var(--text)', lineHeight: 1.8, margin: 0 },
  bullet: { fontSize: 13, marginBottom: 8, display: 'flex', gap: 8 },
  twoCol: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 },
  qCard: { padding: '22px 26px', marginBottom: 14, cursor: 'pointer' },
  qHeader: { display: 'flex', alignItems: 'flex-start', marginBottom: 14 },
  qLabel: { fontSize: 11, color: 'var(--gold)', fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 6 },
  qText: { fontSize: 15, color: 'var(--text)', margin: 0, lineHeight: 1.5, fontWeight: 600 },
  skipTag: { background: 'var(--red-glow)', color: 'var(--red)', fontSize: 9, padding: '2px 7px', borderRadius: 10, marginLeft: 8, verticalAlign: 'middle' },
  answerBox: { background: 'var(--bg)', borderRadius: 10, padding: '12px 16px', marginBottom: 12 },
  answerLabel: { fontSize: 9, color: 'var(--text-dim)', letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 6 },
  answerText: { fontSize: 13, color: 'var(--text-muted)', margin: 0, lineHeight: 1.7 },
  feedback: { fontSize: 13, color: 'var(--text)', lineHeight: 1.6, margin: '0 0 8px' },
  expandedArea: { borderTop: '1px solid var(--border)', marginTop: 16, paddingTop: 16 },
  commGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 24px' },
  keyword: { background: 'var(--green-glow)', color: 'var(--green)', border: '1px solid rgba(0,200,150,0.2)', borderRadius: 20, padding: '3px 12px', fontSize: 11 },
};
