document.addEventListener("DOMContentLoaded", () => {
  const chatWindow = document.getElementById("chat-window");
  const questionEl = document.getElementById("question");
  const sendBtn = document.getElementById("send-btn");

  const profileToggle = document.getElementById("profile-toggle");
  const profileMenu = document.getElementById("profile-menu");
  const profileLabel = document.getElementById("profile-label");

  let currentProfile = "product";
  const sessionIds = {}; // profile -> sessionId
  let isStreaming = false;

  function getSessionIdForProfile(profile) {
    return sessionIds[profile] || null;
  }

  function setSessionIdForProfile(profile, id) {
    sessionIds[profile] = id;
  }

  // --- Profile dropup logic ----------------------------------------------

  profileToggle.addEventListener("click", () => {
    const isOpen = profileMenu.style.display === "block";
    profileMenu.style.display = isOpen ? "none" : "block";
  });

  profileMenu.addEventListener("click", (e) => {
    const opt = e.target.closest(".persona-option");
    if (!opt) return;
    const profile = opt.dataset.profile;
    currentProfile = profile;
    profileLabel.textContent = opt.textContent.trim();
    profileMenu.style.display = "none";
    chatWindow.innerHTML = "";
  });

  document.addEventListener("click", (e) => {
    if (!profileMenu.contains(e.target) && !profileToggle.contains(e.target)) {
      profileMenu.style.display = "none";
    }
  });

  // --- Chat helpers ------------------------------------------------------

  function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = "message " + role;
    div.textContent = text;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }

  function appendSources(sources) {
    if (!sources || !sources.length) return;
    const div = document.createElement("div");
    div.className = "sources";
    const uniqueFiles = Array.from(new Set(sources.map((s) => s.file_path)));
    div.textContent = "Sources: " + uniqueFiles.join(", ");
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }

  function appendError(message) {
    const div = document.createElement("div");
    div.className = "message assistant error";
    div.textContent = "⚠️ " + message;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }

  function setStreaming(val) {
    isStreaming = val;
    sendBtn.disabled = val;
    questionEl.disabled = val;
  }

  // --- Send message (SSE) -----------------------------------------------

  async function sendMessage() {
    const text = questionEl.value.trim();
    if (!text || isStreaming) return;

    appendMessage("user", text);
    questionEl.value = "";

    const existingSession = getSessionIdForProfile(currentProfile);

    const payload = {
      question: text,
      session_id: existingSession,
      profile: currentProfile,
    };

    setStreaming(true);

    try {
      const resp = await fetch("/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok || !resp.body) {
        appendMessage("assistant", "Error: failed to reach backend.");
        setStreaming(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let assistantBuffer = "";
      let hasError = false;

      function handleSSEChunk(chunk) {
        const lines = chunk.split("\n");
        let eventType = "message";
        let data = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.replace("event:", "").trim();
          } else if (line.startsWith("data:")) {
            data += line.replace("data:", "").trim();
          }
        }

        if (!data) return;

        try {
          const parsed = JSON.parse(data);

          if (eventType === "error") {
            // Quota exhausted or other backend RuntimeError
            appendError(parsed.message || "An error occurred.");
            hasError = true;

          } else if (eventType === "meta") {
            if (parsed.session_id) {
              setSessionIdForProfile(currentProfile, parsed.session_id);
            }
            if (parsed.sources) {
              appendSources(parsed.sources);
            }

          } else if (eventType === "message") {
            assistantBuffer += parsed.content || "";
          }

        } catch (err) {
          console.error("Failed to parse SSE data", err, data);
        }
      }

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let sep;
        while ((sep = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          handleSSEChunk(rawEvent);
        }
      }

      // Only render assistant answer if no error was received
      if (assistantBuffer && !hasError) {
        appendMessage("assistant", assistantBuffer);
      }

    } catch (err) {
      console.error(err);
      appendMessage("assistant", "Error: " + String(err));
    } finally {
      setStreaming(false);
    }
  }

  sendBtn.addEventListener("click", sendMessage);

  questionEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
}); 
