const BASE = "http://localhost:8000";

async function request(method, path, body, token) {
  const res = await fetch(BASE + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: "Bearer " + token } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw await res.json();
  }
  return res.json();
}

export const api = {
  login: (data) => request("POST", "/auth/login", data),
  signup: (data) => request("POST", "/auth/signup", data),
  me: (token) => request("GET", "/auth/me", null, token),
};
