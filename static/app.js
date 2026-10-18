/**
 * app.js — Aria AI Enterprise Voice Console
 * Features:
 * - Bespoke Dark Blue Theme logic
 * - Strict Language to Model Mapping:
 *     • English -> ElevenLabs (Adam)
 *     • Hinglish -> Sarvam.ai (Ashutosh)
 *     • Marathi -> Sarvam.ai (Ashutosh)
 *     • Automatic Edge-TTS Fallback on credit limit
 * - Hands-Free Live Mode (Continuous VAD) & Push-to-Talk Mode
 * - Complete removal of confusing badges
 */

// ── State Variables ──────────────────────────────────────────
const API_BASE = window.location.origin;
const SESSION_ID = `session_${Date.now()}`;

let activeLanguage = 'en';         // 'en', 'hi', 'mr'
let interactionMode = 'live';      // 'live' (hands-free) or 'push' (manual)
let isLiveActive = false;          // Is hands-free running
let isLivePaused = false;          // Is hands-free temporarily paused by user
let isRecording = false;           // Push-to-talk recording state
let isProcessing = false;          // Pipeline in flight
let isUserSpeaking = false;        // VAD speech detected
let isAgentSpeaking = false;       // Aria audio playback in progress

let currentAudio = null;
let audioStream = null;
let mediaRecorder = null;
let audioChunks = [];

// Web Audio & VAD
let audioCtx = null;
let analyser = null;
let vadAnimationFrameId = null;
let silenceTimer = null;
let speechStartTime = 0;
const VAD_SILENCE_TIMEOUT_MS = 1000;  // 1.0s silence = turn complete
const VAD_SPEECH_THRESHOLD = 0.026;   // RMS sensitivity
const VAD_MIN_SPEECH_MS = 450;        // Minimum speech duration to prevent click false-triggers

// Waveform
let waveformCanvas = null;
let wCtx = null;
let waveformAnimationId = null;

// ── DOM References ───────────────────────────────────────────
const cardLangEn        = document.getElementById('cardLangEn');
const cardLangHi        = document.getElementById('cardLangHi');
const cardLangMr        = document.getElementById('cardLangMr');

const btnModeLive       = document.getElementById('btnModeLive');
const btnModePush       = document.getElementById('btnModePush');

const activeEngineDisplay  = document.getElementById('activeEngineDisplay');
const activeLanguageDisplay = document.getElementById('activeLanguageDisplay');
const activeModelDisplay   = document.getElementById('activeModelDisplay');

const stageModeName     = document.getElementById('stageModeName');
const stageEngineName   = document.getElementById('stageEngineName');
const currentModeBadge  = document.getElementById('currentModeBadge');
const liveControlsBar   = document.getElementById('liveControlsBar');
const interruptBtn      = document.getElementById('interruptBtn');
const pauseLiveBtn      = document.getElementById('pauseLiveBtn');
const pauseLiveBtnText  = document.getElementById('pauseLiveBtnText');

const ambientOrb        = document.getElementById('ambientOrb');
const orbStatusTitle    = document.getElementById('orbStatusTitle');
const orbStatusSubtitle = document.getElementById('orbStatusSubtitle');

const chatContainer     = document.getElementById('chatContainer');
const welcomeMsg        = document.getElementById('welcomeMsg');

const micBtn            = document.getElementById('micBtn');
const micIcon           = document.getElementById('micIcon');
const stopIcon          = document.getElementById('stopIcon');
const dockHintText      = document.getElementById('dockHintText');

const textInput         = document.getElementById('textInput');
const sendBtn           = document.getElementById('sendBtn');
const processingOverlay = document.getElementById('processingOverlay');
const processingText    = document.getElementById('processingText');

const agentStatusText   = document.getElementById('agentStatusText');

// ── Particle Canvas (Deep Blue Ambient) ───────────────────────
const pCanvas = document.getElementById('particleCanvas');
const pCtx = pCanvas.getContext('2d');
let particles = [];

