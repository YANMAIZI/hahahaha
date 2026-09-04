const clickAudio = typeof Audio !== "undefined" ? new Audio("/sounds/click.mp3") : null;

export const playTick = (enabled) => {
  if (!enabled || !clickAudio) return;
  try {
    clickAudio.currentTime = 0;
    clickAudio.volume = 0.6;
    clickAudio.play().catch(() => {});
  } catch {
    /* audio not available */
  }
};
