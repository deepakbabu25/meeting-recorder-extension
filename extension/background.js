
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

// ❌ Prevent WebRTC globals from being accessed
// self.RTCRtpSender = undefined;

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
    // ✅ Fix: use runtime.sendMessage so the side panel receives it.
    // chrome.tabs.sendMessage only reaches content scripts in a tab,
    // NOT extension pages like the side panel.
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

    // if(senderUrl.includes("sidepanel.html")){
    //   // chrome.runtime.sendMessage(msg);
    //   return;
    // }

    // if(senderUrl.includes("offscreen.html")){
    // chrome.runtime.sendMessage(msg);
    // return;

    if (senderUrl.includes("popup.html")) {
      chrome.runtime.sendMessage(msg);
      return;
    }
    if (senderUrl.includes("offscreen.html")) {
      // ✅ Fix: pass msg directly, not wrapped in { msg } which broke msg.type
      await sendToSidePanel(msg);
      return;
    }
  })();
});