function resizeParticles() {
  pCanvas.width = window.innerWidth;
  pCanvas.height = window.innerHeight;
}

function initParticles() {
  resizeParticles();
  particles = Array.from({ length: 65 }, () => ({
    x: Math.random() * pCanvas.width,
    y: Math.random() * pCanvas.height,
    r: Math.random() * 1.5 + 0.5,
    dx: (Math.random() - 0.5) * 0.25,
    dy: (Math.random() - 0.5) * 0.25,
    opacity: Math.random() * 0.35 + 0.08
  }));
}

function animateParticles() {
  pCtx.clearRect(0, 0, pCanvas.width, pCanvas.height);
  particles.forEach(p => {
    p.x += p.dx;
    p.y += p.dy;
    if (p.x < 0 || p.x > pCanvas.width) p.dx *= -1;
    if (p.y < 0 || p.y > pCanvas.height) p.dy *= -1;

    pCtx.beginPath();
    pCtx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    pCtx.fillStyle = `rgba(56, 189, 248, ${p.opacity})`;
    pCtx.fill();
  });
  requestAnimationFrame(animateParticles);
}

window.addEventListener('resize', resizeParticles);
initParticles();
animateParticles();

// ── Audio Context Helper ─────────────────────────────────────
function getAudioContext() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function getAudioMimeType() {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
  return types.find(t => MediaRecorder.isTypeSupported(t)) || 'audio/webm';
}

// ── Waveform Spectrum ────────────────────────────────────────
function setupWaveform(sourceNode) {
  waveformCanvas = document.getElementById('waveformCanvas');
  wCtx = waveformCanvas.getContext('2d');

  if (!analyser) {
    const ctx = getAudioContext();
    analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.65;
  }
  sourceNode.connect(analyser);
  drawWaveform();
}

function drawWaveform() {
  if (!analyser || !waveformCanvas) return;

  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  analyser.getByteFrequencyData(dataArray);

  const W = waveformCanvas.width = waveformCanvas.offsetWidth || 650;
  const H = waveformCanvas.height = 54;

  wCtx.clearRect(0, 0, W, H);

  const barWidth = (W / bufferLength) * 2.2;
  let x = 0;

  for (let i = 0; i < bufferLength; i++) {
    const v = dataArray[i] / 255;
    const barHeight = Math.max(3, v * H);

    const gradient = wCtx.createLinearGradient(0, H, 0, H - barHeight);
    if (isAgentSpeaking) {
      gradient.addColorStop(0, 'rgba(56, 189, 248, 0.75)');
      gradient.addColorStop(1, 'rgba(129, 140, 248, 0.95)');
    } else {
      gradient.addColorStop(0, 'rgba(37, 99, 235, 0.7)');
      gradient.addColorStop(1, 'rgba(56, 189, 248, 0.9)');
    }

    wCtx.fillStyle = gradient;
    wCtx.beginPath();
    wCtx.roundRect(x, H - barHeight, barWidth - 1.5, barHeight, 2);
    wCtx.fill();
    x += barWidth + 1;
  }

  waveformAnimationId = requestAnimationFrame(drawWaveform);
}

function stopWaveform() {
  if (waveformAnimationId) cancelAnimationFrame(waveformAnimationId);
  if (waveformCanvas && wCtx) {
    wCtx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);
  }
}

// ═════════════════════════════════════════════════════════════
// 1. LANGUAGE & MODEL BINDING LOGIC
// ═════════════════════════════════════════════════════════════

