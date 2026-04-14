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
  apiUrl: document.querySelector("#api-url"),
  apiKey: document.querySelector("#api-key"),
  modelName: document.querySelector("#model-name"),
  calypsoUrl: document.querySelector("#calypso-url"),
  calypsoToken: document.querySelector("#calypso-token"),
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
  elements.chatForm.addEventListener("submit", handleChatSubmit);

  // Load settings from server session
  await loadSettings();
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

  const body = document.createElement("p");
  body.textContent = message.content;

  article.append(role, body);
  elements.chatThread.append(article);
  elements.chatThread.scrollTop = elements.chatThread.scrollHeight;
}

function setSending(isSending) {
  elements.sendButton.disabled = isSending;
  elements.sendButton.textContent = isSending ? "Sending..." : "Send message";
}
