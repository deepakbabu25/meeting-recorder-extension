chrome.runtime.onMessage.addListener((msg) => {
  console.log("📩 Background received:", msg);
});
