(function () {
  const handlers = new Map();
  const PYWEBVIEW_READY_TIMEOUT_MS = 5000;

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

    window.__appBridgePywebviewWaiter = new Promise((resolve) => {
      let resolved = false;

      const finish = (api) => {
        if (!resolved) {
          resolved = true;
          resolve(api);
        }
      };

      window.addEventListener(
        "pywebviewready",
        () => finish(window.pywebview?.api || null),
        { once: true }
      );

      setTimeout(() => {
        finish(window.pywebview?.api || null);
      }, PYWEBVIEW_READY_TIMEOUT_MS);
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