function selectLanguage(langCode) {
  activeLanguage = langCode;

  // Update card UI
  cardLangEn.classList.toggle('active', langCode === 'en');
  cardLangHi.classList.toggle('active', langCode === 'hi');
  cardLangMr.classList.toggle('active', langCode === 'mr');

  // Update Telemetry & Badges
  if (langCode === 'en') {
    activeEngineDisplay.textContent = 'ElevenLabs (George)';
    activeLanguageDisplay.textContent = 'English (Locked)';
    stageEngineName.textContent = 'Voice: ElevenLabs (George)';
    textInput.placeholder = 'Type in English to test ElevenLabs voice...';
  } else if (langCode === 'hi') {
    activeEngineDisplay.textContent = 'Sarvam.ai (Ashutosh)';
    activeLanguageDisplay.textContent = 'Hinglish (Locked)';
    stageEngineName.textContent = 'Voice: Sarvam.ai (Ashutosh)';
    textInput.placeholder = 'Type in Hinglish to test Sarvam.ai voice...';
  } else if (langCode === 'mr') {
    activeEngineDisplay.textContent = 'Sarvam.ai (Ashutosh)';
    activeLanguageDisplay.textContent = 'मराठी (Locked)';
    stageEngineName.textContent = 'Voice: Sarvam.ai (Ashutosh)';
    textInput.placeholder = 'मराठीत टाइप करा (Sarvam.ai आवाज चाचणी)...';
  }

  showToast(`Language set to ${langCode.toUpperCase()} (${activeEngineDisplay.textContent})`);
}

// ═════════════════════════════════════════════════════════════
// 2. INTERACTION MODE (Hands-Free Live vs Push-to-Talk)
// ═════════════════════════════════════════════════════════════

function setInteractionMode(mode) {
  interactionMode = mode;

  btnModeLive.classList.toggle('active', mode === 'live');
  btnModePush.classList.toggle('active', mode === 'push');

  if (mode === 'live') {
    stageModeName.textContent = 'Hands-Free Live';
    dockHintText.textContent = 'Hands-Free Active';
    liveControlsBar.classList.remove('hidden');
    micBtn.classList.remove('active-recording');
    startHandsFreeSession();
  } else {
    stageModeName.textContent = 'Push-to-Talk';
    dockHintText.textContent = 'Click mic to talk';
    liveControlsBar.classList.add('hidden');
    stopHandsFreeSession();
    setOrbState('idle', 'Push-to-Talk Mode', 'Click the microphone button below to speak');
  }
}

// ═════════════════════════════════════════════════════════════
// 3. HANDS-FREE CONTINUOUS LIVE LOGIC
// ═════════════════════════════════════════════════════════════

async function startHandsFreeSession() {
  try {
    const ctx = getAudioContext();
    if (ctx.state === 'suspended') await ctx.resume();

    // Get microphone with hardware echo cancellation
    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      },
      video: false
    });

    isLiveActive = true;
    isLivePaused = false;
    pauseLiveBtnText.textContent = 'Pause Live';
    pauseLiveBtn.classList.remove('resume');

    setOrbState('listening', 'Listening... Speak naturally', 'Pause for ~1s when finished; Aria will reply automatically');
    agentStatusText.textContent = 'Live Listening...';

    // Hook to visualizer & VAD
    const source = ctx.createMediaStreamSource(audioStream);
    setupWaveform(source);

    // Start recorder slice
    startLiveRecorderSlice();

    // Start VAD Loop
    startVADLoop();

  } catch (err) {
    console.error('Failed to start hands-free mic:', err);
    showToast('⚠️ Microphone permission required for Hands-Free mode.');
    setInteractionMode('push');
  }
}

function stopHandsFreeSession() {
  isLiveActive = false;
  isUserSpeaking = false;
  isAgentSpeaking = false;

  if (silenceTimer) {
    clearTimeout(silenceTimer);
    silenceTimer = null;
  }

  if (vadAnimationFrameId) {
    cancelAnimationFrame(vadAnimationFrameId);
    vadAnimationFrameId = null;
  }

  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    try { mediaRecorder.stop(); } catch (e) {}
  }

  if (audioStream) {
    audioStream.getTracks().forEach(t => t.stop());
    audioStream = null;
  }

  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }

  stopWaveform();
}

