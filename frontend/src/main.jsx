import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

const style = document.createElement('style')
style.textContent = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:          #030712;
    --surface:     #080f1e;
    --surface2:    #0d1628;
    --surface3:    #111e35;
    --border:      rgba(180, 140, 55, 0.18);
    --border-med:  rgba(180, 140, 55, 0.35);
    --gold:        #c9a84c;
    --gold-light:  #e8c96a;
    --gold-glow:   rgba(201, 168, 76, 0.12);
    --gold-glow2:  rgba(201, 168, 76, 0.06);
    --text:        #eef1f8;
    --text-muted:  #6b7a99;
    --text-dim:    #3a4a66;
    --green:       #00c896;
    --green-glow:  rgba(0, 200, 150, 0.12);
    --red:         #ff4560;
    --red-glow:    rgba(255, 69, 96, 0.12);
    --blue:        #4a90e2;
  }

  body { background: var(--bg); color: var(--text); }
  input, select, textarea, button { font-family: inherit; }
  input:focus, select:focus, textarea:focus { outline: none; }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--surface); }
  ::-webkit-scrollbar-thumb { background: var(--border-med); border-radius: 3px; }

  /* ── Animations ── */
  @keyframes pulse-ring {
    0% { transform: scale(1); opacity: 0.8; }
    50% { transform: scale(1.12); opacity: 0.3; }
    100% { transform: scale(1); opacity: 0.8; }
  }
  @keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
  @keyframes fade-in {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes slide-up {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes shimmer {
    0%   { background-position: -200% center; }
    100% { background-position: 200% center; }
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  @keyframes countdown {
    from { stroke-dashoffset: 0; }
    to   { stroke-dashoffset: 283; }
  }
  @keyframes wave {
    0%, 100% { height: 6px; }
    50%       { height: 28px; }
  }
  @keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 20px rgba(201,168,76,0.2); }
    50%       { box-shadow: 0 0 40px rgba(201,168,76,0.5); }
  }

  .animate-fade-in { animation: fade-in 0.4s ease forwards; }
  .animate-slide-up { animation: slide-up 0.5s ease forwards; }
  .pulse-ring { animation: pulse-ring 2s ease-in-out infinite; }
  .pulse-dot { animation: pulse-dot 1.5s ease-in-out infinite; }
  .spin { animation: spin 1s linear infinite; }
  .glow-gold { animation: glow-pulse 2s ease-in-out infinite; }

  /* ── Waveform bars ── */
  .wave-bar { animation: wave 1.2s ease-in-out infinite; }
  .wave-bar:nth-child(1) { animation-delay: 0s; }
  .wave-bar:nth-child(2) { animation-delay: 0.1s; }
  .wave-bar:nth-child(3) { animation-delay: 0.2s; }
  .wave-bar:nth-child(4) { animation-delay: 0.3s; }
  .wave-bar:nth-child(5) { animation-delay: 0.4s; }
  .wave-bar:nth-child(6) { animation-delay: 0.3s; }
  .wave-bar:nth-child(7) { animation-delay: 0.2s; }
  .wave-bar:nth-child(8) { animation-delay: 0.1s; }
  .wave-bar:nth-child(9) { animation-delay: 0s; }

  /* ── Buttons ── */

  /* ── Light theme overrides ── */
  body[data-theme="light"] {
    --bg:          #f5f5f5;
    --surface:     #ffffff;
    --surface2:    #ececec;
    --surface3:    #e0e0e0;
    --border:      rgba(100,100,100,0.18);
    --border-med:  rgba(100,100,100,0.35);
    --gold:        #c9a84c;
    --gold-light:  #e8c96a;
    --gold-glow:   rgba(201, 168, 76, 0.12);
    --gold-glow2:  rgba(201, 168, 76, 0.06);
    --text:        #111111;
    --text-muted:  #555555;
    --text-dim:    #888888;
    --green:       #00c896;
    --green-glow:  rgba(0, 200, 150, 0.12);
    --red:         #ff4560;
    --red-glow:    rgba(255, 69, 96, 0.12);
    --blue:        #4a90e2;
  }

  /* ── Buttons ── */
  .btn-gold {
    background: linear-gradient(135deg, #c9a84c 0%, #e8c96a 50%, #c9a84c 100%);
    background-size: 200% auto;
    color: #000;
    border: none;
    cursor: pointer;
    font-weight: 800;
    transition: background-position 0.4s, transform 0.2s, box-shadow 0.2s;
    border-radius: 12px;
  }
  .btn-gold:hover {
    background-position: right center;
    box-shadow: 0 8px 24px rgba(201,168,76,0.35);
    transform: translateY(-1px);
  }
  .btn-gold:active { transform: translateY(0); }
  .btn-ghost {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-muted);
    cursor: pointer;
    font-weight: 600;
    transition: all 0.2s;
    border-radius: 12px;
  }
  .btn-ghost:hover {
    border-color: var(--border-med);
    color: var(--text);
    background: var(--gold-glow2);
  }

  /* theme toggle control in the corner */
  .theme-toggle-btn {
    background: transparent;
    border: none;
    font-size: 20px;
    cursor: pointer;
    padding: 6px;
    line-height: 1;
  }

  /* ── Input ── */
  .input-dark {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 16px;
    color: var(--text);
    font-size: 14px;
    width: 100%;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .input-dark:focus {
    border-color: var(--gold);
    box-shadow: 0 0 0 3px var(--gold-glow);
  }
  .input-dark::placeholder { color: var(--text-dim); }

  /* ── Card ── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
  }
  .card-glow {
    background: var(--surface);
    border: 1px solid var(--border-med);
    border-radius: 20px;
    box-shadow: 0 0 40px var(--gold-glow2), inset 0 1px 0 rgba(255,255,255,0.04);
  }

  /* ── Label ── */
  .label {
    font-size: 11px;
    font-weight: 700;
    color: var(--gold);
    letter-spacing: 2px;
    text-transform: uppercase;
  }

  /* ── Gold gradient text ── */
  .gold-text {
    background: linear-gradient(135deg, #c9a84c, #e8c96a, #c9a84c);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
`
document.head.appendChild(style)

createRoot(document.getElementById('root')).render(
  <StrictMode><App /></StrictMode>
)
