
// ============================
// KEEP SERVICE WORKER ALIVE
// Chrome terminates idle SWs after ~30s — alarms prevent this
// ============================
chrome.alarms.create("sw-keepalive", { periodInMinutes: 0.33 }); // every ~20s
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "sw-keepalive") {
    console.log("⏰ SW keepalive ping");
  }
});

async function ensureOffscreen() {
  const exists = await chrome.offscreen.hasDocument();
  if (!exists) {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["USER_MEDIA"],
      justification: "Capture tab audio and mic via getUserMedia for transcription"
    });
    console.log("✅ Offscreen document created");
  }
}

async function sendToSidePanel(msg) {
  try {
    await chrome.runtime.sendMessage(msg);
  } catch (e) {
    console.warn("Sidepanel not ready, message dropped:", msg.type);
  }
}

chrome.runtime.onMessage.addListener((msg, sender) => {
  (async () => {
    await ensureOffscreen();

    const senderUrl = sender?.url || "";
    console.log("🛣 BG routing:", msg, "from", senderUrl);

    // ── Track recording state in chrome.storage so bootstrap can detect it ──
    // This allows the side panel to know if a recording is active even when
    // it was opened AFTER MEETING_STARTED was already fired.
    if (msg.type === "MEETING_STARTED" && msg.meeting_id) {
      await chrome.storage.local.set({
        recording_active: true,
        activeMeetingId: msg.meeting_id,
        currentMeetingId: msg.meeting_id
      });
    }
    if (msg.type === "MEETING_ENDED" || msg.type === "MEETING_STOPPED") {
      await chrome.storage.local.set({ recording_active: false });
    }

    if (senderUrl.includes("popup.html")) {
      chrome.runtime.sendMessage(msg);
      return;
    }
    if (senderUrl.includes("offscreen.html")) {
      await sendToSidePanel(msg);
      return;
    }
  })();
});
