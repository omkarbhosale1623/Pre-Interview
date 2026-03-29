/**
 * components/InterviewRoom.jsx — Speech-to-Speech interview UI.
 *
 * UX improvements:
 *  - "Processing…" state shows immediately when user stops speaking
 *  - "Preparing next question…" distinguishes STT phase from TTS fetch phase
 *  - Silence countdown shows remaining seconds so user knows when to speak
 *  - No skip button (as before), submit button only shown when there's a transcript
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { conversationStep } from '../services/api';
import { useInterviewSpeech } from '../hooks/useSpeech';

const MAX_REPEATS = 2;

export default function InterviewRoom({ session, bank, onComplete }) {
  const [botText,     setBotText]     = useState('');
  const [error,       setError]       = useState('');
  const [hasStarted,  setHasStarted]  = useState(false);
  const [currentQ,    setCurrentQ]    = useState(session.current_question_index || 0);
  const [subStatus,   setSubStatus]   = useState(''); // fine-grained status inside a phase
  const sessionRef = useRef(session);

  // ── Answer handler ────────────────────────────────────────────────────────

  const handleAnswerReady = useCallback(async (text, skipped, durationMs) => {
    setError('');
    setSubStatus('Sending your answer…');
    try {
      const res = await conversationStep(sessionRef.current.id, text);
      if (typeof res.question_index === 'number') {
        setCurrentQ(res.question_index);
        sessionRef.current.current_question_index = res.question_index;
      }
      setSubStatus('');

      if (res.done) {
        onComplete(sessionRef.current.id);
        return;
      }
      if (res.bot_text) {
        setBotText(res.bot_text);
        askQuestion(res.bot_text, res.audio);
      }
    } catch (e) {
      setSubStatus('');
      setError(`Error: ${e.message}`);
    }
  }, [onComplete]);

  // ── Speech orchestrator ───────────────────────────────────────────────────

  const {
    phase,
    countdown,
    repeatCount,
    transcript,
    askQuestion,
    forceSubmit,
    sttSupported,
    isSpeaking,
  } = useInterviewSpeech({
    onAnswerReady: handleAnswerReady,
    onRepeat: (n) => {
      setSubStatus(`No response detected — repeating question (${n}/${MAX_REPEATS})`);
      setTimeout(() => setSubStatus(''), 1500);
    },
    onSkip: () => setSubStatus('Moving to next question…'),
  });

  // ── Start interview ───────────────────────────────────────────────────────

  const startConversation = useCallback(async () => {
    setError('');
    setHasStarted(true);
    setSubStatus('Connecting…');
    try {
      const res = await conversationStep(sessionRef.current.id);
      if (typeof res.question_index === 'number') {
        setCurrentQ(res.question_index);
        sessionRef.current.current_question_index = res.question_index;
      }
      setSubStatus('');
      if (res.done) { onComplete(sessionRef.current.id); return; }
      if (res.bot_text) {
        setBotText(res.bot_text);
        askQuestion(res.bot_text, res.audio);
      }
    } catch (e) {
      setSubStatus('');
      setHasStarted(false);
      setError(`Failed to start: ${e.message}`);
    }
  }, [onComplete]);

  const totalQ   = bank?.questions?.length || 1;
  const progress = Math.min(100, (currentQ / totalQ) * 100);

  // ── Pre-start screen ──────────────────────────────────────────────────────

  if (!hasStarted) {
    return (
      <div style={S.fullscreen}>
        <div style={{ textAlign: 'center', maxWidth: 480, padding: '40px 24px' }}>
          <div style={{ fontSize: 48, marginBottom: 20 }}>🎙</div>
          <h2 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text)', marginBottom: 12 }}>
            Ready to begin?
          </h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: 32, lineHeight: 1.7 }}>
            Find a quiet place and allow microphone access. The AI interviewer will speak first,
            then listen for your answer. Answer naturally — there's no rush.
          </p>
          <div style={S.tipsRow}>
            {['🔇 Quiet environment', '🎤 Mic allowed', '🗣 Speak clearly'].map(t => (
              <span key={t} style={S.tip}>{t}</span>
            ))}
          </div>
          <button className="btn-gold" style={{ padding: '16px 56px', fontSize: 16, marginTop: 32 }}
            onClick={startConversation}>
            ▶ Start Interview
          </button>
          {error && <div style={{ ...S.errorBox, marginTop: 20 }}>{error}</div>}
        </div>
      </div>
    );
  }

  if (!botText && phase !== 'complete' && !subStatus) {
    return (
      <div style={S.fullscreen}>
        <div style={{ fontSize: 40, animation: 'pulse-dot 2s ease infinite' }}>🎙</div>
        <p style={{ color: 'var(--text-muted)', marginTop: 16 }}>Starting interview…</p>
      </div>
    );
  }

  if (phase === 'complete') {
    return (
      <div style={S.fullscreen}>
        <div style={{ fontSize: 56 }}>✅</div>
        <p style={{ fontSize: 20, color: 'var(--green)', marginTop: 16, fontWeight: 700 }}>
          Interview Complete
        </p>
      </div>
    );
  }

  return (
    <div style={S.page}>
      <div style={S.grid} />

      {/* Header */}
      <div style={S.header}>
        <div>
          <div style={S.candidateName}>{session.candidate_name}</div>
          {session.candidate_role && <div style={S.candidateRole}>{session.candidate_role}</div>}
        </div>
        <div style={S.headerRight}>
          <span style={S.qBadge}>Q{currentQ + 1} / {totalQ}</span>
          {repeatCount > 0 && (
            <span style={S.repeatBadge}>Repeat {repeatCount}/{MAX_REPEATS}</span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div style={S.progressBg}>
        <div style={{ ...S.progressFill, width: `${progress}%` }} />
      </div>

      {/* Main content */}
      <div style={S.content}>

        {/* Status bar */}
        <StatusBar phase={phase} isSpeaking={isSpeaking} countdown={countdown} subStatus={subStatus} />

        {/* Current question */}
        {botText && (
          <div className="card animate-fade-in" style={S.questionCard}>
            <div style={S.qLabel}>Current Question</div>
            <p style={S.questionText}>{botText}</p>
          </div>
        )}

        {/* Waveform visualizer */}
        <PhaseVisual phase={phase} isSpeaking={isSpeaking} />

        {/* Transcript */}
        {transcript && (
          <div className="card animate-fade-in" style={S.transcriptCard}>
            <div className="label" style={{ marginBottom: 8, fontSize: 10 }}>Your Response</div>
            <p style={S.transcriptText}>{transcript}</p>
          </div>
        )}

        {/* Submit button — only when transcript exists and not already processing */}
        {transcript && phase === 'countdown' && (
          <div style={S.controls}>
            <button className="btn-gold" style={S.submitBtn} onClick={forceSubmit}>
              ✓ Submit Answer
            </button>
          </div>
        )}

        {!sttSupported && (
          <div style={S.warnBox}>⚠ Microphone recording not supported in this browser.</div>
        )}
        {error && <div style={S.errorBox}>{error}</div>}
      </div>
    </div>
  );
}

