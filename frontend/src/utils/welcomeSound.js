/**
 * Uses Web Speech API to say "Welcome to ACK AI" on login/register success.
 */
export function playWelcomeSound() {
  if ('speechSynthesis' in window) {
    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    // Using periods and spaces to force the TTS engine to spell out the letters
    const utterance = new SpeechSynthesisUtterance('Welcome to A. C. K.  A. i.');
    utterance.rate = 0.8;
    utterance.pitch = 1.1;
    utterance.volume = 0.8;

    // Try to pick a good English voice
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(
      (v) => v.lang.startsWith('en') && v.name.includes('Google')
    ) || voices.find((v) => v.lang.startsWith('en'));
    if (preferred) utterance.voice = preferred;

    window.speechSynthesis.speak(utterance);
  }
}
