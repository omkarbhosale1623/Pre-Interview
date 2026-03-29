/**
 * App.jsx — Pre-Interview AI · Top-level flow manager.
 *
 * Steps:
 *  AUTH        → recruiter sign-in / sign-up
 *  UPLOAD      → dashboard (upload bank + candidate details)
 *  SCHEDULE    → schedule later (date/time picker)
 *  CONFIRM     → schedule now confirmation (send link)
 *  INTERVIEW   → live interview (recruiter view, shouldn't happen)
 *  REPORT      → evaluation report (recruiter)
 *  CANDIDATE   → thank-you screen (candidate who joined via link)
 *  JOINING     → loading state while resolving token
 *  JOIN_ERROR  → invalid/expired link
 */
import { useEffect, useState } from 'react';
import Auth from './components/Auth';
import InterviewRoom from './components/InterviewRoom';
import Report from './components/Report';
import ScheduleInterview from './components/ScheduleInterview';
import UploadBank from './components/UploadBank';
import { joinInterview, scheduleInterview } from './services/api';

const STEP = {
  AUTH: 'auth', UPLOAD: 'upload', SCHEDULE: 'schedule',
  INTERVIEW: 'interview', REPORT: 'report',
  CANDIDATE: 'candidate',   // thank-you screen
  JOINING: 'joining', JOIN_ERROR: 'join_error',
};

export default function App() {
  const [step, setStep] = useState(STEP.AUTH);
  const [recruiter, setRecruiter] = useState(null);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('pia_theme') || 'dark';
  });
  const [token, setToken] = useState(null);
  const [session, setSession] = useState(null);
  const [bank, setBank] = useState(null);
  const [completedSessionId, setCompletedSessionId] = useState(null);
  const [joinError, setJoinError] = useState('');
  const [candidateInfo, setCandidateInfo] = useState(null);  // {bankId, candidateName, candidateEmail, candidateRole}
  const [isCandidate, setIsCandidate] = useState(false);
  const [scheduleResult, setScheduleResult] = useState(null);

  // ── Check auth on load ───────────────────────────────────────────────────
  useEffect(() => {
    const saved = localStorage.getItem('pia_token');
    const savedRec = localStorage.getItem('pia_recruiter');
    if (saved && savedRec) {
      try {
        setToken(saved);
        setRecruiter(JSON.parse(savedRec));
        setStep(STEP.UPLOAD);
      } catch (_) {}
    }

    // ── Check for candidate join URL ─────────────────────────────────────
    const match = window.location.pathname.match(/^\/interview\/join\/([^/]+)$/);
    if (match) {
      setStep(STEP.JOINING);
      setIsCandidate(true);
      joinInterview(match[1])
        .then(({ session: s, bank: b }) => {
          setSession(s);
          setBank(b);
          window.history.replaceState({}, '', '/');
          setStep(STEP.INTERVIEW);
        })
        .catch(e => {
          setJoinError(e.message);
          setStep(STEP.JOIN_ERROR);
        });
    }
  }, []);

  // ── Recruiter auth ────────────────────────────────────────────────────────
  function handleAuth(tok, rec) {
    setToken(tok); setRecruiter(rec); setStep(STEP.UPLOAD);
  }

  function handleSignOut() {
    localStorage.removeItem('pia_token');
    localStorage.removeItem('pia_recruiter');
    setToken(null); setRecruiter(null);
    setStep(STEP.AUTH);
  }

  // ── Schedule Now ──────────────────────────────────────────────────────────
  async function handleScheduleNow(info) {
    setCandidateInfo(info);
    // Schedule immediately (is_immediate=true, scheduled_at = now)
    try {
      const res = await scheduleInterview({
        bank_id: info.bankId,
        candidate_name: info.candidateName,
        candidate_email: info.candidateEmail,
        candidate_role: info.candidateRole,
        scheduled_at: new Date().toISOString(),
        recruiter_email: recruiter.email,
        interviewer_name: recruiter.full_name,
        company_name: recruiter.company_name,
        is_immediate: true,
      });
      setScheduleResult(res);
      setStep('confirm');
    } catch (e) {
      alert(`Failed to schedule: ${e.message}`);
    }
  }

  // ── Schedule Later ────────────────────────────────────────────────────────
  function handleScheduleLater(info) {
    setCandidateInfo(info);
    setStep(STEP.SCHEDULE);
  }

  // ── Interview complete (recruiter side) ────────────────────────────────
  function handleInterviewComplete(sid) {
    setCompletedSessionId(sid);
    // Candidate sees thank-you, recruiter would see report
    if (isCandidate) setStep(STEP.CANDIDATE);
    else setStep(STEP.REPORT);
  }

  function handleRestart() {
    setSession(null); setBank(null);
    setCompletedSessionId(null); setCandidateInfo(null);
    setScheduleResult(null); setIsCandidate(false);
    setStep(STEP.UPLOAD);
  }

  function toggleTheme() {
    setTheme(t => (t === 'dark' ? 'light' : 'dark'));
  }

  useEffect(() => {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('pia_theme', theme);
  }, [theme]);

  // ── Render ────────────────────────────────────────────────────────────────

  if (step === STEP.JOINING) return <Loader message="Joining your interview…" sub="Validating your link, please wait." />;
  if (step === STEP.JOIN_ERROR) return <JoinError message={joinError} />;

  if (step === STEP.CANDIDATE || (isCandidate && step === STEP.REPORT)) {
    return <Report sessionId={completedSessionId} isCandidate={true} />;
  }

  if (step === STEP.AUTH) return <Auth onAuth={handleAuth} />;

  if (step === 'confirm' && scheduleResult) {
    return <ConfirmSent result={scheduleResult} onDone={handleRestart} onBack={() => setStep(STEP.UPLOAD)} />;
  }

  return (
    <>
      {/* theme toggle control */}
      <div style={{ position: 'fixed', top: 12, right: 12, zIndex: 999 }}>
        <button className="theme-toggle-btn" onClick={toggleTheme}>
          {theme === 'dark' ? '🌞' : '🌙'}
        </button>
      </div>

      {step === STEP.UPLOAD && (
        <UploadBank recruiter={recruiter} onScheduleNow={handleScheduleNow}
          onScheduleLater={handleScheduleLater} onSignOut={handleSignOut} />
      )}
      {step === STEP.SCHEDULE && candidateInfo && (
        <ScheduleInterview candidateInfo={candidateInfo} recruiter={recruiter}
          onBack={() => setStep(STEP.UPLOAD)} onDone={handleRestart} />
      )}
      {step === STEP.INTERVIEW && session && bank && (
        <InterviewRoom session={session} bank={bank} onComplete={handleInterviewComplete} />
      )}
      {step === STEP.REPORT && completedSessionId && (
        <Report sessionId={completedSessionId} isCandidate={false} onRestart={handleRestart} />
      )}
    </>
  );
}

