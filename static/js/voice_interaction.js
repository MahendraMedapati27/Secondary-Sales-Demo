/**
 * Voice Interaction Module
 * Handles voice input (Speech-to-Text) and output (Text-to-Speech) for the chatbot
 * Uses Azure Speech Services for high-quality voice recognition and synthesis
 */

let voiceRecognition = null;
let isListening = false;
let currentLanguage = 'en';
let speechConfig = null;
let audioConfig = null;
let recognizer = null;
let voiceEnabled = false;
let speechSynthesis = null;

// Initialize voice interaction
async function initializeVoiceInteraction() {
    console.log('[VOICE] Initializing voice interaction...');
    
    try {
        // Check if browser supports Web Speech API (fallback)
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            console.log('[VOICE] Browser supports Web Speech API');
        }
        
        // Wait a bit for Speech SDK to load from CDN
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Check Azure Speech Service availability
        const configResponse = await fetch('/enhanced-chat/api/voice/config');
        const config = await configResponse.json();
        
        if (config.enabled) {
            voiceEnabled = true;
            console.log('[VOICE] ✅ Azure Speech Service is enabled');
            console.log('[VOICE] Region:', config.region);
            console.log('[VOICE] Available languages:', config.languages);
            
            // Check if SpeechSDK is available
            if (typeof SpeechSDK !== 'undefined') {
                console.log('[VOICE] ✅ Azure Speech SDK is loaded');
                // Initialize Azure Speech SDK
                await initializeAzureSpeech();
            } else {
                console.warn('[VOICE] ⚠️ Azure Speech SDK not loaded, will use Web Speech API');
                initializeWebSpeechAPI();
            }
        } else {
            console.warn('[VOICE] ⚠️ Azure Speech Service is not configured');
            console.warn('[VOICE] Falling back to browser Web Speech API');
            initializeWebSpeechAPI();
        }
        
        // Setup voice button
        setupVoiceButton();
        
    } catch (error) {
        console.error('[VOICE] ❌ Error initializing voice interaction:', error);
        // Fallback to Web Speech API
        initializeWebSpeechAPI();
    }
}

// Initialize speech config with token
function initializeSpeechConfig(tokenData) {
    try {
        speechConfig = SpeechSDK.SpeechConfig.fromAuthorizationToken(
            tokenData.token,
            tokenData.region
        );
        
        // Set language
        updateSpeechLanguage();
        
        console.log('[VOICE] ✅ Azure Speech SDK initialized');
    } catch (error) {
        console.error('[VOICE] ❌ Error creating speech config:', error);
        throw error;
    }
}

// Initialize Azure Speech SDK
async function initializeAzureSpeech() {
    try {
        // Get access token from backend
        const tokenResponse = await fetch('/enhanced-chat/api/voice/token');
        const tokenData = await tokenResponse.json();
        
        if (!tokenData.token) {
            throw new Error('Failed to get access token');
        }
        
        // Wait for Speech SDK to load if not already available
        if (typeof SpeechSDK === 'undefined') {
            console.warn('[VOICE] Azure Speech SDK not loaded yet, waiting...');
            // Wait up to 5 seconds for SDK to load
            let attempts = 0;
            const checkSDK = setInterval(() => {
                attempts++;
                if (typeof SpeechSDK !== 'undefined') {
                    clearInterval(checkSDK);
                    console.log('[VOICE] ✅ Azure Speech SDK loaded');
                    try {
                        initializeSpeechConfig(tokenData);
                    } catch (error) {
                        console.error('[VOICE] Error initializing config:', error);
                        initializeWebSpeechAPI();
                    }
                } else if (attempts >= 50) { // 5 seconds max wait
                    clearInterval(checkSDK);
                    console.error('[VOICE] Azure Speech SDK failed to load, using Web Speech API fallback');
                    initializeWebSpeechAPI();
                }
            }, 100);
            return;
        }
        
        initializeSpeechConfig(tokenData);
        
    } catch (error) {
        console.error('[VOICE] ❌ Error initializing Azure Speech SDK:', error);
        initializeWebSpeechAPI();
    }
}

