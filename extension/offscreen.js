let ws;
let audioContext;
let processor;
let source;
let tabStream;
let micStream;
let currentMeetingId = null;
let heartbeatInterval = null;
let reconnectInterval = null;
let isExpectedClose = false;

// Audio buffering
let audioBufferQueue = []; // Holds PCM buffers while offline
const MAX_BUFFER_SIZE = 5000; // ~2.5 mins of audio depending on buffer size

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
    isExpectedClose = false;
    audioBufferQueue = []; // Reset buffer

    function connectWebSocket() {
      let wsUrl = "wss://debroah-prehazard-candance.ngrok-free.dev/ws/audio";
      const params = [];
      if (msg.token) params.push(`token=${msg.token}`);
      if (currentMeetingId) params.push(`meeting_id=${currentMeetingId}`);
      if (params.length > 0) wsUrl += `?${params.join('&')}`;

      ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";

      setupWebSocketHandlers();
    }

    function setupWebSocketHandlers() {
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

        if (data.type === "PARTIAL_TRANSCRIPT") {
          chrome.runtime.sendMessage({
            type: "PARTIAL_TRANSCRIPT",
            meeting_id: data.meeting_id,
            text: data.text
          });
          return;
        }

        if (data.type === "CHAT_READY") {
          chrome.runtime.sendMessage({
            type: "CHAT_READY",
            meeting_id: data.meeting_id
          });
          return;
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
            isExpectedClose = true;
            ws.close();
          }

          return;
        }
      };

      ws.onclose = () => {
        console.log("WebSocket closed");
        if (heartbeatInterval) clearInterval(heartbeatInterval);

        // Auto-reconnect logic
        if (!isExpectedClose) {
          console.warn("Unexpected WebSocket closure. Attempting to reconnect...");
          if (!reconnectInterval) {
            reconnectInterval = setInterval(() => {
              if (!ws || ws.readyState === WebSocket.CLOSED) {
                console.log(" reconnecting...");
                connectWebSocket();
              }
            }, 3000); // Retry every 3 seconds
          }
        }
      };

      ws.onopen = async () => {
        console.log("WebSocket opened");
        if (reconnectInterval) {
          clearInterval(reconnectInterval);
          reconnectInterval = null;
        }

        // Flush buffered audio chunks
        while (audioBufferQueue.length > 0 && ws.readyState === WebSocket.OPEN) {
          const chunk = audioBufferQueue.shift();
          ws.send(chunk);
        }
        console.log(` flushed remaining audio chunks (remaining: ${audioBufferQueue.length})`);
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
          const pcm = e.inputBuffer.getChannelData(0);
          // Create a copy of the buffer so it doesn't get swept by garbage collector
          const pcmCopy = new Float32Array(pcm);

          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(pcmCopy.buffer);
          } else if (!isExpectedClose) {
            // Buffer audio if unexpectedly offline
            audioBufferQueue.push(pcmCopy.buffer);
            if (audioBufferQueue.length > MAX_BUFFER_SIZE) {
              audioBufferQueue.shift(); // Drop oldest chunk
            }
          }
        };

        source.connect(processor);
        processor.connect(silentGain);
        silentGain.connect(audioContext.destination);

        console.log("🎙 Tab audio streaming started");
      };
    } // End of setupWebSocketHandlers()

    // Initial connection kickoff
    connectWebSocket();
  }

  // ================= STOP =================
  if (msg.type === "STOP_RECORDING") {
    console.log("Stopping audio");

    // Stop heartbeat
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }

    isExpectedClose = true;

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
