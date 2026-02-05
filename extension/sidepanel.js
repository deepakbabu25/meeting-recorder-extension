const summaryDiv = document.getElementById("content");
const messagesDiv = document.getElementById("messages");
const questionInput = document.getElementById("question");
const askBtn = document.getElementById("ask");

let currentMeetingId = null;
let summaryReady = false;

summaryDiv.innerHTML = "<i>Analyzing meeting...</i>";

// 🔥 RECEIVE DATA FROM BACKGROUND / OFFSCREEN
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "MEETING_STARTED") {
    currentMeetingId = msg.meeting_id;
    summaryReady = false;
  }

  if (msg.type === "MEETING_SUMMARY") {
    const s = msg.summary;
    summaryReady = true;

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
        🤖 You can now ask questions about this meeting
      </p>
    `;
  }
});

// 🔥 CHAT
askBtn.onclick = async () => {
  const q = questionInput.value.trim();
  if (!q || !currentMeetingId || !summaryReady) return;

  // UI: show user message
  messagesDiv.innerHTML += `<p><b>You:</b> ${q}</p>`;
  questionInput.value = "";

  // UI: show thinking
  const thinkingId = `thinking-${Date.now()}`;
  messagesDiv.innerHTML += `<p id="${thinkingId}"><i>Bot is thinking…</i></p>`;
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  askBtn.disabled = true;

  try {
    const res = await fetch("http://127.0.0.1:8000/chat", {
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
  } catch (err) {
    document.getElementById(thinkingId).innerHTML =
      `<p><b>Bot:</b> Error answering question.</p>`;
  }

  askBtn.disabled = false;
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
};
