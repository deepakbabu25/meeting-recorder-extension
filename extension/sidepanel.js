

async function bootstrap() {
  try {
    // Read THIS browser's own stored meeting_id — never use /meeting/latest.
    // Each browser instance stores its own meeting_id so two users can never
    // see each other's sessions.
    const stored = await chrome.storage.local.get("currentMeetingId");
    if (!stored.currentMeetingId) {
      console.log("No stored meeting_id — waiting for MEETING_STARTED event.");
      return;
    }

    currentMeetingId = stored.currentMeetingId;
    console.log("Bootstrapped from local storage:", currentMeetingId);

    // Check the meeting state directly using this browser's own meeting_id.
    const res = await fetch(
      `https://debroah-prehazard-candance.ngrok-free.dev/meeting/${currentMeetingId}/summary`,
      { headers: { "ngrok-skip-browser-warning": "true" } }
    );
    const data = await res.json();

    if (data.status === "READY") {
      // Already done — render immediately, no polling needed.
      renderSummary(data.summary);
      summaryReady = true;
      askBtn.disabled = false;
      questionInput.disabled = false;
    } else if (data.status === "PROCESSING") {
      // Still generating — start polling.
      pollMeetingSummary(currentMeetingId);
    }
    // RECORDING or NOT_FOUND — wait for MEETING_ENDED event.
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
questionInput.disabled = true;
summaryDiv.innerHTML = "<i>Analyzing meeting...</i>";

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "MEETING_STARTED") {
    currentMeetingId = msg.meeting_id;
    summaryReady = false;
    pollingStarted = false;
    askBtn.disabled = true;
    questionInput.disabled = true;
    summaryDiv.innerHTML = "<i>Analyzing meeting...</i>";

    // Save this browser's own meeting_id locally so bootstrap can restore it
    // if the side panel is closed and reopened.
    chrome.storage.local.set({ currentMeetingId: msg.meeting_id });
  }

  if (msg.type === "MEETING_ENDED") {
    if (pollingStarted) return;
    if (!currentMeetingId && msg.meeting_id) {
      currentMeetingId = msg.meeting_id;
    }
    if (!currentMeetingId) {
      console.warn("MEETING_ENDED recieved but no meeting_id");
      return;
    }
    pollingStarted = true;
    pollMeetingSummary(currentMeetingId)
  }

  // RAG first chunk ready — enable chat during live meeting
  if (msg.type === "CHAT_READY") {
    if (!currentMeetingId && msg.meeting_id) {
      currentMeetingId = msg.meeting_id;
    }
    summaryReady = true;
    askBtn.disabled = false;
    questionInput.disabled = false;
    summaryDiv.innerHTML += "<p><i>💬 Chat is now available — ask questions about what's been discussed so far.</i></p>";
  }
});


async function pollMeetingSummary(meetingId) {
  const interval = setInterval(async () => {
    try {
      // const res = await fetch(
      //   `http://127.0.0.1:8000/meeting/${meetingId}/summary`
      // );
      const res = await fetch(
        `https://debroah-prehazard-candance.ngrok-free.dev/meeting/${meetingId}/summary`,
        { headers: { "ngrok-skip-browser-warning": "true" } }
      );

      const data = await res.json();

      if (data.status === "READY") {
        clearInterval(interval);
        renderSummary(data.summary);
        summaryReady = true;
        askBtn.disabled = false;
        questionInput.disabled = false;
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
    <ul>${s.action_items.length
      ? s.action_items.map(a => `<li>${a}</li>`).join("")
      : "<li>None</li>"
    }</ul>

    <h4>Decisions</h4>
    <ul>${s.decisions.length
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
  messagesDiv.innerHTML += `<p id="${thinkingId}"><i>Bot is thinking</i></p>`;
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  askBtn.disabled = true;

  try {
    const res = await fetch("https://debroah-prehazard-candance.ngrok-free.dev/chat/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true"
      },
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