// Initialize Web Speech API (fallback)
function initializeWebSpeechAPI() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
        console.error('[VOICE] ❌ Web Speech API not supported in this browser');
        disableVoiceButton();
        return;
    }
    
    voiceRecognition = new SpeechRecognition();
    voiceRecognition.continuous = false;
    voiceRecognition.interimResults = true;
    voiceRecognition.lang = getLanguageCode(currentLanguage);
    
    voiceRecognition.onstart = () => {
        console.log('[VOICE] 🎤 Listening started (Web Speech API)');
        isListening = true;
        updateVoiceButtonState(true);
    };
    
    voiceRecognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        
        if (event.results[event.resultIndex].isFinal) {
            console.log('[VOICE] 📝 Final transcript:', transcript);
            // Stop recognition before handling (prevents auto-restart)
            isListening = false;
            if (voiceRecognition.state === 'listening' || voiceRecognition.state === 'starting') {
                try {
                    voiceRecognition.stop();
                } catch (e) {
                    console.warn('[VOICE] Error stopping after result:', e);
                }
            }
            handleVoiceInput(transcript);
        } else {
            // Show interim results
            updateVoiceStatus('listening', transcript);
        }
    };
    
    voiceRecognition.onerror = (event) => {
        console.error('[VOICE] ❌ Recognition error:', event.error);
        
        // Don't stop on 'no-speech' or 'aborted' errors - they're normal
        if (event.error === 'no-speech') {
            console.log('[VOICE] No speech detected, continuing to listen...');
            return;
        }
        
        if (event.error === 'aborted') {
            console.log('[VOICE] Recognition aborted (normal during stop/restart)');
            return;
        }
        
        // Stop on other errors
        isListening = false;
        updateVoiceButtonState(false);
        updateVoiceStatus('error', 'Error: ' + event.error);
        
        if (event.error === 'not-allowed') {
            alert('Microphone access denied. Please allow microphone access to use voice input.');
        }
    };
    
    voiceRecognition.onend = () => {
        console.log('[VOICE] 🛑 Listening stopped');
        // Only update state if we're not intentionally restarting
        if (!isListening) {
            updateVoiceButtonState(false);
            hideVoiceStatus();
        }
    };
    
    console.log('[VOICE] ✅ Web Speech API initialized');
}

// Setup voice button
function setupVoiceButton() {
    const voiceButton = document.getElementById('voiceButton');
    if (!voiceButton) return;
    
    // Click to toggle
    voiceButton.addEventListener('click', toggleVoiceInput);
    
    // Long press support (optional)
    let pressTimer = null;
    voiceButton.addEventListener('mousedown', () => {
        pressTimer = setTimeout(() => {
            startVoiceInput();
        }, 300);
    });
    
    voiceButton.addEventListener('mouseup', () => {
        if (pressTimer) {
            clearTimeout(pressTimer);
            pressTimer = null;
        }
    });
    
    voiceButton.addEventListener('mouseleave', () => {
        if (pressTimer) {
            clearTimeout(pressTimer);
            pressTimer = null;
        }
    });
}

// Toggle voice input
function toggleVoiceInput() {
    if (isListening) {
        stopVoiceInput();
    } else {
        startVoiceInput();
    }
}

// Start voice input
async function startVoiceInput() {
    if (isListening) {
        console.log('[VOICE] Already listening, stopping first...');
        stopVoiceInput();
        // Wait a bit before starting again
        await new Promise(resolve => setTimeout(resolve, 300));
    }
    
    try {
        // Request microphone permission
        await navigator.mediaDevices.getUserMedia({ audio: true });
        
        if (voiceEnabled && typeof SpeechSDK !== 'undefined') {
            // Use Azure Speech SDK
            await startAzureRecognition();
        } else if (voiceRecognition) {
            // Use Web Speech API - check if already started
            const currentState = voiceRecognition.state;
            if (currentState === 'listening' || currentState === 'starting') {
                console.log('[VOICE] Web Speech API already active, stopping first...');
                try {
                    voiceRecognition.stop();
                    await new Promise(resolve => setTimeout(resolve, 500));
                } catch (e) {
                    console.warn('[VOICE] Error stopping recognition:', e);
                    // Recreate if in bad state
                    initializeWebSpeechAPI();
                }
            }
            
            // Only start if in idle or stopped state
            if (voiceRecognition.state === 'idle' || voiceRecognition.state === 'stopped' || !voiceRecognition.state) {
                try {
                    voiceRecognition.start();
                } catch (error) {
                    if (error.name === 'InvalidStateError') {
                        console.log('[VOICE] Invalid state, recreating Web Speech API...');
                        initializeWebSpeechAPI();
                        await new Promise(resolve => setTimeout(resolve, 200));
                        if (voiceRecognition) {
                            voiceRecognition.start();
                        }
                    } else {
                        throw error;
                    }
                }
            }
        } else {
            alert('Voice recognition is not available. Please check your browser support.');
        }
        
    } catch (error) {
        console.error('[VOICE] ❌ Error starting voice input:', error);
        isListening = false;
        updateVoiceButtonState(false);
        
        if (error.name === 'NotAllowedError') {
            alert('Microphone access denied. Please allow microphone access in your browser settings.');
        } else if (error.name === 'InvalidStateError') {
            // Recognition already started - try to stop and restart
            console.log('[VOICE] Recognition already started, attempting to reset...');
            stopVoiceInput();
            setTimeout(() => {
                startVoiceInput();
            }, 500);
        } else {
            alert('Failed to start voice input: ' + error.message);
        }
    }
}

