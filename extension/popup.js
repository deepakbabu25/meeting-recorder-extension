document.getElementById("start").onclick = async () => {
  const streamId = await chrome.tabCapture.getMediaStreamId();

  chrome.runtime.sendMessage({
    type: "START_TAB_CAPTURE",
    streamId
  });

  console.log("🎧 tabCapture streamId sent");
};

document.getElementById("stop").onclick = () => {
  chrome.runtime.sendMessage({ type: "STOP_RECORDING" });
};
