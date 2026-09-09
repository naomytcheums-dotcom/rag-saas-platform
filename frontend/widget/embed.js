/*!
 * RAG SaaS Platform -- embeddable widget client (Partie 9.3.1/9.3.13/9.3.14).
 * Vanilla JS, dependency-free on purpose: this file runs on ARBITRARY
 * third-party sites via a plain <script> tag, so it cannot assume the
 * host page has React/Vue/any bundler available. Served by the
 * backend at both /widget/script.js and /widget/embed.js (same file,
 * two literal URLs the DeepSeek asks name separately -- see
 * api/routers/widget.py's own docstring on that real consolidation).
 *
 * Real security note (vision critique): the ONLY credential this
 * file ever holds is the real, non-secret `public_key` read from its
 * own <script data-key="..."> attribute -- never a real, secret
 * OrganizationAPIKey. See api/security/widget_auth.py's own top
 * docstring for the real two-tier design this implements.
 */
(function () {
  "use strict";

  if (window.RAGWidget && window.RAGWidget.__initialized) return;

  var currentScript = document.currentScript || (function () {
    var scripts = document.getElementsByTagName("script");
    return scripts[scripts.length - 1];
  })();

  var API_BASE = currentScript.getAttribute("data-base-url") || new URL(currentScript.src).origin;
  var PUBLIC_KEY = currentScript.getAttribute("data-key");

  var listeners = {};
  var state = { open: false, config: null, sessionToken: null, iframe: null, launcher: null, ready: false };

  function emit(event, payload) {
    (listeners[event] || []).forEach(function (cb) {
      try { cb(payload); } catch (e) { /* one bad subscriber must not break the others */ }
    });
  }

  function on(event, cb) {
    listeners[event] = listeners[event] || [];
    listeners[event].push(cb);
  }

  function off(event, cb) {
    if (!listeners[event]) return;
    listeners[event] = listeners[event].filter(function (fn) { return fn !== cb; });
  }

  function fetchJSON(path, opts) {
    return fetch(API_BASE + path, opts).then(function (res) {
      if (!res.ok) return res.json().catch(function () { return {}; }).then(function (body) {
        throw new Error((body && body.detail) || ("Request failed: " + res.status));
      });
      return res.json();
    });
  }

  function applyPositionStyle(el, config) {
    var vertical = config.position.indexOf("top") === 0 ? "top" : "bottom";
    var horizontal = config.position.indexOf("left") !== -1 ? "left" : "right";
    el.style.position = "fixed";
    el.style[vertical] = config.offset_y + "px";
    el.style[horizontal] = config.offset_x + "px";
    el.style.zIndex = "2147483000";
  }

  function createLauncher(config) {
    var button = document.createElement("button");
    button.setAttribute("aria-label", config.name || "Open chat");
    button.style.cssText =
      "width:60px;height:60px;border-radius:50%;border:none;cursor:pointer;" +
      "background:" + config.colors.primary + ";color:" + config.colors.text + ";" +
      "box-shadow:0 4px 14px rgba(0,0,0,.2);font-size:26px;";
    button.textContent = "💬";
    applyPositionStyle(button, config);
    button.addEventListener("click", toggle);
    document.body.appendChild(button);
    return button;
  }

  function createIframe(config) {
    var iframe = document.createElement("iframe");
    var params = new URLSearchParams({ key: PUBLIC_KEY });
    iframe.src = API_BASE + "/widget/iframe?" + params.toString();
    iframe.title = config.name || "Chat widget";
    iframe.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms");
    iframe.setAttribute("loading", "lazy");
    iframe.style.cssText =
      "width:min(380px,calc(100vw - 40px));height:min(600px,calc(100vh - 120px));" +
      "border:none;border-radius:" + config.border_radius + ";box-shadow:0 8px 30px rgba(0,0,0,.25);" +
      "display:none;background:" + config.colors.background + ";";
    applyPositionStyle(iframe, config);
    iframe.style[config.position.indexOf("top") === 0 ? "top" : "bottom"] = (config.offset_y + 76) + "px";
    document.body.appendChild(iframe);
    return iframe;
  }

  function open() {
    if (!state.ready || state.open) return;
    state.open = true;
    state.iframe.style.display = "block";
    state.launcher.style.display = "none";
    emit("open");
  }

  function close() {
    if (!state.open) return;
    state.open = false;
    state.iframe.style.display = "none";
    state.launcher.style.display = "flex";
    emit("close");
  }

  function toggle() {
    if (state.open) close(); else open();
  }

  function sendMessage(message) {
    if (!state.iframe) return;
    state.iframe.contentWindow.postMessage({ type: "ragwidget:send", message: message }, "*");
    emit("message:sent", { message: message });
  }

  function updateConfig(partial) {
    state.config = Object.assign({}, state.config, partial);
    if (state.launcher) applyPositionStyle(state.launcher, state.config);
    if (state.iframe) applyPositionStyle(state.iframe, state.config);
    emit("theme:changed", state.config);
  }

  function destroy() {
    window.removeEventListener("message", handleMessage);
    if (state.launcher) state.launcher.remove();
    if (state.iframe) state.iframe.remove();
    state.ready = false;
  }

  function handleMessage(event) {
    var data = event.data;
    if (!data || typeof data !== "object" || data.source !== "ragwidget-iframe") return;
    if (data.type === "message:received") emit("message:received", data.payload);
    else if (data.type === "message:stream") emit("message:stream", data.payload);
    else if (data.type === "error") emit("error", data.payload);
    else if (data.type === "resize" && state.iframe) state.iframe.style.height = data.payload.height + "px";
  }

  function init(overrides) {
    if (!PUBLIC_KEY) {
      emit("error", { message: "Missing data-key attribute on the widget <script> tag" });
      return;
    }
    fetchJSON("/widget/config?key=" + encodeURIComponent(PUBLIC_KEY))
      .then(function (config) {
        state.config = Object.assign({}, config, overrides || {});
        state.launcher = createLauncher(state.config);
        state.iframe = createIframe(state.config);
        window.addEventListener("message", handleMessage);
        state.ready = true;
        emit("ready");
      })
      .catch(function (err) {
        emit("error", { message: err.message });
      });
  }

  window.RAGWidget = {
    __initialized: true,
    init: init, open: open, close: close, toggle: toggle,
    sendMessage: sendMessage, on: on, off: off, destroy: destroy, updateConfig: updateConfig,
  };

  // Auto-init unless the embedding page opts out (data-manual-init="true"),
  // matching the literal script-tag ask's own zero-config default.
  if (currentScript.getAttribute("data-manual-init") !== "true") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () { init(); });
    } else {
      init();
    }
  }
})();