// Start Azure Speech recognition
async function startAzureRecognition() {
    try {
        // Get fresh token
        const tokenResponse = await fetch('/enhanced-chat/api/voice/token');
        const tokenData = await tokenResponse.json();
        
        if (!tokenData.token) {
            throw new Error('Failed to get access token');
        }
        
        // Check if SpeechSDK is available
        if (typeof SpeechSDK === 'undefined') {
            throw new Error('Azure Speech SDK not loaded');
        }
        
        // Create new speech config with fresh token
        const config = SpeechSDK.SpeechConfig.fromAuthorizationToken(
            tokenData.token,
            tokenData.region
        );
        
        // Set language for recognition
        const langCode = getLanguageCode(currentLanguage);
        config.speechRecognitionLanguage = langCode;
        
        // Create audio config (use default microphone)
        audioConfig = SpeechSDK.AudioConfig.fromDefaultMicrophoneInput();
        
        // Create recognizer
        recognizer = new SpeechSDK.SpeechRecognizer(config, audioConfig);
        
        // Setup event handlers
        recognizer.recognizing = (s, e) => {
            if (e.result.text) {
                updateVoiceStatus('listening', e.result.text);
            }
        };
        
        recognizer.recognized = (s, e) => {
            if (e.result.reason === SpeechSDK.ResultReason.RecognizedSpeech) {
                console.log('[VOICE] 📝 Recognized:', e.result.text);
                handleVoiceInput(e.result.text);
            } else if (e.result.reason === SpeechSDK.ResultReason.NoMatch) {
                console.log('[VOICE] ⚠️ No speech recognized');
                updateVoiceStatus('error', 'No speech detected. Please try again.');
                setTimeout(hideVoiceStatus, 2000);
            }
        };
        
        recognizer.canceled = (s, e) => {
            console.log('[VOICE] ❌ Recognition canceled:', e.reason);
            if (e.reason === SpeechSDK.CancellationReason.Error) {
                console.error('[VOICE] Error details:', e.errorDetails);
                updateVoiceStatus('error', 'Recognition error: ' + e.errorDetails);
            }
            isListening = false;
            updateVoiceButtonState(false);
            hideVoiceStatus();
        };
        
        recognizer.sessionStopped = (s, e) => {
            console.log('[VOICE] 🛑 Session stopped');
            isListening = false;
            updateVoiceButtonState(false);
            hideVoiceStatus();
            recognizer.close();
        };
        
        // Start recognition
        recognizer.startContinuousRecognitionAsync(
            () => {
                console.log('[VOICE] 🎤 Listening started (Azure Speech)');
                isListening = true;
                updateVoiceButtonState(true);
            },
            (error) => {
                console.error('[VOICE] ❌ Failed to start recognition:', error);
                isListening = false;
                updateVoiceButtonState(false);
            }
        );
        
    } catch (error) {
        console.error('[VOICE] ❌ Error in Azure recognition:', error);
        isListening = false;
        updateVoiceButtonState(false);
        alert('Failed to start voice recognition: ' + error.message);
    }
}

