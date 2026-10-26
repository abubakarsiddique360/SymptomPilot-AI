const state = {
  history: [],
  busy: false,
  meta: null,
  answer: "",
};

const els = {
  conversation: document.getElementById("conversation"),
  composer: document.getElementById("composer"),
  message: document.getElementById("message"),
  send: document.getElementById("send"),
  status: document.getElementById("status"),
  banner: document.getElementById("banner"),
  bannerLevel: document.getElementById("banner-level"),
  bannerText: document.getElementById("banner-text"),
  topicList: document.getElementById("topic-list"),
  themeToggle: document.getElementById("theme-toggle"),
  disclaimer: document.getElementById("disclaimer"),
  suggestions: document.getElementById("suggestions"),
};

const LEVEL_LABEL = {
  emergency: "Emergency",
  urgent: "Urgent",
  routine: "Routine",
  unknown: "Unclear",
};

/* ------------------------------------------------------------------ render */

const escapeHtml = (value) =>
  value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);

function renderMarkdown(text) {
  const lines = escapeHtml(text).split("\n");
  const out = [];
  let listOpen = false;

  const inline = (line) =>
    line
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[S(\d+)\]/g, '<span class="cite">[S$1]</span>');

  const closeList = () => {
    if (listOpen) {
      out.push("</ul>");
      listOpen = false;
    }
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      closeList();
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      if (!listOpen) {
        out.push("<ul>");
        listOpen = true;
      }
      out.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`);
      continue;
    }
    closeList();
    out.push(`<p>${inline(line)}</p>`);
  }
  closeList();
  return out.join("");
}

function evidenceHtml(citations) {
  if (!citations || !citations.length) return "";
  const cards = citations
    .map((citation) => {
      const source = (citation.sources || [])[0];
      const link = source && source.url
        ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.publisher || source.title)}</a>`
        : "";
      return `
        <div class="evidence-card">
          <h4>[${escapeHtml(citation.marker)}] ${escapeHtml(citation.title)} · ${escapeHtml(citation.section)}</h4>
          <p>${escapeHtml(citation.snippet.slice(0, 220))}…</p>
          ${link}
        </div>`;
    })
    .join("");
  return `<details class="evidence" open><summary>Evidence used (${citations.length})</summary>${cards}</details>`;
}

function followUpHtml(questions) {
  if (!questions || !questions.length) return "";
  const chips = questions
    .map((question) => `<button type="button" class="chip" data-prompt="${escapeHtml(question)}">${escapeHtml(question)}</button>`)
    .join("");
  return `<div class="follow-ups"><h3>Helpful next details</h3><div class="suggestions">${chips}</div></div>`;
}

function setBanner(urgency) {
  if (!urgency || !urgency.headline) {
    els.banner.hidden = true;
    return;
  }
  els.banner.hidden = false;
  els.banner.dataset.level = urgency.level;
  els.bannerLevel.textContent = LEVEL_LABEL[urgency.level] || urgency.level;
  const actions = (urgency.actions || []).slice(0, 2).join(" ");
  els.bannerText.textContent = `${urgency.headline}. ${actions}`;
}

function addMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const body = document.createElement("div");
  body.className = "message-body";
  body.innerHTML = role === "user" ? renderMarkdown(text) : "";
  article.appendChild(body);
  els.conversation.appendChild(article);
  els.conversation.scrollTop = els.conversation.scrollHeight;
  return article;
}

function typingHtml() {
  return '<span class="typing" aria-label="thinking"><span></span><span></span><span></span></span>';
}

/* -------------------------------------------------------------------- api */

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("health check failed");
    const data = await response.json();
    const mode = data.llm_mode === "llm" ? data.llm_provider : "extractive";
    els.status.textContent = `${mode} · ${data.documents} topics · ${data.chunks} passages`;
    els.status.classList.add("ready");
  } catch {
    els.status.textContent = "backend offline";
    els.status.classList.remove("ready");
  }
}

async function loadTopics() {
  try {
    const response = await fetch("/api/topics");
    if (!response.ok) throw new Error("topics failed");
    const topics = await response.json();
    els.topicList.innerHTML = "";
    for (const topic of topics) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = topic.title;
      button.dataset.prompt = `What should I know about ${topic.title.toLowerCase()}?`;
      item.appendChild(button);
      els.topicList.appendChild(item);
    }
  } catch {
    els.topicList.innerHTML = '<li class="muted">topics unavailable</li>';
  }
}

