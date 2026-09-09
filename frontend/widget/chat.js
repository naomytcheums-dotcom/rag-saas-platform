/*!
 * Partie 9.3 -- real chat logic running INSIDE the widget iframe
 * (loaded by iframe.html). Talks to the backend directly (same
 * origin as the iframe itself, so no CORS concern here -- see
 * WIDGET_CORS_ALLOWED_ORIGINS for the embedding page's own origin,
 * used only by script.js/config's own cross-origin calls).
 */
(function () {
  "use strict";

  var params = new URLSearchParams(window.location.search);
  var publicKey = params.get("key");
  var messagesEl = document.getElementById("rw-messages");
  var inputEl = document.getElementById("rw-input");
  var sendBtn = document.getElementById("rw-send");
  var closeBtn = document.getElementById("rw-close");
  var nameEl = document.getElementById("rw-name");
  var avatarEl = document.getElementById("rw-avatar");
  var suggestedEl = document.getElementById("rw-suggested");

  var config = null;
  var sessionToken = null;
  var conversationId = null;
  var messageCount = 0;

  function postToParent(type, payload) {
    window.parent.postMessage({ source: "ragwidget-iframe", type: type, payload: payload }, "*");
  }

  function addBubble(role, text) {
    var el = document.createElement("div");
    el.className = "rw-bubble " + role;
    el.textContent = text;
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
  }

  function showError(message) {
    var el = document.createElement("div");
    el.className = "rw-error";
    el.textContent = message;
    messagesEl.appendChild(el);
    postToParent("error", { message: message });
  }

  function applyConfig(cfg) {
    document.documentElement.setAttribute("data-rw-theme", cfg.theme || "auto");
    var vars = document.createElement("style");
    vars.textContent =
      ":root{--widget-primary:" + cfg.colors.primary + ";--widget-secondary:" + cfg.colors.secondary +
      ";--widget-text:" + cfg.colors.text + ";--widget-bg:" + cfg.colors.background +
      ";--widget-header-bg:" + cfg.colors.header_background + ";--widget-radius:" + cfg.border_radius +
      ";--widget-font:" + cfg.font_family + ";}";
    document.head.appendChild(vars);
    if (cfg.custom_css) {
      var custom = document.createElement("style");
      custom.textContent = cfg.custom_css;
      document.head.appendChild(custom);
    }

    nameEl.textContent = cfg.name || "Assistant";
    if (cfg.avatar_url) {
      avatarEl.innerHTML = '<img src="' + cfg.avatar_url + '" alt="">';
    } else {
      avatarEl.className = "rw-avatar-fallback";
      avatarEl.textContent = (cfg.name || "A").trim().charAt(0).toUpperCase();
    }

    if (cfg.welcome_message) {
      var welcome = document.createElement("div");
      welcome.className = "rw-welcome";
      welcome.textContent = cfg.welcome_message;
      messagesEl.appendChild(welcome);
    }

    (cfg.suggested_questions || []).forEach(function (q) {
      var chip = document.createElement("button");
      chip.className = "rw-chip";
      chip.type = "button";
      chip.textContent = q.label || q.question;
      chip.addEventListener("click", function () { sendMessage(q.question); });
      suggestedEl.appendChild(chip);
    });
  }

  function startSession() {
    return fetch("/widget/session", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ public_key: publicKey }),
    }).then(function (res) { return res.json(); }).then(function (data) {
      sessionToken = data.session_token;
    });
  }

  function sendMessage(text) {
    if (!text || !sessionToken) return;
    if (messageCount >= (config.max_messages || 50)) {
      showError("Message limit reached for this session.");
      return;
    }
    messageCount += 1;
    addBubble("user", text);
    inputEl.value = "";
    sendBtn.disabled = true;

    fetch("/widget/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + sessionToken },
      body: JSON.stringify({ message: text, conversation_id: conversationId }),
    })
      .then(function (res) {
        if (!res.ok) return res.json().then(function (b) { throw new Error(b.detail || "Chat request failed"); });
        return res.json();
      })
      .then(function (data) {
        conversationId = data.conversation_id;
        addBubble("assistant", data.response);
        postToParent("message:received", data);
      })
      .catch(function (err) { showError(err.message); })
      .finally(function () { sendBtn.disabled = false; });
  }

  sendBtn.addEventListener("click", function () { sendMessage(inputEl.value.trim()); });
  inputEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter") sendMessage(inputEl.value.trim());
  });
  closeBtn.addEventListener("click", function () { window.parent.postMessage({ type: "ragwidget:close" }, "*"); });

  window.addEventListener("message", function (event) {
    var data = event.data;
    if (data && data.type === "ragwidget:send") sendMessage(data.message);
  });

  if (!publicKey) {
    showError("Missing widget key");
  } else {
    fetch("/widget/config?key=" + encodeURIComponent(publicKey))
      .then(function (res) { return res.json(); })
      .then(function (cfg) {
        config = cfg;
        applyConfig(cfg);
        return startSession();
      })
      .catch(function (err) { showError(err.message); });
  }
})();