// ── Confirm sent screen (Schedule Now) ────────────────────────────────────────

function ConfirmSent({ result, onDone, onBack }) {
  const sched = result.scheduled_interview;
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
      <div className="animate-slide-up card-glow" style={{ maxWidth: 480, width: '100%', padding: 44, textAlign: 'center' }}>
        <div style={{ fontSize: 60, marginBottom: 20 }}>⚡</div>
        <h2 style={{ fontSize: 26, fontWeight: 900, color: 'var(--text)', marginBottom: 12 }}>Link Sent!</h2>
        <p style={{ fontSize: 14, color: 'var(--text-muted)', lineHeight: 1.7, marginBottom: 28 }}>
          {result.email_sent
            ? `Interview link sent to ${sched.candidate_email}. They can start immediately.`
            : `Email not configured. Share this link with ${sched.candidate_name}:`}
        </p>
        {!result.email_sent && (
          <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 12, padding: 16, marginBottom: 24 }}>
            <div style={{ fontSize: 12, color: 'var(--blue)', wordBreak: 'break-all', fontFamily: 'monospace', marginBottom: 10 }}>{result.interview_link}</div>
            <button className="btn-ghost" style={{ padding: '7px 14px', fontSize: 12 }}
              onClick={() => navigator.clipboard.writeText(result.interview_link)}>📋 Copy</button>
          </div>
        )}
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button className="btn-ghost" style={{ padding: '12px 22px', fontSize: 14 }} onClick={onBack}>← Back</button>
          <button className="btn-gold" style={{ padding: '12px 22px', fontSize: 14 }} onClick={onDone}>+ New Interview</button>
        </div>
      </div>
    </div>
  );
}

// ── Loading / Error screens ───────────────────────────────────────────────────

function Loader({ message, sub }) {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, fontFamily: 'system-ui', color: 'var(--text-muted)', textAlign: 'center' }}>
      <div style={{ fontSize: 40 }}>🔗</div>
      <div style={{ fontSize: 17, color: 'var(--text)' }}>{message}</div>
      <div style={{ fontSize: 13 }}>{sub}</div>
    </div>
  );
}

function JoinError({ message }) {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, fontFamily: 'system-ui', textAlign: 'center', padding: 24 }}>
      <div style={{ fontSize: 40 }}>⚠️</div>
      <div style={{ fontSize: 20, color: 'var(--red)', fontWeight: 700 }}>Interview Link Error</div>
      <div style={{ fontSize: 14, color: 'var(--text-muted)', maxWidth: 400, lineHeight: 1.7 }}>{message}</div>
      <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 8 }}>Please contact your recruiter for a new link.</div>
    </div>
  );
}