// Stop voice input
function stopVoiceInput() {
    if (!isListening && (!recognizer || recognizer.state === 'Stopped') && 
        (!voiceRecognition || voiceRecognition.state === 'idle' || voiceRecognition.state === 'stopped')) {
        return;
    }
    
    isListening = false;
    updateVoiceButtonState(false);
    hideVoiceStatus();
    
    if (recognizer) {
        try {
            if (recognizer.state === 'Recognizing' || recognizer.state === 'Starting') {
                recognizer.stopContinuousRecognitionAsync(
                    () => {
                        console.log('[VOICE] 🛑 Azure recognition stopped');
                        recognizer.close();
                        recognizer = null;
                    },
                    (error) => {
                        console.error('[VOICE] ❌ Error stopping Azure recognition:', error);
                        recognizer.close();
                        recognizer = null;
                    }
                );
            } else {
                recognizer.close();
                recognizer = null;
            }
        } catch (error) {
            console.error('[VOICE] ❌ Error closing recognizer:', error);
            recognizer = null;
        }
    }
    
    if (voiceRecognition) {
        try {
            if (voiceRecognition.state === 'listening' || voiceRecognition.state === 'starting') {
                voiceRecognition.stop();
                console.log('[VOICE] 🛑 Web Speech API stopped');
            } else {
                // If in error state, abort to reset
                voiceRecognition.abort();
            }
        } catch (error) {
            console.error('[VOICE] ❌ Error stopping Web Speech API:', error);
            // Recreate recognition object if it's in a bad state
            if (error.message && error.message.includes('already started')) {
                console.log('[VOICE] Recreating Web Speech API object...');
                initializeWebSpeechAPI();
            }
        }
    }
}

// Handle voice input
function handleVoiceInput(transcript) {
    if (!transcript || !transcript.trim()) {
        console.log('[VOICE] Empty transcript, ignoring');
        return;
    }
    
    console.log('[VOICE] ✅ Processing transcript:', transcript);
    
    // Stop listening first
    stopVoiceInput();
    
    // Set the input field value
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.value = transcript;
        
        // Enable send button
        const sendButton = document.getElementById('sendButton');
        if (sendButton) {
            sendButton.disabled = false;
        }
        
        // Auto-send the message (voice input should work like typing and sending)
        console.log('[VOICE] Auto-sending voice input message...');
        if (typeof sendMessage === 'function') {
            // Small delay to ensure input is set
            setTimeout(() => {
                sendMessage();
            }, 100);
        } else {
            console.warn('[VOICE] sendMessage function not available');
        }
    }
    
    // Hide voice status
    hideVoiceStatus();
}

// Update speech language
function updateSpeechLanguage() {
    const langCode = getLanguageCode(currentLanguage);
    
    // Update Azure Speech config if available
    if (speechConfig && typeof SpeechSDK !== 'undefined') {
        try {
            speechConfig.speechRecognitionLanguage = langCode;
            console.log('[VOICE] Language updated to:', langCode);
        } catch (error) {
            console.warn('[VOICE] Could not update speech language:', error);
        }
    }
    
    // Update Web Speech API if available
    if (voiceRecognition) {
        voiceRecognition.lang = langCode;
        console.log('[VOICE] Web Speech API language updated to:', langCode);
    }
}

// Get language code for speech recognition
function getLanguageCode(lang) {
    const langMap = {
        'en': 'en-US',
        'hi': 'hi-IN',
        'te': 'te-IN',
        'my': 'my-MM'
    };
    return langMap[lang] || 'en-US';
}

// Update voice button state
function updateVoiceButtonState(listening) {
    const voiceButton = document.getElementById('voiceButton');
    const voiceIcon = document.getElementById('voiceIcon');
    
    if (!voiceButton || !voiceIcon) return;
    
    if (listening) {
        voiceButton.classList.add('active');
        voiceButton.classList.add('btn-danger');
        voiceButton.classList.remove('btn-outline-secondary');
        voiceIcon.classList.remove('fa-microphone');
        voiceIcon.classList.add('fa-microphone-slash');
        voiceButton.title = 'Stop listening (Click to stop)';
    } else {
        voiceButton.classList.remove('active');
        voiceButton.classList.remove('btn-danger');
        voiceButton.classList.add('btn-outline-secondary');
        voiceIcon.classList.remove('fa-microphone-slash');
        voiceIcon.classList.add('fa-microphone');
        voiceButton.title = 'Voice Input (Click to speak)';
    }
}

// Update voice status
function updateVoiceStatus(status, text) {
    const voiceStatus = document.getElementById('voiceStatus');
    const voiceStatusText = document.getElementById('voiceStatusText');
    
    if (!voiceStatus || !voiceStatusText) return;
    
    voiceStatus.style.display = 'flex';
    
    switch (status) {
        case 'listening':
            voiceStatusText.textContent = 'Listening: ' + (text || '...');
            break;
        case 'error':
            voiceStatusText.textContent = text || 'Error occurred';
            voiceStatus.classList.add('text-danger');
            break;
        default:
            voiceStatusText.textContent = text || 'Processing...';
    }
}

