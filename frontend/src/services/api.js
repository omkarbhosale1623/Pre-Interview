/**
 * services/api.js — Centralised API client for Pre-Interview AI.
 */

const BASE_URL = '/api';

function getToken() {
  return localStorage.getItem('pia_token') || '';
}

async function request(method, path, { body, form, auth = true } = {}) {
  const headers = {};
  if (!form) headers['Content-Type'] = 'application/json';
  if (auth) {
    const tok = getToken();
    if (tok) headers['Authorization'] = `Bearer ${tok}`;
  }
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: form ? form : body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function recruiterSignup(email, password, full_name, company_name) {
  return request('POST', '/auth/signup', { body: { email, password, full_name, company_name }, auth: false });
}

export async function recruiterSignin(email, password) {
  return request('POST', '/auth/signin', { body: { email, password }, auth: false });
}

export async function recruiterSignout() {
  return request('POST', '/auth/signout');
}

export async function getMe() {
  return request('GET', '/auth/me');
}

// ── Question Banks ────────────────────────────────────────────────────────────

export async function uploadQuestionBank(file, bankName, role) {
  const form = new FormData();
  form.append('file', file);
  form.append('bank_name', bankName);
  if (role) form.append('role', role);
  return request('POST', '/questions/upload', { form });
}

export async function listBanks() {
  return request('GET', '/questions/banks');
}

// ── Speech helpers ───────────────────────────────────────────────────────────

export async function transcribeAudio(blob) {
  const form = new FormData();
  form.append('file', blob, 'speech.webm');
  // unauthenticated; the interview session token is sent separately if needed
  return request('POST', '/speech/transcribe', { form, auth: false });
}

export async function fetchTTS(text) {
  const form = new FormData();
  form.append('text', text);
  const res = await fetch(`${BASE_URL}/speech/tts`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText);
    throw new Error(err);
  }
  return res.blob();
}

export async function getBank(bankId) {
  return request('GET', `/questions/banks/${bankId}`);
}

// ── Sessions ──────────────────────────────────────────────────────────────────

export async function createSession(bankId, candidateName, candidateRole, candidateEmail, recruiterEmail) {
  return request('POST', '/interview/sessions', {
    body: { bank_id: bankId, candidate_name: candidateName, candidate_role: candidateRole, candidate_email: candidateEmail, recruiter_email: recruiterEmail },
  });
}

export async function startSession(sessionId) {
  return request('POST', `/interview/sessions/${sessionId}/start`);
}

export async function getNextQuestion(sessionId) {
  return request('GET', `/interview/sessions/${sessionId}/next`, { auth: false });
}

export async function submitAnswer(sessionId, questionId, transcript, durationS, wasSkipped = false) {
  return request('POST', `/interview/sessions/${sessionId}/answer`, {
    auth: false,
    body: {
      session_id: sessionId,
      question_id: questionId,
      answer_transcript: transcript,
      answer_duration_s: durationS,
      was_skipped: wasSkipped,
    },
  });
}

export async function completeSession(sessionId) {
  return request('POST', `/interview/sessions/${sessionId}/complete`, { auth: false });
}

export async function conversationStep(sessionId, transcript) {
  const body = { transcript: transcript !== undefined ? transcript : null };
  return request('POST', `/interview/sessions/${sessionId}/conversation`, {
    auth: false,
    body,
  });
}

// ── Evaluation ────────────────────────────────────────────────────────────────

export async function runEvaluation(sessionId) {
  return request('POST', `/evaluation/${sessionId}`, { auth: false });
}

export async function getEvaluation(sessionId) {
  return request('GET', `/evaluation/${sessionId}`, { auth: false });
}

// ── Report ────────────────────────────────────────────────────────────────────

export function textReportUrl(sessionId) {
  return `${BASE_URL}/report/${sessionId}/text`;
}

// ── Scheduling ────────────────────────────────────────────────────────────────

export async function scheduleInterview(payload) {
  return request('POST', '/schedule', { body: payload });
}

export async function joinInterview(token) {
  return request('GET', `/schedule/join/${token}`, { auth: false });
}

export async function listScheduled() {
  return request('GET', '/schedule/list');
}
