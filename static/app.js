const elements = {
  shell: document.querySelector(".shell"),
  sidebarToggle: document.querySelector("#sidebar-toggle"),
  navLinks: document.querySelectorAll(".nav-link"),
  views: document.querySelectorAll(".view"),
  settingsForm: document.querySelector("#settings-form"),
  settingsFeedback: document.querySelector("#settings-feedback"),
  connectionStatus: document.querySelector("#connection-status"),
  connectionHint: document.querySelector("#connection-hint"),
  chatForm: document.querySelector("#chat-form"),
  chatThread: document.querySelector("#chat-thread"),
  messageInput: document.querySelector("#message-input"),
  sendButton: document.querySelector("#send-button"),
  clearChatButton: document.querySelector("#clear-chat-button"),
  apiUrl: document.querySelector("#api-url"),
  apiKey: document.querySelector("#api-key"),
  modelName: document.querySelector("#model-name"),
  calypsoUrl: document.querySelector("#calypso-url"),
  calypsoToken: document.querySelector("#calypso-token"),
  calypsoEnabled: document.querySelector("#calypso-enabled"),
  calypsoFields: document.querySelector("#calypso-fields"),
  exportSettingsButton: document.querySelector("#export-settings-button"),
  importSettingsButton: document.querySelector("#import-settings-button"),
  importFileInput: document.querySelector("#import-file-input"),
  // RAG / Knowledge Base
  ragEnabled: document.querySelector("#rag-enabled"),
  ragDocCount: document.querySelector("#rag-doc-count"),
  kbUploadForm: document.querySelector("#kb-upload-form"),
  kbFileInput: document.querySelector("#kb-file-input"),
  kbDropZone: document.querySelector("#kb-drop-zone"),
  kbDocuments: document.querySelector("#kb-documents"),
  kbUploadFeedback: document.querySelector("#kb-upload-feedback"),
};

const state = {
  messages: [],
  configured: false,
};

initialize();

async function initialize() {
  elements.sidebarToggle.addEventListener("click", toggleSidebar);

  elements.navLinks.forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.viewTarget));
  });

  elements.settingsForm.addEventListener("submit", handleSettingsSave);
  elements.exportSettingsButton.addEventListener("click", handleExportSettings);
  elements.importSettingsButton.addEventListener("click", () => elements.importFileInput.click());
  elements.importFileInput.addEventListener("change", handleImportSettings);
  elements.chatForm.addEventListener("submit", handleChatSubmit);
  elements.clearChatButton.addEventListener("click", handleClearChat);

  // Toggle F5 AI Security fields visibility
  elements.calypsoEnabled.addEventListener("change", () => {
    elements.calypsoFields.classList.toggle("hidden", !elements.calypsoEnabled.checked);
  });

  // RAG: file upload & drag-and-drop
  elements.kbFileInput.addEventListener("change", handleKBUpload);
  elements.kbDropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    elements.kbDropZone.classList.add("dragover");
  });
  elements.kbDropZone.addEventListener("dragleave", () => {
    elements.kbDropZone.classList.remove("dragover");
  });
  elements.kbDropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    elements.kbDropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      elements.kbFileInput.files = e.dataTransfer.files;
      handleKBUpload();
    }
  });

  // Load settings from server session
  await loadSettings();
  await loadKBDocuments();
}

function toggleSidebar() {
  elements.shell.classList.toggle("sidebar-collapsed");
}

async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    const settings = await response.json();
    elements.apiUrl.value = settings.apiUrl || "";
    elements.apiKey.value = "";
    elements.apiKey.placeholder = settings.apiKey ? "Key saved on server" : "Enter your secret key";
    elements.modelName.value = settings.modelName || "gpt-4o-mini";
    elements.calypsoEnabled.checked = Boolean(settings.calypsoEnabled);
    elements.calypsoFields.classList.toggle("hidden", !elements.calypsoEnabled.checked);
    elements.calypsoUrl.value = settings.calypsoUrl || "";
    elements.calypsoToken.value = "";
    elements.calypsoToken.placeholder = settings.calypsoToken ? "Token saved on server" : "Enter your F5 AI Security token";

    state.configured = Boolean(settings.apiUrl && settings.apiKey);
    updateConnectionStatus(settings);
  } catch {
    updateConnectionStatus({});
  }
}

