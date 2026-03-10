document.getElementById("start").onclick = async () => {
  try {
    await navigator.mediaDevices.getUserMedia({ audio: true });
    console.log("mic permission granted");
  } catch (err) {
    console.error("mic permission failed:", err);
    alert("microphone permission required to record your voice"
    )
    return;
  }

  // Open side panel immediately so live transcript is visible
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  await chrome.sidePanel.open({ tabId: tab.id });

  const streamId = await chrome.tabCapture.getMediaStreamId();

  const authData = await chrome.storage.local.get('auth_token');

  chrome.runtime.sendMessage({
    type: "START_TAB_CAPTURE",
    streamId,
    token: authData.auth_token || null
  });

  console.log("🎧 tabCapture streamId sent, side panel opened");
};

document.getElementById("stop").onclick = async () => {
  chrome.runtime.sendMessage({ type: "STOP_RECORDING" });
  console.log("stop recording sent");
};