// Hide voice status
function hideVoiceStatus() {
    const voiceStatus = document.getElementById('voiceStatus');
    if (voiceStatus) {
        voiceStatus.style.display = 'none';
        voiceStatus.classList.remove('text-danger');
    }
}

// Disable voice button
function disableVoiceButton() {
    const voiceButton = document.getElementById('voiceButton');
    if (voiceButton) {
        voiceButton.disabled = true;
        voiceButton.title = 'Voice input not available';
    }
}

// Text-to-Speech: Speak avatar response
async function speakText(text, language = 'en') {
    if (!text || !text.trim()) {
        console.log('[VOICE] Empty text, skipping TTS');
        return;
    }
    
    try {
        console.log('[VOICE] 🔊 Generating speech for:', text.substring(0, 50) + '...');
        
        // Call TTS endpoint
        const response = await fetch('/enhanced-chat/api/voice/tts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: text,
                language: language
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('[VOICE] TTS request failed:', response.status, errorText);
            throw new Error(`TTS request failed: ${response.status} ${response.statusText}`);
        }
        
        // Check if response is actually audio
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('audio')) {
            const errorText = await response.text();
            console.error('[VOICE] TTS returned non-audio response:', errorText);
            throw new Error('TTS returned invalid response');
        }
        
        // Get audio blob
        const audioBlob = await response.blob();
        
        if (!audioBlob || audioBlob.size === 0) {
            throw new Error('TTS returned empty audio');
        }
        
        console.log('[VOICE] ✅ Audio blob received, size:', audioBlob.size, 'bytes');
        const audioUrl = URL.createObjectURL(audioBlob);
        
        // Create audio element and play
        const audio = new Audio(audioUrl);
        
        // Enhanced lip sync: Start speaking animation when audio starts playing
        let speakingAnimationActive = false;
        
        // Notify avatar to start speaking BEFORE playing audio
        if (window.setAvatarSpeaking) {
            window.setAvatarSpeaking(true);
            speakingAnimationActive = true;
            console.log('[VOICE] 🎭 Avatar speaking animation started');
        }
        
        // Play audio
        const playPromise = audio.play();
        
        if (playPromise !== undefined) {
            playPromise
                .then(() => {
                    console.log('[VOICE] ✅ Audio playback started');
                    // Ensure avatar is still speaking (in case there was a delay)
                    if (window.setAvatarSpeaking && !speakingAnimationActive) {
                        window.setAvatarSpeaking(true);
                        speakingAnimationActive = true;
                    }
                })
                .catch(error => {
                    console.error('[VOICE] ❌ Audio play failed:', error);
                    if (window.setAvatarSpeaking && speakingAnimationActive) {
                        window.setAvatarSpeaking(false);
                        speakingAnimationActive = false;
                    }
                    URL.revokeObjectURL(audioUrl);
                });
        }
        
        // When audio ends, notify avatar to stop speaking
        audio.onended = () => {
            console.log('[VOICE] ✅ Speech playback completed');
            if (window.setAvatarSpeaking && speakingAnimationActive) {
                window.setAvatarSpeaking(false);
                speakingAnimationActive = false;
            }
            // Clean up
            URL.revokeObjectURL(audioUrl);
        };
        
        audio.onerror = (error) => {
            console.error('[VOICE] ❌ Audio playback error:', error);
            if (window.setAvatarSpeaking && speakingAnimationActive) {
                window.setAvatarSpeaking(false);
                speakingAnimationActive = false;
            }
            URL.revokeObjectURL(audioUrl);
        };
        
        // Also handle pause/stop events
        audio.onpause = () => {
            if (window.setAvatarSpeaking && speakingAnimationActive) {
                window.setAvatarSpeaking(false);
                speakingAnimationActive = false;
            }
        };
        
    } catch (error) {
        console.error('[VOICE] ❌ Error in TTS:', error);
        // Don't show error to user, just log it
        if (window.setAvatarSpeaking) {
            window.setAvatarSpeaking(false);
        }
    }
}

// Update language (called when user changes language)
function updateVoiceLanguage(language) {
    currentLanguage = language;
    updateSpeechLanguage();
    console.log('[VOICE] Language updated to:', language);
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeVoiceInteraction);
} else {
    initializeVoiceInteraction();
}

// Export functions for use in other scripts
window.toggleVoiceInput = toggleVoiceInput;
window.startVoiceInput = startVoiceInput;
window.stopVoiceInput = stopVoiceInput;
window.speakText = speakText;
window.updateVoiceLanguage = updateVoiceLanguage;

