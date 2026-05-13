document.addEventListener("DOMContentLoaded", () => {

const API_BASE = "http://localhost:8000";
let sessionId = null;
let isStreaming = false;

const chatWindow = document.getElementById("chat-window");
const questionEl = document.getElementById("question");
const sendBtn    = document.getElementById("send-btn");
const clearBtn   = document.getElementById("clear-btn");
const statusDot  = document.getElementById("status-dot");

async function checkHealth() { 
  try {
    const res = await fetch(`${API_BASE}/health`);
    statusDot.classList.toggle("offline", !res.ok);
  } catch { statusDot.classList.add("offline"); }
}
checkHealth();
setInterval(checkHealth, 30000);

questionEl.addEventListener("input", () => {
  questionEl.style.height = "auto";
  questionEl.style.height = Math.min(questionEl.scrollHeight, 140) + "px";
});

questionEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

sendBtn.addEventListener("click", handleSend);
clearBtn.addEventListener("click", clearConversation);

async function handleSend() {
  const question = questionEl.value.trim();
  if (!question || isStreaming) return;
  hideEmptyState();
  appendMessage("user", question);
  questionEl.value = "";
  questionEl.style.height = "auto";
  setStreaming(true);
  const { bubbleEl, sourcesEl } = appendAssistantPlaceholder();
  try {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, ...(sessionId && { session_id: sessionId }) }),
    });
    if (!response.ok) { bubbleEl.textContent = `Error: ${response.status}`; setStreaming(false); return; }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;
        let event;
        try { event = JSON.parse(raw); } catch { continue; }
        if (event.type === "meta") {
          sessionId = event.session_id;
          if (event.sources?.length) renderSources(sourcesEl, event.sources);
        } else if (event.type === "token") {
          const ind = bubbleEl.querySelector(".typing-indicator");
          if (ind) ind.remove();
          bubbleEl.textContent += event.content;
          scrollToBottom();
        }
      }
    }
  } catch (err) { bubbleEl.textContent = `Connection error: ${err.message}`; }
  setStreaming(false);
  scrollToBottom();
}

async function clearConversation() {
  if (sessionId) {
    try { await fetch(`${API_BASE}/history/${sessionId}/clear`, { method: "DELETE" }); } catch {}
    sessionId = null;
  }
  chatWindow.innerHTML = "";
  chatWindow.appendChild(createEmptyState());
}

function appendMessage(role, text) {
  const msg = document.createElement("div");
  msg.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  msg.appendChild(bubble);
  chatWindow.appendChild(msg);
  scrollToBottom();
}

function appendAssistantPlaceholder() {
  const msg = document.createElement("div");
  msg.className = "message assistant";
  const bubbleEl = document.createElement("div");
  bubbleEl.className = "bubble";
  const ind = document.createElement("div");
  ind.className = "typing-indicator";
  ind.innerHTML = "<span></span><span></span><span></span>";
  bubbleEl.appendChild(ind);
  const sourcesEl = document.createElement("div");
  sourcesEl.className = "sources";
  msg.appendChild(bubbleEl);
  msg.appendChild(sourcesEl);
  chatWindow.appendChild(msg);
  scrollToBottom();
  return { bubbleEl, sourcesEl };
}

function renderSources(container, sources) {
  container.textContent = "Sources: ";
  sources.forEach((src) => {
    const tag = document.createElement("span");
    tag.textContent = src.split("/").pop();
    tag.title = src;
    container.appendChild(tag);
  });
}

function hideEmptyState() { document.getElementById("empty-state")?.remove(); }

function createEmptyState() {
  const div = document.createElement("div");
  div.className = "empty-state";
  div.id = "empty-state";
  div.innerHTML = "<h2>Ask anything about WorldMonitor</h2><p>Answers are grounded in the WorldMonitor knowledge base.</p>";
  return div;
}

function setStreaming(val) {
  isStreaming = val;
  sendBtn.disabled = val;
  questionEl.disabled = val;
}

function scrollToBottom() { chatWindow.scrollTop = chatWindow.scrollHeight; }

}); // end DOMContentLoaded 
