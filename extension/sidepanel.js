
async function bootstrap() {
  try {
    const res = await fetch("http://127.0.0.1:8000/meeting/latest");
    if (!res.ok) {
      console.warn("No existing meeting yet");
      return;
    }

    const data = await res.json();
    currentMeetingId = data.meeting_id;

    console.log(" Bootstrapped meeting:", currentMeetingId);

    pollMeetingSummary(currentMeetingId);
  } catch (e) {
    console.warn("Bootstrap failed", e);
  }
}

bootstrap();

const summaryDiv = document.getElementById("content");
const messagesDiv = document.getElementById("messages");
const questionInput = document.getElementById("question");
const askBtn = document.getElementById("ask");

let currentMeetingId = null;
let summaryReady = false;
let pollingStarted = false;

askBtn.disabled = true;
summaryDiv.innerHTML = "<i>Analyzing meeting...</i>";

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "MEETING_STARTED") {
    currentMeetingId = msg.meeting_id;
    summaryReady = false;
    pollingStarted = false;
    askBtn.disabled = true;
    summaryDiv.innerHTML = "<i>Analyzing meeting...</i>";
  }

  if (msg.type === "MEETING_ENDED") {
    if (pollingStarted) return;
    if(!currentMeetingId && msg.meeting_id){
      currentMeetingId = msg.meeting_id
    }
    if(!currentMeetingId){
      console.warn("MEETING_ENDED recieved but no meeting_id");
      return;
    }
    pollingStarted = true;
    pollMeetingSummary(currentMeetingId)
  }
});

async function pollMeetingSummary(meetingId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/meeting/${meetingId}/summary`
      );
      const data = await res.json();

      if (data.status === "READY") {
        clearInterval(interval);
        renderSummary(data.summary);
        summaryReady = true;
        askBtn.disabled = false;
      }

      if (data.status === "NOT_FOUND") {
        clearInterval(interval);
        summaryDiv.innerHTML = "<i>Meeting not found.</i>";
      }
    } catch (e) {
      console.error("Polling error", e);
    }
  }, 2000);
}

function renderSummary(s) {
  summaryDiv.innerHTML = `
    <h3>Meeting Insights</h3>

    <p><b>Summary</b><br>${s.summary}</p>

    <h4>Key Points</h4>
    <ul>${s.key_points.map(p => `<li>${p}</li>`).join("")}</ul>

    <h4>Action Items</h4>
    <ul>${
      s.action_items.length
        ? s.action_items.map(a => `<li>${a}</li>`).join("")
        : "<li>None</li>"
    }</ul>

    <h4>Decisions</h4>
    <ul>${
      s.decisions.length
        ? s.decisions.map(d => `<li>${d}</li>`).join("")
        : "<li>None</li>"
    }</ul>

    <p style="opacity:0.8;margin-top:12px;">
      You can now ask questions about this meeting
    </p>
  `;
}

askBtn.onclick = async () => {
  const q = questionInput.value.trim();
  if (!q || !summaryReady) return;

  messagesDiv.innerHTML += `<p><b>You:</b> ${q}</p>`;
  questionInput.value = "";

  const thinkingId = `thinking-${Date.now()}`;
  messagesDiv.innerHTML += `<p id="${thinkingId}"><i>Bot is thinking…</i></p>`;
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  askBtn.disabled = true;

  try {
    const res = await fetch("http://127.0.0.1:8000/chat/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        meeting_id: currentMeetingId,
        question: q
      })
    });

    const data = await res.json();
    document.getElementById(thinkingId).innerHTML =
      `<p><b>Bot:</b> ${data.answer}</p>`;
  } catch {
    document.getElementById(thinkingId).innerHTML =
      `<p><b>Bot:</b> Error answering question.</p>`;
  }

  askBtn.disabled = false;
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
};
