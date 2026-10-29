const DEFAULT_TIMEOUT = 45000;
const WARMUP_WINDOW = 40000;

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("aborted", "AbortError"));
    }, { once: true });
  });
}

async function request(path, options = {}) {
  const { method = "GET", params, body, signal, timeout = DEFAULT_TIMEOUT } = options;
  const url = new URL(path, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    }
  }

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeout);
  const onAbort = () => controller.abort();
  if (signal) signal.addEventListener("abort", onAbort, { once: true });

  try {
    const deadline = Date.now() + WARMUP_WINDOW;
    while (true) {
      let response;
      try {
        response = await fetch(url, {
          method,
          signal: controller.signal,
          headers: body === undefined ? {} : { "Content-Type": "application/json" },
          body: body === undefined ? undefined : JSON.stringify(body),
        });
      } catch (err) {
        if (signal?.aborted) throw new DOMException("aborted", "AbortError");
        if (timedOut) throw new ApiError("请求超时，请稍后重试", 0, null);
        throw err;
      }
      if (response.status === 202 && Date.now() < deadline) {
        await sleep(650, controller.signal);
        continue;
      }
      const text = await response.text();
      let payload = null;
      try {
        payload = text ? JSON.parse(text) : null;
      } catch (err) {
        payload = { error: text.slice(0, 200) };
      }
      if (!response.ok) {
        const message = (payload && payload.error) || "请求失败（HTTP " + response.status + "）";
        throw new ApiError(message, response.status, payload);
      }
      return payload;
    }
  } finally {
    clearTimeout(timer);
    if (signal) signal.removeEventListener("abort", onAbort);
  }
}

export const api = {
  get(path, params, options = {}) {
    return request(path, { ...options, params });
  },
  post(path, body, options = {}) {
    return request(path, { ...options, method: "POST", body });
  },
};