function showView(viewName) {
  elements.navLinks.forEach((button) => {
    button.classList.toggle("active", button.dataset.viewTarget === viewName);
  });

  elements.views.forEach((view) => {
    view.classList.toggle("active", view.dataset.view === viewName);
  });
}

function updateConnectionStatus(settings) {
  const isConfigured = state.configured;
  elements.connectionStatus.textContent = isConfigured ? "Ready" : "Not configured";
  elements.connectionHint.textContent = isConfigured
    ? `${settings.modelName || "Model"} via saved endpoint`
    : "Add your API URL and key in Settings to start chatting.";
}

async function handleSettingsSave(event) {
  event.preventDefault();

  const payload = {
    apiUrl: elements.apiUrl.value.trim(),
    modelName: elements.modelName.value.trim() || "gpt-4o-mini",
    calypsoEnabled: elements.calypsoEnabled.checked,
    calypsoUrl: elements.calypsoUrl.value.trim(),
  };

  // Only send the key if the user typed a new one
  const keyValue = elements.apiKey.value.trim();
  if (keyValue) {
    payload.apiKey = keyValue;
  }

  // Only send the token if the user typed a new one
  const tokenValue = elements.calypsoToken.value.trim();
  if (tokenValue) {
    payload.calypsoToken = tokenValue;
  }

  try {
    const response = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();

    if (response.ok) {
      elements.settingsFeedback.textContent = result.message;
      elements.settingsFeedback.className = "settings-feedback success";
      elements.apiKey.value = "";
      elements.apiKey.placeholder = "Key saved on server";
      elements.calypsoToken.value = "";
      elements.calypsoToken.placeholder = "Token saved on server";
      state.configured = true;
      updateConnectionStatus({
        apiUrl: payload.apiUrl,
        apiKey: "saved",
        modelName: payload.modelName,
      });
    } else {
      elements.settingsFeedback.textContent = result.error || "Failed to save.";
      elements.settingsFeedback.className = "settings-feedback error";
    }
  } catch (error) {
    elements.settingsFeedback.textContent = `Network error: ${error.message}`;
    elements.settingsFeedback.className = "settings-feedback error";
  }
}

function handleExportSettings() {
  // Trigger a file download by navigating to the export endpoint
  const link = document.createElement("a");
  link.href = "/api/settings/export";
  link.download = "ai-assistant-config.json";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

async function handleImportSettings() {
  const file = elements.importFileInput.files[0];
  if (!file) return;

  try {
    const text = await file.text();
    const data = JSON.parse(text);
    const llm = data.llm || {};
    const f5 = data.f5_ai_security || {};
    const mask = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022";

    // Populate LLM fields
    if (llm.apiUrl) {
      elements.apiUrl.value = llm.apiUrl;
    }
    if (llm.apiKey && llm.apiKey !== mask) {
      elements.apiKey.value = llm.apiKey;
    }
    if (llm.modelName) {
      elements.modelName.value = llm.modelName;
    }

    // Populate F5 AI Security fields
    elements.calypsoEnabled.checked = Boolean(f5.enabled);
    elements.calypsoFields.classList.toggle("hidden", !elements.calypsoEnabled.checked);
    if (f5.url) {
      elements.calypsoUrl.value = f5.url;
    }
    if (f5.token && f5.token !== mask) {
      elements.calypsoToken.value = f5.token;
    }

    // Also save to the server session immediately
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("/api/settings/import", {
      method: "POST",
      body: formData,
    });
    const result = await response.json();

    if (response.ok) {
      elements.settingsFeedback.textContent = "Configuration imported — review the fields and click Save if needed.";
      elements.settingsFeedback.className = "settings-feedback success";
      state.configured = Boolean(elements.apiUrl.value && (elements.apiKey.value || result.hasApiKey));
      updateConnectionStatus({ modelName: elements.modelName.value, apiUrl: elements.apiUrl.value, apiKey: "saved" });
    } else {
      elements.settingsFeedback.textContent = result.error || "Import failed.";
      elements.settingsFeedback.className = "settings-feedback error";
    }
  } catch (error) {
    elements.settingsFeedback.textContent = `Import error: ${error.message}`;
    elements.settingsFeedback.className = "settings-feedback error";
  }

  // Reset so the same file can be re-imported
  elements.importFileInput.value = "";
}

function handleClearChat() {
  state.messages = [];
  elements.chatThread.innerHTML = "";
}

async function handleChatSubmit(event) {
  event.preventDefault();

  const prompt = elements.messageInput.value.trim();
  if (!prompt) return;

  if (!state.configured) {
    showView("settings");
    elements.settingsFeedback.textContent =
      "Please add your API URL and key before sending a message.";
    elements.settingsFeedback.className = "settings-feedback error";
    return;
  }

  const userMessage = { role: "user", content: prompt };
  state.messages.push(userMessage);
  appendMessage(userMessage);
  elements.messageInput.value = "";
  setSending(true);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: state.messages.map(({ role, content }) => ({ role, content })),
        ragEnabled: elements.ragEnabled.checked,
      }),
    });

    const result = await response.json();

    if (response.ok) {
      const assistantMessage = { role: "assistant", content: result.content };
      state.messages.push(assistantMessage);
      appendMessage(assistantMessage);
    } else {
      appendMessage({
        role: "assistant",
        content: `Error: ${result.error}`,
      });
    }
  } catch (error) {
    appendMessage({
      role: "assistant",
      content: `Request failed: ${error.message}`,
    });
  } finally {
    setSending(false);
  }
}