function toggleHandsFreePause() {
  if (!isLiveActive) {
    startHandsFreeSession();
    return;
  }

  isLivePaused = !isLivePaused;

  if (isLivePaused) {
    pauseLiveBtnText.textContent = 'Resume Live';
    pauseLiveBtn.classList.add('resume');
    setOrbState('idle', 'Live Mode Paused', 'Click Resume Live to start speaking again');
    agentStatusText.textContent = 'Live Paused';
    if (currentAudio) {
      currentAudio.pause();
    }
  } else {
    pauseLiveBtnText.textContent = 'Pause Live';
    pauseLiveBtn.classList.remove('resume');
    resumeLiveListening();
  }
}

function startLiveRecorderSlice() {
  if (!isLiveActive || !audioStream) return;

  audioChunks = [];
  try {
    mediaRecorder = new MediaRecorder(audioStream, { mimeType: getAudioMimeType() });
    mediaRecorder.ondataavailable = e => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.start(100);
  } catch (err) {
    console.error('Error starting live slice:', err);
  }
}

function startVADLoop() {
  if (!analyser) return;

  const bufferLength = analyser.fftSize;
  const timeData = new Float32Array(bufferLength);

  function checkVolume() {
    if (!isLiveActive || isLivePaused) return;

    // Do NOT capture microphone while Aria is speaking (prevents echo loop)
    if (isAgentSpeaking || isProcessing) {
      vadAnimationFrameId = requestAnimationFrame(checkVolume);
      return;
    }

    analyser.getFloatTimeDomainData(timeData);

    // Compute RMS Energy
    let sum = 0;
    for (let i = 0; i < bufferLength; i++) {
      sum += timeData[i] * timeData[i];
    }
    const rms = Math.sqrt(sum / bufferLength);

    if (rms > VAD_SPEECH_THRESHOLD) {
      // User is actively speaking
      if (!isUserSpeaking) {
        isUserSpeaking = true;
        speechStartTime = Date.now();
        setOrbState('hearing', 'Listening to you...', 'Voice energy detected...');
      }

      // Reset silence timer on any word/sound
      if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
      }
    } else {
      // Below threshold (silence)
      if (isUserSpeaking) {
        if (!silenceTimer) {
          silenceTimer = setTimeout(() => {
            onSilenceComplete();
          }, VAD_SILENCE_TIMEOUT_MS);
        }
      }
    }

    vadAnimationFrameId = requestAnimationFrame(checkVolume);
  }

  vadAnimationFrameId = requestAnimationFrame(checkVolume);
}

function onSilenceComplete() {
  silenceTimer = null;
  const duration = Date.now() - speechStartTime;

  // Ignore tiny accidental sounds
  if (duration < VAD_MIN_SPEECH_MS) {
    isUserSpeaking = false;
    setOrbState('listening', 'Listening... Speak naturally', 'Pause for ~1s when finished');
    return;
  }

  isUserSpeaking = false;
  isProcessing = true;

  setOrbState('thinking', 'Aria is thinking...', `Generating response via ${activeEngineDisplay.textContent}...`);
  agentStatusText.textContent = 'Thinking...';

  // Stop recorder slice and send
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
      sendVoiceAudio(blob);
    };
    mediaRecorder.stop();
  }
}

