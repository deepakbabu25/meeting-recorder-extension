document.getElementById("start").onclick = async () => {
  try{
  await navigator.mediaDevices.getUserMedia({audio:true});
  console.log("mic permission granted");
  }catch(err){
    console.error("mic permission failed:", err);
    alert("microphone permission required to record your voice"
    )
    return;
  }
  const streamId = await chrome.tabCapture.getMediaStreamId();

  chrome.runtime.sendMessage({
    type: "START_TAB_CAPTURE",
    streamId
  });

  console.log("🎧 tabCapture streamId sent");
};

document.getElementById("stop").onclick =async () => {
  // chrome.runtime.sendMessage({ type: "STOP_RECORDING" });


  const[tab]=await chrome.tabs.query({
    active: true,
    currentWindow: true
  })
  await chrome.sidePanel.open({
    tabId: tab.id
  });
  chrome.runtime.sendMessage({ type: "STOP_RECORDING" });
//   chrome.runtime.sendMessage({
//   type: "OPEN_SUMMARY_PANEL"
// });

console.log("side panel opened")
};