function appendMessage(message) {
  const article = document.createElement("article");
  article.className = `message ${message.role}`;

  const role = document.createElement("p");
  role.className = "message-role";
  role.textContent = message.role;

  const body = document.createElement("div");
  body.className = "message-body";

  if (message.role === "assistant" && typeof marked !== "undefined") {
    body.innerHTML = marked.parse(message.content);
  } else {
    body.textContent = message.content;
  }

  article.append(role, body);
  elements.chatThread.append(article);
  elements.chatThread.scrollTop = elements.chatThread.scrollHeight;
}

function setSending(isSending) {
  elements.sendButton.disabled = isSending;
  elements.sendButton.textContent = isSending ? "Sending..." : "Send message";
}

// ── RAG / Knowledge Base helpers ────────────────────────────────────

async function loadKBDocuments() {
  try {
    const res = await fetch("/api/rag/documents");
    const data = await res.json();
    renderKBDocuments(data.documents || []);
  } catch {
    renderKBDocuments([]);
  }
}

function renderKBDocuments(docs) {
  elements.ragDocCount.textContent = `${docs.length} doc${docs.length !== 1 ? "s" : ""}`;

  if (!docs.length) {
    elements.kbDocuments.innerHTML = '<p class="kb-empty">No documents loaded yet.</p>';
    return;
  }

  elements.kbDocuments.innerHTML = docs
    .map(
      (d) => `
      <div class="kb-doc-card">
        <div class="kb-doc-info">
          <span class="kb-doc-name">${escapeHtml(d.name)}</span>
          <span class="kb-doc-meta">${d.chunk_count} chunk${d.chunk_count !== 1 ? "s" : ""}</span>
        </div>
        <button class="kb-doc-remove" data-doc-id="${d.id}" title="Remove document">&times;</button>
      </div>`
    )
    .join("");

  // Attach delete handlers
  elements.kbDocuments.querySelectorAll(".kb-doc-remove").forEach((btn) => {
    btn.addEventListener("click", () => handleKBDelete(btn.dataset.docId));
  });
}

async function handleKBUpload() {
  const files = elements.kbFileInput.files;
  if (!files || !files.length) return;

  const formData = new FormData();
  for (const f of files) {
    formData.append("files", f);
  }

  elements.kbUploadFeedback.textContent = "Uploading & indexing...";
  elements.kbUploadFeedback.className = "settings-feedback";

  try {
    const res = await fetch("/api/rag/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (res.ok) {
      elements.kbUploadFeedback.textContent = `Uploaded ${data.uploaded.length} file(s).`;
      elements.kbUploadFeedback.className = "settings-feedback success";
      renderKBDocuments(data.documents || []);
    } else {
      elements.kbUploadFeedback.textContent = data.error || "Upload failed.";
      elements.kbUploadFeedback.className = "settings-feedback error";
    }
  } catch (err) {
    elements.kbUploadFeedback.textContent = `Upload error: ${err.message}`;
    elements.kbUploadFeedback.className = "settings-feedback error";
  }

  // Reset the input so the same file can be re-uploaded
  elements.kbFileInput.value = "";
}

async function handleKBDelete(docId) {
  try {
    const res = await fetch(`/api/rag/documents/${docId}`, { method: "DELETE" });
    const data = await res.json();
    if (res.ok) {
      renderKBDocuments(data.documents || []);
    }
  } catch {
    // silent
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
