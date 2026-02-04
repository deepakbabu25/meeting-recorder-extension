async function ensureOffscreen() {
  const exists = await chrome.offscreen.hasDocument();
  if (!exists) {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["AUDIO_PLAYBACK"],
      justification: "Process tab audio for transcription"
    });
    console.log("✅ Offscreen document created");
  }
}

chrome.runtime.onMessage.addListener((msg) => {
  (async () => {
    await ensureOffscreen();
    chrome.runtime.sendMessage(msg);
  })();
});
