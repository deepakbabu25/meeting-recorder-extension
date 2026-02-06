

// ❌ Prevent WebRTC globals from being accessed
// self.RTCRtpSender = undefined;


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
async function sendToSidePanel(msg) {
  try{
  const [tab] = await chrome.tabs.query({
    active: true,
    currentWindow: true
  });

  if (!tab?.id) return;

  await chrome.tabs.sendMessage(tab.id, msg);
}catch(e){
   console.warn("Sidepanel not ready, message dropped:", msg.type);
}}
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
      await sendToSidePanel({
        msg
      });
      return;
    }
  })();
});