// ── Status bar ────────────────────────────────────────────────────────────────

function StatusBar({ phase, isSpeaking, countdown, subStatus }) {
  // Sub-status overrides phase display during answer processing
  if (subStatus) {
    return (
      <div style={{ ...S.statusBar, borderColor: 'var(--gold)40', background: 'var(--gold)0a' }}>
        <span style={{ fontSize: 20 }}>⏳</span>
        <span style={{ fontSize: 14, color: 'var(--gold)', fontWeight: 600 }}>{subStatus}</span>
      </div>
    );
  }

  const cfgs = {
    loading:      { color: 'var(--text-muted)', icon: '⏳', text: 'Loading…' },
    bot_speaking: { color: 'var(--blue)',        icon: '🔊', text: 'AI interviewer speaking…' },
    countdown: {
      color: isSpeaking ? 'var(--gold)' : 'var(--text-muted)',
      icon: '🎤',
      text: isSpeaking
        ? 'Recording — speak clearly'
        : `Listening — ${Math.ceil(countdown)}s remaining`,
    },
    processing:   { color: 'var(--text-muted)', icon: '↑',  text: 'Processing your answer…' },
    complete:     { color: 'var(--green)',       icon: '✅', text: 'Interview complete!' },
  };
  const cfg = cfgs[phase] || cfgs.loading;

  return (
    <div style={{ ...S.statusBar, borderColor: cfg.color + '40', background: cfg.color + '0a' }}>
      <span style={{ fontSize: 20 }}>{cfg.icon}</span>
      <span style={{ fontSize: 14, color: cfg.color, fontWeight: 600 }}>{cfg.text}</span>
      {phase === 'countdown' && (
        <div style={{
          marginLeft: 'auto',
          width: 10, height: 10, borderRadius: '50%',
          background: isSpeaking ? 'var(--gold)' : 'rgba(255,255,255,0.15)',
          animation: 'pulse-dot 1.2s ease-in-out infinite',
        }} />
      )}
    </div>
  );
}

// ── Waveform visualizer ───────────────────────────────────────────────────────

