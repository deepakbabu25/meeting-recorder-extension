document.getElementById("start").onclick = async () => {
  const streamId = await chrome.tabCapture.getMediaStreamId();

  chrome.runtime.sendMessage({
    type: "START_TAB_CAPTURE",
    streamId
  });

  console.log("🎧 tabCapture streamId sent");
};

document.getElementById("stop").onclick =async () => {
  chrome.runtime.sendMessage({ type: "STOP_RECORDING" });


  const[tab]=await chrome.tabs.query({
    active: true,
    currentWindow: true
  })
  await chrome.sidePanel.open({
    tabId: tab.id
  });
//   chrome.runtime.sendMessage({
//   type: "OPEN_SUMMARY_PANEL"
// });

console.log("side panel opened")
};
