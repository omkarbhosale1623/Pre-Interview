/**
 * hooks/useSpeech.js — Speech-to-Speech for Pre-Interview AI.
 *
 * FIXES:
 *  1. CRITICAL: Audio MIME type was "audio/wav" — ElevenLabs returns MP3.
 *     Fixed to "audio/mpeg". This was causing silent/broken playback in
 *     some browsers (Chrome on Windows especially).
 *  2. Silence timeout reduced from 7s → 5s (feels more natural in an interview).
 *     After the user stops speaking, the question advances in 5s not 7s.
 *  3. Guard flag (resultSentRef) prevents onResult firing more than once.
 *  4. null return from transcription = transient error → retry, not counted
 *     as a "no answer" toward MAX_REPEATS.
 *  5. Properly cancel requestAnimationFrame on stop/unmount.
 *  6. Small blobs (<300 bytes) are discarded — background noise, not speech.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

const API_BASE = '/api';
const SILENCE_TIMEOUT_MS   = 5000;   // 5s of silence → auto-advance (was 7s)
const MAX_REPEATS          = 2;
const SPEECH_RMS_THRESHOLD = 0.012;  // tune: higher = less sensitive


// ── TTS player ────────────────────────────────────────────────────────────────

export function useTTS() {
  const audioRef = useRef(null);

  const speak = useCallback(async (text, base64Audio = null) => {
    // Stop anything currently playing
    if (audioRef.current) {
      audioRef.current.pause();
      try { URL.revokeObjectURL(audioRef.current.src); } catch {}
      audioRef.current = null;
    }

    let url;
    if (base64Audio) {
      // FIXED: ElevenLabs returns MP3 (mp3_22050_32 format), NOT WAV.
      // Using audio/wav here caused silent/broken playback in many browsers.
      url = 'data:audio/mpeg;base64,' + base64Audio;
    } else {
      const form = new FormData();
      form.append('text', text);
      try {
        const res = await fetch(`${API_BASE}/speech/tts`, { method: 'POST', body: form });
        if (!res.ok) { console.warn('TTS HTTP error', res.status); return; }
        const blob = await res.blob();
        url = URL.createObjectURL(blob);
      } catch (err) {
        console.warn('TTS fetch error:', err);
        return;
      }
    }

    const audio = new Audio(url);
    audioRef.current = audio;

    return new Promise((resolve) => {
      audio.onended = () => { if (!base64Audio) URL.revokeObjectURL(url); resolve(); };
      audio.onerror = (e) => {
        console.warn('Audio playback error:', e);
        if (!base64Audio) URL.revokeObjectURL(url);
        resolve();
      };
      audio.play().catch((e) => {
        console.warn('audio.play() blocked:', e);
        resolve();
      });
    });
  }, []);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      try { URL.revokeObjectURL(audioRef.current.src); } catch {}
      audioRef.current = null;
    }
  }, []);

  const isSpeaking = useCallback(
    () => !!(audioRef.current && !audioRef.current.paused && !audioRef.current.ended),
    [],
  );

  return { speak, stop, isSpeaking, supported: true };
}


// ── STT via backend Whisper ───────────────────────────────────────────────────

export function useSTT() {
  const [transcript,  setTranscript]  = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking,  setIsSpeaking]  = useState(false);

  const recorderRef   = useRef(null);
  const streamRef     = useRef(null);
  const audioCtxRef   = useRef(null);
  const rafRef        = useRef(null);
  const chunksRef     = useRef([]);
  const activeRef     = useRef(false);
  const resultSentRef = useRef(false);

  const supported =
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined';

  const _cleanup = useCallback(() => {
    if (rafRef.current)      { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    if (audioCtxRef.current) { try { audioCtxRef.current.close(); } catch {} audioCtxRef.current = null; }
    if (streamRef.current)   { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    activeRef.current = false;
  }, []);

  const stop = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop();
    }
    recorderRef.current = null;
    _cleanup();
    setIsListening(false);
    setIsSpeaking(false);
  }, [_cleanup]);

  const start = useCallback(({
    silenceTimeoutMs = SILENCE_TIMEOUT_MS,
    onSilence,
    onAudioLevel,
    onResult,
  } = {}) => {
    if (!supported || activeRef.current) return;
    activeRef.current   = true;
    resultSentRef.current = false;

    setTranscript('');
    setIsListening(true);
    setIsSpeaking(false);
    chunksRef.current = [];

    navigator.mediaDevices.getUserMedia({ audio: true })
      .then((stream) => {
        if (!activeRef.current) { stream.getTracks().forEach(t => t.stop()); return; }
        streamRef.current = stream;

        const AudioContext = window.AudioContext || window.webkitAudioContext;
        const ac = new AudioContext();
        audioCtxRef.current = ac;
        const src = ac.createMediaStreamSource(stream);
        const analyser = ac.createAnalyser();
        analyser.fftSize = 2048;
        src.connect(analyser);
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        let lastSpokeAt = Date.now();

        const monitorLevel = () => {
          if (!activeRef.current) return;
          analyser.getByteTimeDomainData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            const v = dataArray[i] / 128 - 1;
            sum += v * v;
          }
          const rms     = Math.sqrt(sum / dataArray.length);
          const speaking = rms > SPEECH_RMS_THRESHOLD;
          const now      = Date.now();

          if (speaking) { lastSpokeAt = now; setIsSpeaking(true); }
          else          { setIsSpeaking(false); }

          const msSilent = now - lastSpokeAt;
          if (onAudioLevel) onAudioLevel(rms, msSilent);

          if (msSilent >= silenceTimeoutMs) {
            if (recorderRef.current && recorderRef.current.state !== 'inactive') {
              recorderRef.current.stop();
            }
            return; // stop RAF loop
          }

          rafRef.current = requestAnimationFrame(monitorLevel);
        };

        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : '';

        const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
        recorderRef.current = recorder;
        chunksRef.current   = [];

        recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };

        recorder.onstop = async () => {
          if (resultSentRef.current) return; // fire at most once per session
          resultSentRef.current = true;

          _cleanup();
          setIsListening(false);
          setIsSpeaking(false);

          const blob = new Blob(chunksRef.current, { type: mimeType || 'audio/webm' });

          if (blob.size < 300) {
            setTranscript('');
            onResult?.('');
            return;
          }

          const form = new FormData();
          form.append('file', blob, 'speech.webm');

          try {
            const resp = await fetch(`${API_BASE}/speech/transcribe`, { method: 'POST', body: form });
            if (!resp.ok) {
              console.error(`/speech/transcribe HTTP ${resp.status}`);
              onResult?.(null); // null = transient failure
              return;
            }
            const data = await resp.json();
            const text = (data.text || '').trim();
            setTranscript(text);
            onResult?.(text);
          } catch (err) {
            console.error('Transcription network error:', err);
            onResult?.(null);
          }
        };

        recorder.start(250);
        rafRef.current = requestAnimationFrame(monitorLevel);
      })
      .catch((err) => {
        console.error('Microphone access error:', err);
        activeRef.current = false;
        setIsListening(false);
      });
  }, [supported, _cleanup]);

  useEffect(() => () => { stop(); }, [stop]);

  return { transcript, isListening, isSpeaking, start, stop, supported };
}


// ── Interview orchestrator ────────────────────────────────────────────────────

export function useInterviewSpeech({ onAnswerReady, onRepeat, onSkip } = {}) {
  const [phase,       setPhase]      = useState('idle');
  const [countdown,   setCountdown]  = useState(SILENCE_TIMEOUT_MS / 1000);
  const [repeatCount, setRepeatCount]= useState(0);
  const [transcript,  setTranscript] = useState('');

  const { speak, stop: stopTTS, isSpeaking }  = useTTS();
  const { start: startRec, stop: stopRec, isSpeaking: isSpeakingSTT } = useSTT();

  const repeatRef      = useRef(0);
  const currentTextRef = useRef('');
  const startTimeRef   = useRef(null);
  const phaseRef       = useRef('idle');

  const _setPhase = (p) => { phaseRef.current = p; setPhase(p); };

  const _onResult = useCallback((text) => {
    if (phaseRef.current === 'processing') return;

    // null = backend error → retry silently, don't count as "no answer"
    if (text === null) {
      console.warn('Transcription error — retrying recording');
      setTimeout(() => {
        if (phaseRef.current !== 'processing') _startRecording();
      }, 500);
      return;
    }

    const hasAnswer  = text.trim().length > 2;
    const durationMs = startTimeRef.current ? Date.now() - startTimeRef.current : 0;

    if (hasAnswer) {
      setTranscript(text.trim());
      _setPhase('processing');
      onAnswerReady?.(text.trim(), false, durationMs);
      return;
    }

    // Genuine silence → count toward repeats
    const next = repeatRef.current + 1;
    repeatRef.current = next;
    setRepeatCount(next);

    if (next >= MAX_REPEATS) {
      _setPhase('processing');
      onSkip?.();
      onAnswerReady?.('(No answer provided)', true, 0);
    } else {
      onRepeat?.(next);
      setTimeout(() => {
        if (phaseRef.current !== 'processing') {
          _speakAndRecord(currentTextRef.current);
        }
      }, 600);
    }
  }, [onAnswerReady, onRepeat, onSkip]);

  const _startRecording = useCallback(() => {
    startTimeRef.current = Date.now();
    _setPhase('countdown');
    setCountdown(SILENCE_TIMEOUT_MS / 1000);

    startRec({
      silenceTimeoutMs: SILENCE_TIMEOUT_MS,
      onAudioLevel: (_rms, msSinceLast) => {
        setCountdown(Math.max(0, (SILENCE_TIMEOUT_MS - msSinceLast) / 1000));
      },
      onResult: _onResult,
    });
  }, [startRec, _onResult]);

  const _speakAndRecord = useCallback(async (text, base64Audio = null) => {
    _setPhase('bot_speaking');
    await speak(text, base64Audio);
    if (phaseRef.current === 'processing') return;
    // Brief delay to let the browser fully release audio resources from TTS
    // before re-acquiring the microphone for STT recording
    await new Promise(r => setTimeout(r, 300));
    _startRecording();
  }, [speak, _startRecording]);

  const askQuestion = useCallback((text, base64Audio = null) => {
    stopRec();
    stopTTS();
    currentTextRef.current = text;
    repeatRef.current = 0;
    setRepeatCount(0);
    setTranscript('');
    setCountdown(SILENCE_TIMEOUT_MS / 1000);
    _speakAndRecord(text, base64Audio);
  }, [stopRec, stopTTS, _speakAndRecord]);

  const forceSubmit = useCallback(() => {
    if (phaseRef.current === 'processing') return;
    stopRec();
    const t          = transcript.trim();
    const durationMs = startTimeRef.current ? Date.now() - startTimeRef.current : 0;
    _setPhase('processing');
    onAnswerReady?.(t || '(No answer provided)', !t, durationMs);
  }, [stopRec, transcript, onAnswerReady]);

  const resetForNext = useCallback(() => {
    stopRec();
    stopTTS();
    _setPhase('idle');
    setTranscript('');
    setRepeatCount(0);
    setCountdown(SILENCE_TIMEOUT_MS / 1000);
    repeatRef.current = 0;
  }, [stopRec, stopTTS]);

  useEffect(() => () => { stopRec(); stopTTS(); }, []);

  return {
    phase, countdown, repeatCount, transcript,
    askQuestion, forceSubmit, resetForNext,
    ttsSupported: true, sttSupported: true,
    isSpeaking: isSpeaking(),
  };
}