function paintAnswer(article, meta, answer) {
  const body = article.querySelector(".message-body");
  body.innerHTML =
    renderMarkdown(answer) + evidenceHtml(meta.citations) + followUpHtml(meta.follow_up_questions);
  article.dataset.level = meta.urgency ? meta.urgency.level : "";
  els.conversation.scrollTop = els.conversation.scrollHeight;
}

async function streamTriage(text, article) {
  const response = await fetch("/api/triage/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text, history: state.history.slice(-8) }),
  });
  if (!response.ok || !response.body) throw new Error(`stream failed (${response.status})`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  state.answer = "";

  const handle = (rawEvent) => {
    const lines = rawEvent.split("\n");
    let event = "message";
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (!dataLines.length) return;
    const payload = JSON.parse(dataLines.join("\n"));
    if (event === "meta") {
      state.meta = payload;
      setBanner(payload.urgency);
    } else if (event === "token") {
      state.answer += payload.text;
      paintAnswer(article, state.meta, state.answer);
    } else if (event === "done") {
      paintAnswer(article, state.meta, state.answer);
    }
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      if (part.trim()) handle(part);
    }
  }
  if (buffer.trim()) handle(buffer);
  return state.meta;
}

/* ---------------------------------------------------------------- actions */

function setBusy(busy) {
  state.busy = busy;
  els.send.disabled = busy;
  els.message.disabled = busy;
  if (!busy) els.message.focus();
}

async function sendMessage(text) {
  const trimmed = text.trim();
  if (!trimmed || state.busy) return;

  if (els.suggestions) els.suggestions.remove();
  addMessage("user", trimmed);
  state.history.push({ role: "user", content: trimmed });
  els.message.value = "";
  autoGrow();

  const article = addMessage("assistant", "");
  article.querySelector(".message-body").innerHTML = typingHtml();
  setBusy(true);

  try {
    const meta = await streamTriage(trimmed, article);
    state.history.push({ role: "assistant", content: state.answer });
    if (meta && meta.mode) {
      els.status.textContent = `${meta.mode} · ${meta.latency_ms} ms`;
    }
  } catch (error) {
    try {
      const response = await fetch("/api/triage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, history: state.history.slice(-8) }),
      });
      if (!response.ok) throw new Error(`request failed (${response.status})`);
      const data = await response.json();
      state.meta = data;
      setBanner(data.urgency);
      paintAnswer(article, data, data.answer);
      state.history.push({ role: "assistant", content: data.answer });
    } catch (fallbackError) {
      article.querySelector(".message-body").innerHTML =
        '<p class="error-note">The assistant could not be reached. Check that the server is running and try again.</p>';
      console.error(error, fallbackError);
    }
  } finally {
    setBusy(false);
  }
}

function autoGrow() {
  els.message.style.height = "auto";
  els.message.style.height = `${Math.min(els.message.scrollHeight, 144)}px`;
}

/* ----------------------------------------------------------------- events */

els.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(els.message.value);
});

els.message.addEventListener("input", autoGrow);
els.message.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    sendMessage(els.message.value);
  }
});

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-prompt]");
  if (!trigger) return;
  const prompt = trigger.getAttribute("data-prompt");
  if (prompt) sendMessage(prompt);
});

els.themeToggle.addEventListener("click", () => {
  const root = document.documentElement;
  const next = root.dataset.theme === "dark" ? "light" : "dark";
  root.dataset.theme = next;
  try {
    localStorage.setItem("symptompilot-theme", next);
  } catch {
    /* storage may be disabled */
  }
});

(function initTheme() {
  try {
    const stored = localStorage.getItem("symptompilot-theme");
    if (stored) document.documentElement.dataset.theme = stored;
    else if (window.matchMedia("(prefers-color-scheme: light)").matches) {
      document.documentElement.dataset.theme = "light";
    }
  } catch {
    /* ignore */
  }
})();

loadHealth();
loadTopics();
els.message.focus();