async function sendVoiceAudio(audioBlob) {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'speech.webm');
  formData.append('session_id', SESSION_ID);
  formData.append('language', activeLanguage); // Send locked language

  try {
    const response = await fetch(`${API_BASE}/api/chat/voice`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    isProcessing = false;

    if (data.error) {
      if (data.transcription === '') {
        console.warn('VAD: Empty transcription');
      } else {
        showToast(data.error);
      }
      if (interactionMode === 'live') resumeLiveListening();
      return;
    }

    hideWelcome();

    // Render Chat Bubbles
    if (data.transcription) {
      addMessage('user', data.transcription, activeLanguage);
    }
    addMessage('assistant', data.response_text, activeLanguage, data.provider);

    // Play Voice
    if (data.audio_base64) {
      playAudioResponse(data.audio_base64, () => {
        if (interactionMode === 'live') {
          setTimeout(resumeLiveListening, 300);
        }
      });
    } else {
      if (interactionMode === 'live') resumeLiveListening();
    }

  } catch (err) {
    console.error('Voice pipeline error:', err);
    isProcessing = false;
    showToast('Connection error to server.');
    if (interactionMode === 'live') resumeLiveListening();
  }
}

function resumeLiveListening() {
  if (!isLiveActive || isLivePaused) return;

  isAgentSpeaking = false;
  isUserSpeaking = false;
  isProcessing = false;

  setOrbState('listening', 'Listening... Speak naturally', 'Pause for ~1s when finished; Aria will reply automatically');
  agentStatusText.textContent = 'Live Listening...';
  interruptBtn.classList.add('hidden');

  startLiveRecorderSlice();
}

function interruptAgent() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  isAgentSpeaking = false;
  interruptBtn.classList.add('hidden');
  resumeLiveListening();
}

// ═════════════════════════════════════════════════════════════
// 4. PUSH-TO-TALK MODE (Manual)
// ═════════════════════════════════════════════════════════════

function handleMicButtonClick() {
  if (interactionMode === 'live') {
    // In live mode, tapping mic toggles pause/resume
    toggleHandsFreePause();
  } else {
    togglePushRecording();
  }
}

async function togglePushRecording() {
  if (isProcessing) return;
  if (isRecording) {
    stopPushRecording();
  } else {
    await startPushRecording();
  }
}

async function startPushRecording() {
  try {
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    mediaRecorder = new MediaRecorder(audioStream, { mimeType: getAudioMimeType() });
    audioChunks = [];

    mediaRecorder.ondataavailable = e => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
      processManualAudio(blob);
    };

    mediaRecorder.start(100);
    isRecording = true;

    const ctx = getAudioContext();
    const source = ctx.createMediaStreamSource(audioStream);
    setupWaveform(source);

    micBtn.classList.add('active-recording');
    micIcon.classList.add('hidden');
    stopIcon.classList.remove('hidden');
    dockHintText.textContent = 'Recording (Tap to send)';
    setOrbState('hearing', 'Recording speech...', 'Tap mic again to send');
    agentStatusText.textContent = 'Recording...';

  } catch (err) {
    console.error('Mic error:', err);
    showToast('Microphone access denied.');
  }
}

function stopPushRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    audioStream.getTracks().forEach(t => t.stop());
    isRecording = false;
    stopWaveform();

    micBtn.classList.remove('active-recording');
    micIcon.classList.remove('hidden');
    stopIcon.classList.add('hidden');
    dockHintText.textContent = 'Processing...';
    setOrbState('thinking', 'Aria is thinking...', `Synthesizing via ${activeEngineDisplay.textContent}...`);
    agentStatusText.textContent = 'Thinking...';
  }
}

