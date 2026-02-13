let ws;
let audioContext;
let processor;
let source;
let stream;
let currentMeetingId = null;
console.log("🔥 Offscreen script loaded");

chrome.runtime.onMessage.addListener(async (msg) => {
  console.log("📩 Offscreen received:", msg);

  if (msg.type === "START_TAB_CAPTURE") {
    console.log("🎵 Starting tab audio stream");
    

    ws = new WebSocket("ws://127.0.0.1:8000/ws/audio");
    ws.binaryType = "arraybuffer";

    


   ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  console.log("📩 WS → Offscreen:", data);

  if (data.type === "MEETING_STARTED") {
    currentMeetingId = data.meeting_id;
    console.log("Meeting ID received:", currentMeetingId);

    chrome.runtime.sendMessage({
      type: "MEETING_STARTED",
      meeting_id: currentMeetingId
    });
    return;
  }

  if (data.type === "MEETING_ENDED") {
    console.log("📤 Forwarding MEETING_ENDED to background");

    chrome.runtime.sendMessage({
      type: "MEETING_ENDED",
      meeting_id: data.meeting_id
    });
    return;
  }

  // (optional, you’re not using this now)
  // if (data.type === "MEETING_SUMMARY") {
  //   chrome.runtime.sendMessage(data);
  // }
};


    ws.onopen = async () => {
      audioContext = new AudioContext({ sampleRate: 16000 });

      // stream = await navigator.mediaDevices.getUserMedia({
      //   audio: {
      //     mandatory: {
      //       chromeMediaSource: "tab",
      //       chromeMediaSourceId: msg.streamId
      //     }
      //   }
      // });
      const tabStream=await navigator.mediaDevices.getUserMedia({
        audio:{
          mandatory:{
            chromeMediaSource: "tab",
            chromeMediaSourceId: msg.streamId,
            googleDisableLocalEcho: true

          }
        }
      });
      const micStream =await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl:true
        }
      });

      const tabSource = audioContext.createMediaStreamSource(tabStream);
      const micSource= audioContext.createMediaStreamSource(micStream);

      const destination= audioContext.createMediaStreamDestination();

      tabSource.connect(destination);
      micSource.connect(destination);

      source = audioContext.createMediaStreamSource(destination.stream);
      processor = audioContext.createScriptProcessor(4096, 1, 1);

      const silentGain = audioContext.createGain();
      silentGain.gain.value=0;

      processor.onaudioprocess = (e) => {
        const pcm = e.inputBuffer.getChannelData(0);
        ws.send(pcm.buffer);
      };
      // source.connect(audioContext.destination)
      source.connect(processor);
      processor.connect(silentGain);
      silentGain.connect(audioContext.destination);

      console.log("🎙 Tab audio streaming started");
    };
  }

  if (msg.type === "STOP_RECORDING") {
    console.log("🛑 Stopping audio");
    if(ws && ws.readyState === WebSocket.OPEN){
      ws.send(JSON.stringify({type:"MEETING_END"}));
     

    }

    if (processor) processor.disconnect();
    if (source) source.disconnect();
    
    if (stream) stream.getTracks().forEach(t => t.stop());
  }
});
