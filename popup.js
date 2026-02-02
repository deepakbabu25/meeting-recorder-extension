let mediaRecorder;
let audioChunks = [];
let audioContext; // keep reference

document.getElementById("start").onclick = async () => {
  console.log(" Start clicked");

  chrome.runtime.sendMessage({
    type: "RECORDING_STARTED",
    time: Date.now()
  });

  chrome.tabCapture.capture({ audio: true, video: false }, async (stream) => {
    if (!stream) {
      console.error(" tabCapture failed:", chrome.runtime.lastError);
      return;
    }

    console.log("Tab audio stream captured");

    /*
        RESTORE AUDIO PLAYBACK
        */

    audioContext = new AudioContext();
    await audioContext.resume(); // IMPORTANT

    const source = audioContext.createMediaStreamSource(stream);
    source.connect(audioContext.destination);

    console.log("Audio routed to speakers");

    /* 
     RECORD AUDIO
        */

    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.start();
    console.log("MediaRecorder started");

    mediaRecorder.ondataavailable = (e) => {
      console.log("Audio chunk:", e.data.size);
      audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      console.log("Recording stopped");
       chrome.runtime.sendMessage({
        type: "RECORDING_STOPPED",
        time: Date.now()
    });

      const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
      const url = URL.createObjectURL(audioBlob);

      // open recorded audio in new tab
      chrome.tabs.create({ url });
    };
  });
};

document.getElementById("stop").onclick = () => {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
};
