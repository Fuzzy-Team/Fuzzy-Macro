(function () {
  const handlers = new Map();
  const PYWEBVIEW_READY_TIMEOUT_MS = 15000;

  function hasPywebviewApi() {
    return !!(window.pywebview && window.pywebview.api);
  }

  async function getPywebviewApi() {
    if (hasPywebviewApi()) {
      return window.pywebview.api;
    }

    if (window.__appBridgePywebviewWaiter) {
      return window.__appBridgePywebviewWaiter;
    }

    // Prefer the native pywebviewready event, but keep polling for older or
    // slower backends where the bridge appears asynchronously.
    window.__appBridgePywebviewWaiter = new Promise((resolve) => {
      const intervalMs = 100;
      const timeoutMs = PYWEBVIEW_READY_TIMEOUT_MS;
      let elapsed = 0;
      let settled = false;

      const finish = (api) => {
        if (settled) {
          return;
        }
        settled = true;
        window.removeEventListener("pywebviewready", onReady);
        clearInterval(poll);
        resolve(api);
      };

      const onReady = () => {
        finish(hasPywebviewApi() ? window.pywebview.api : null);
      };

      window.addEventListener("pywebviewready", onReady, { once: true });

      const poll = setInterval(() => {
        if (hasPywebviewApi()) {
          finish(window.pywebview.api);
          return;
        }
        elapsed += intervalMs;
        if (elapsed >= timeoutMs) {
          finish(
            window.pywebview && window.pywebview.api
              ? window.pywebview.api
              : null
          );
        }
      }, intervalMs);
    });

    return window.__appBridgePywebviewWaiter;
  }

  async function call(method, ...args) {
    const pywebviewApi = await getPywebviewApi();
    if (pywebviewApi && typeof pywebviewApi[method] === "function") {
      return await pywebviewApi[method](...args);
    }

    // No fallback available — pywebview is the only supported backend now
    throw new Error(`Backend method unavailable: ${method}`);
  }

  async function fireAndForget(method, ...args) {
    try {
      return await call(method, ...args);
    } catch (error) {
      console.error(`Backend call failed: ${method}`, error);
      return null;
    }
  }

  function expose(fn, name) {
    const eventName = name || fn.name;
    if (!eventName) {
      throw new Error("AppBridge.expose requires a function name");
    }

    handlers.set(eventName, fn);
    // Keep handler registered for frontend dispatch; do not expose via Eel.
    // Avoid adding global fallbacks.
    return fn;
  }

  function on(eventName, fn) {
    handlers.set(eventName, fn);
    return fn;
  }

  function dispatch(eventName, ...args) {
    const handler = handlers.get(eventName) || window[eventName];
    if (typeof handler !== "function") {
      console.warn(`No frontend handler registered for ${eventName}`);
      return null;
    }

    return handler(...args);
  }

  function backendMode() {
    if (hasPywebviewApi()) {
      return "pywebview";
    }
    return "none";
  }

  window.AppBridge = {
    backendMode,
    call,
    dispatch,
    expose,
    fireAndForget,
    on,
  };
  window.backend = window.AppBridge;
})();