async function processManualAudio(audioBlob) {
  showProcessing('Processing speech...');

  const formData = new FormData();
  formData.append('audio', audioBlob, 'speech.webm');
  formData.append('session_id', SESSION_ID);
  formData.append('language', activeLanguage);

  try {
    const response = await fetch(`${API_BASE}/api/chat/voice`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    hideProcessing();
    dockHintText.textContent = 'Click mic to talk';

    if (data.error) {
      showToast(data.error);
      setOrbState('idle', 'Push-to-Talk Mode', 'Click the microphone button below to speak');
      agentStatusText.textContent = 'Ready';
      return;
    }

    hideWelcome();

    if (data.transcription) {
      addMessage('user', data.transcription, activeLanguage);
    }
    addMessage('assistant', data.response_text, activeLanguage, data.provider);

    if (data.audio_base64) {
      playAudioResponse(data.audio_base64, () => {
        setOrbState('idle', 'Push-to-Talk Mode', 'Click the microphone button below to speak');
        agentStatusText.textContent = 'Ready';
      });
    } else {
      setOrbState('idle', 'Push-to-Talk Mode', 'Click the microphone button below to speak');
      agentStatusText.textContent = 'Ready';
    }

  } catch (err) {
    hideProcessing();
    dockHintText.textContent = 'Click mic to talk';
    showToast('Connection error to server.');
    setOrbState('idle', 'Push-to-Talk Mode', 'Click the microphone button below to speak');
    agentStatusText.textContent = 'Ready';
  }
}

// ═════════════════════════════════════════════════════════════
// 5. TEXT CHAT WITH VOICE PLAYBACK
// ═════════════════════════════════════════════════════════════

async function sendTextMessage(overrideText) {
  const message = overrideText || textInput.value.trim();
  if (!message || isProcessing) return;

  textInput.value = '';
  autoResizeTextarea(textInput);
  sendBtn.disabled = true;
  isProcessing = true;

  hideWelcome();
  addMessage('user', message, activeLanguage);

  const typingId = addTypingIndicator();
  setOrbState('thinking', 'Aria is thinking...', `Generating via ${activeEngineDisplay.textContent}...`);

  try {
    const response = await fetch(`${API_BASE}/api/chat/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: SESSION_ID,
        language: activeLanguage
      })
    });

    const data = await response.json();
    removeTypingIndicator(typingId);
    isProcessing = false;
    sendBtn.disabled = false;

    if (data.error) {
      showToast(data.error);
      if (interactionMode === 'live') resumeLiveListening();
      return;
    }

    addMessage('assistant', data.response_text, activeLanguage, data.provider);

    if (data.audio_base64) {
      playAudioResponse(data.audio_base64, () => {
        if (interactionMode === 'live') {
          setTimeout(resumeLiveListening, 300);
        } else {
          setOrbState('idle', 'Push-to-Talk Mode', 'Click the microphone button below to speak');
        }
      });
    } else {
      if (interactionMode === 'live') resumeLiveListening();
    }

  } catch (err) {
    removeTypingIndicator(typingId);
    isProcessing = false;
    sendBtn.disabled = false;
    showToast('Connection error.');
    if (interactionMode === 'live') resumeLiveListening();
  }
}

function handlePresetClick(text, lang) {
  selectLanguage(lang);
  sendTextMessage(text);
}

// ═════════════════════════════════════════════════════════════
// 6. AUDIO PLAYBACK & ORB ANIMATIONS
// ═════════════════════════════════════════════════════════════

function playAudioResponse(base64Audio, onComplete) {
  try {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }

    const audioBytes = atob(base64Audio);
    const byteArray = new Uint8Array(audioBytes.length);
    for (let i = 0; i < audioBytes.length; i++) {
      byteArray[i] = audioBytes.charCodeAt(i);
    }

    const blob = new Blob([byteArray], { type: 'audio/mpeg' });
    const url = URL.createObjectURL(blob);

    currentAudio = new Audio(url);
    isAgentSpeaking = true;

    setOrbState('speaking', 'Aria is speaking...', `Voice: ${activeEngineDisplay.textContent}`);
    agentStatusText.textContent = 'Speaking...';
    if (interactionMode === 'live') interruptBtn.classList.remove('hidden');

    currentAudio.play().catch(e => {
      console.warn('Playback error:', e);
      isAgentSpeaking = false;
      if (onComplete) onComplete();
    });

    currentAudio.onended = () => {
      URL.revokeObjectURL(url);
      currentAudio = null;
      isAgentSpeaking = false;
      interruptBtn.classList.add('hidden');
      if (onComplete) onComplete();
    };

  } catch (err) {
    console.error('Audio decode error:', err);
    isAgentSpeaking = false;
    if (onComplete) onComplete();
  }
}

function setOrbState(state, title, subtitle) {
  if (!ambientOrb) return;
  ambientOrb.className = `ambient-orb state-${state}`;
  if (orbStatusTitle && title) orbStatusTitle.textContent = title;
  if (orbStatusSubtitle && subtitle) orbStatusSubtitle.textContent = subtitle;
}

// ═════════════════════════════════════════════════════════════
// 7. UI MESSAGES & TOASTS
// ═════════════════════════════════════════════════════════════

function addMessage(role, text, lang, provider) {
  const row = document.createElement('div');
  row.className = `message-row ${role}`;

  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const providerHtml = provider ? `<span class="msg-provider-tag">${escapeHtml(provider)}</span>` : '';
  const langTag = lang ? `<span class="msg-lang-tag">${lang.toUpperCase()}</span>` : '';

  if (role === 'assistant') {
    row.innerHTML = `
      <div class="msg-avatar-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="23"/>
          <line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
      </div>
      <div class="msg-bubble-card">
        <p class="msg-text-content">${escapeHtml(text)}</p>
        <div class="msg-meta-bar">
          <span>${timeStr}</span>
          ${langTag}
          ${providerHtml}
        </div>
      </div>
    `;
  } else {
    row.innerHTML = `
      <div class="msg-avatar-icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
          <circle cx="12" cy="7" r="4"/>
        </svg>
      </div>
      <div class="msg-bubble-card">
        <p class="msg-text-content">${escapeHtml(text)}</p>
        <div class="msg-meta-bar">
          <span>${timeStr}</span>
          ${langTag}
        </div>
      </div>
    `;
  }

  chatContainer.appendChild(row);
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addTypingIndicator() {
  const id = `typing_${Date.now()}`;
  const row = document.createElement('div');
  row.className = 'message-row assistant typing-row';
  row.id = id;
  row.innerHTML = `
    <div class="msg-avatar-icon">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      </svg>
    </div>
    <div class="msg-bubble-card typing-bubble">
      <div class="typing-dot-blue"></div>
      <div class="typing-dot-blue"></div>
      <div class="typing-dot-blue"></div>
    </div>
  `;
  chatContainer.appendChild(row);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function hideWelcome() {
  if (welcomeMsg) welcomeMsg.style.display = 'none';
}

async function clearConversation() {
  if (isLiveActive) stopHandsFreeSession();
  try {
    await fetch(`${API_BASE}/api/session/clear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: SESSION_ID })
    });
  } catch (e) {}

  chatContainer.innerHTML = '';
  if (welcomeMsg) {
    welcomeMsg.style.display = 'flex';
    chatContainer.appendChild(welcomeMsg);
  }

  if (interactionMode === 'live') {
    startHandsFreeSession();
  } else {
    setOrbState('idle', 'Push-to-Talk Mode', 'Click the microphone button below to speak');
  }
}

function showProcessing(text) {
  if (processingText) processingText.textContent = text;
  if (processingOverlay) processingOverlay.classList.remove('hidden');
}

function hideProcessing() {
  if (processingOverlay) processingOverlay.classList.add('hidden');
}

function showToast(msg) {
  const toast = document.createElement('div');
  toast.className = 'bespoke-toast';
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/\n/g, '<br>');
}

function handleTextKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendTextMessage();
  }
}

function autoResizeTextarea(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 100) + 'px';
}

// ── Check API Health on Startup ──
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    const data = await res.json();
    if (data.model) {
      activeModelDisplay.textContent = data.model.split('/').pop().split(':')[0];
    }
  } catch (e) {
    console.warn('Health check offline:', e);
  }
}

// ── Initialization ──
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  selectLanguage('en');         // Default to English -> ElevenLabs
  setInteractionMode('live');   // Default to Hands-Free mode
});
