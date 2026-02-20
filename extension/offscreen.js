let ws;
let audioContext;
let processor;
let source;
let tabStream;
let micStream;
let currentMeetingId = null;
let heartbeatInterval = null;

console.log(" Offscreen script loaded");

chrome.runtime.onMessage.addListener(async (msg) => {
  console.log(" Offscreen received:", msg);

  // ================= START =================
  if (msg.type === "START_TAB_CAPTURE") {
    // Guard: prevent double WebSocket if already recording
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      console.warn("⚠️ WebSocket already active, ignoring duplicate START_TAB_CAPTURE");
      return;
    }

    console.log(" Starting tab audio stream");

    // ws = new WebSocket("ws://127.0.0.1:8000/ws/audio");
    ws = new WebSocket("wss://debroah-prehazard-candance.ngrok-free.dev/ws/audio");
    ws.binaryType = "arraybuffer";

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      console.log(" WS → Offscreen:", data);

      if (data.type === "MEETING_STARTED") {
        currentMeetingId = data.meeting_id;

        chrome.runtime.sendMessage({
          type: "MEETING_STARTED",
          meeting_id: currentMeetingId
        });
        return;
      }

      if (data.type === "KEEPALIVE") {
        return; // server keepalive — ignore silently
      }

      if (data.type === "MEETING_ENDED") {
        console.log("Backend finished meeting");

        chrome.runtime.sendMessage({
          type: "MEETING_ENDED",
          meeting_id: data.meeting_id
        });

        //  IMPORTANT FIX:
        // Close WebSocket ONLY after backend confirms
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.close();
        }

        return;
      }
    };

    ws.onopen = async () => {
      // Keep ngrok tunnel alive — send a ping every 20s
      heartbeatInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "PING" }));
          console.log("💓 Heartbeat ping sent");
        }
      }, 20000);

      audioContext = new AudioContext({ sampleRate: 16000 });

      // Capture TAB audio
      tabStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          mandatory: {
            chromeMediaSource: "tab",
            chromeMediaSourceId: msg.streamId,
            googleDisableLocalEcho: true
          }
        }
      });

      //  Capture MIC audio
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      const tabSource = audioContext.createMediaStreamSource(tabStream);
      const micSource = audioContext.createMediaStreamSource(micStream);

      const destination = audioContext.createMediaStreamDestination();

      // Record BOTH
      tabSource.connect(destination);
      micSource.connect(destination);

      // Play ONLY remote/tab audio locally (no mic echo)
      tabSource.connect(audioContext.destination);

      source = audioContext.createMediaStreamSource(destination.stream);
      processor = audioContext.createScriptProcessor(4096, 1, 1);

      const silentGain = audioContext.createGain();
      silentGain.gain.value = 0;

      processor.onaudioprocess = (e) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          const pcm = e.inputBuffer.getChannelData(0);
          ws.send(pcm.buffer);
        }
      };

      source.connect(processor);
      processor.connect(silentGain);
      silentGain.connect(audioContext.destination);

      console.log("🎙 Tab audio streaming started");
    };
  }

  // ================= STOP =================
  if (msg.type === "STOP_RECORDING") {
    console.log("Stopping audio");

    // Stop heartbeat
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
      //  Send end signal
      ws.send(JSON.stringify({ type: "MEETING_END" }));

      //  DO NOT CLOSE HERE
      // Wait for MEETING_ENDED from backend
    }

    if (processor) processor.disconnect();
    if (source) source.disconnect();

    if (tabStream) tabStream.getTracks().forEach(t => t.stop());
    if (micStream) micStream.getTracks().forEach(t => t.stop());

    // if (audioContext) audioContext.close();
    if (audioContext && audioContext.state !== "closed") {
      audioContext.close();
    }

  }
});