function PhaseVisual({ phase, isSpeaking }) {
  if (phase === 'bot_speaking') {
    return (
      <div style={S.visualBox}>
        <div style={S.waveform}>
          {[...Array(9)].map((_, i) => (
            <div key={i} className="wave-bar"
              style={{ ...S.waveBar, background: 'var(--blue)', animationDelay: `${i * 0.1}s` }} />
          ))}
        </div>
        <span style={{ fontSize: 12, color: 'var(--blue)', marginTop: 10 }}>AI Speaking</span>
      </div>
    );
  }

  if (phase === 'countdown') {
    return (
      <div style={S.visualBox}>
        <div style={S.waveform}>
          {[...Array(9)].map((_, i) => (
            <div key={i}
              className={isSpeaking ? 'wave-bar' : undefined}
              style={{
                ...S.waveBar,
                background: isSpeaking
                  ? 'linear-gradient(180deg, var(--gold), var(--gold-light))'
                  : 'var(--text-dim)',
                height: isSpeaking ? undefined : 6,
                animationDelay: `${i * 0.1}s`,
              }} />
          ))}
        </div>
        <span style={{ fontSize: 12, color: isSpeaking ? 'var(--gold)' : 'var(--text-muted)', marginTop: 10 }}>
          {isSpeaking ? 'Recording your answer…' : 'Waiting for your voice…'}
        </span>
      </div>
    );
  }

  if (phase === 'processing') {
    return (
      <div style={{ ...S.visualBox, gap: 8 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {[0, 1, 2].map(i => (
            <div key={i} style={{
              width: 8, height: 8, borderRadius: '50%',
              background: 'var(--gold)', opacity: 0.5,
              animation: 'pulse-dot 1.2s ease-in-out infinite',
              animationDelay: `${i * 0.2}s`,
            }} />
          ))}
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Preparing next question…</span>
      </div>
    );
  }

  return null;
}

// ── Styles ────────────────────────────────────────────────────────────────────

const S = {
  page: {
    minHeight: '100vh', background: 'var(--bg)',
    display: 'flex', flexDirection: 'column',
    fontFamily: "'Segoe UI', system-ui, sans-serif", position: 'relative',
  },
  grid: {
    position: 'fixed', inset: 0, pointerEvents: 'none', opacity: 0.02,
    backgroundImage: 'linear-gradient(var(--gold) 1px,transparent 1px),linear-gradient(90deg,var(--gold) 1px,transparent 1px)',
    backgroundSize: '60px 60px',
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
    padding: '24px 32px 0', position: 'relative', zIndex: 1,
  },
  candidateName: { fontSize: 18, fontWeight: 800, color: 'var(--text)' },
  candidateRole: { fontSize: 12, color: 'var(--text-muted)', marginTop: 3 },
  headerRight:   { display: 'flex', alignItems: 'center', gap: 10 },
  qBadge: {
    fontSize: 12, fontFamily: 'monospace', color: 'var(--gold)',
    background: 'var(--gold-glow)', border: '1px solid var(--border)',
    padding: '4px 14px', borderRadius: 20,
  },
  repeatBadge: {
    fontSize: 11, color: 'var(--red)',
    background: 'var(--red-glow)', border: '1px solid rgba(255,69,96,0.3)',
    padding: '4px 12px', borderRadius: 20,
  },
  progressBg: {
    height: 2, background: 'var(--surface2)',
    margin: '20px 32px 0', overflow: 'hidden', borderRadius: 1,
  },
  progressFill: {
    height: '100%',
    background: 'linear-gradient(90deg, var(--gold), var(--gold-light))',
    transition: 'width 0.6s ease', borderRadius: 1,
  },
  content: {
    flex: 1, maxWidth: 720, width: '100%', margin: '0 auto',
    padding: '32px 24px', display: 'flex', flexDirection: 'column',
    gap: 20, position: 'relative', zIndex: 1,
  },
  statusBar: {
    display: 'flex', alignItems: 'center', gap: 12,
    border: '1px solid', borderRadius: 14, padding: '14px 20px',
    transition: 'all 0.3s',
  },
  qLabel: {
    fontSize: 10, color: 'var(--gold)', fontWeight: 700,
    letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 10,
  },
  questionCard:  { padding: '28px 32px' },
  questionText:  { fontSize: 21, lineHeight: 1.65, color: 'var(--text)', fontWeight: 600, margin: 0 },
  transcriptCard:{ padding: '20px 24px' },
  transcriptText:{ fontSize: 15, lineHeight: 1.8, color: 'var(--text)', margin: 0 },
  controls: { display: 'flex', justifyContent: 'center' },
  submitBtn: { padding: '13px 40px', fontSize: 15 },
  warnBox: {
    fontSize: 12, color: 'var(--gold)', background: 'var(--gold-glow)',
    border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px', textAlign: 'center',
  },
  errorBox: {
    background: 'var(--red-glow)', border: '1px solid rgba(255,69,96,0.3)',
    borderRadius: 10, padding: '12px 16px', fontSize: 13, color: 'var(--red)', textAlign: 'center',
  },
  visualBox: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    padding: 28, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 20,
  },
  waveform: { display: 'flex', alignItems: 'center', gap: 5, height: 40 },
  waveBar:  { width: 5, borderRadius: 3, minHeight: 6 },
  fullscreen: {
    minHeight: '100vh', background: 'var(--bg)',
    display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', fontFamily: 'system-ui',
  },
  tipsRow: { display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' },
  tip: {
    fontSize: 12, color: 'var(--text-muted)', background: 'var(--surface)',
    border: '1px solid var(--border)', borderRadius: 20, padding: '6px 14px',
  },
};
