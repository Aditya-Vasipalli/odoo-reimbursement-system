const BASE = "http://localhost:8000";

function buildHeaders(token, body) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  if (!(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

function normalizeError(payload, status) {
  if (!payload) {
    return { detail: `Request failed with status ${status}` };
  }
  if (typeof payload === "string") {
    return { detail: payload };
  }
  if (Array.isArray(payload?.detail)) {
    return {
      detail: payload.detail
        .map((item) => `${(item.loc || []).join(".")}: ${item.msg || "Invalid value"}`)
        .join("; "),
    };
  }
  return payload;
}

async function request(method, path, body, token) {
  const response = await fetch(BASE + path, {
    method,
    headers: buildHeaders(token, body),
    body: body ? (body instanceof FormData ? body : JSON.stringify(body)) : undefined,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw normalizeError(payload, response.status);
  }
  return payload;
}

export const api = {
  login: (data) => request("POST", "/auth/login", data),
  signup: (data) => request("POST", "/auth/signup", data),
  me: (token) => request("GET", "/auth/me", null, token),

  createExpense: (data, token) => request("POST", "/expenses", data, token),
  myExpenses: (token) => request("GET", "/expenses/mine", null, token),
  teamExpenses: (token) => request("GET", "/expenses/team", null, token),
  getExpenseDetail: (expenseId, token) => request("GET", `/expenses/${expenseId}`, null, token),
  decideExpense: (expenseId, data, token) => request("PATCH", `/expenses/${expenseId}/approve`, data, token),
  deleteExpense: (expenseId, token) => request("DELETE", `/expenses/${expenseId}`, null, token),

  approvalQueue: (token) => request("GET", "/approvals/queue", null, token),

  countries: () => request("GET", "/currency/countries"),
  convertCurrency: ({ from, to, amount }) => request("GET", `/currency/convert?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&amount=${encodeURIComponent(amount)}`),

  scanReceipt: (file, token) => {
    const formData = new FormData();
    formData.append("file", file);
    return request("POST", "/ocr/scan", formData, token);
  },

  adminUsers: (token) => request("GET", "/admin/users", null, token),
  adminCreateUser: (data, token) => request("POST", "/admin/users", data, token),
  adminUpdateUser: (userId, data, token) => request("PATCH", `/admin/users/${userId}`, data, token),
  adminApprovalRules: (token) => request("GET", "/admin/approval-rules", null, token),
  adminCreateApprovalRule: (data, token) => request("POST", "/admin/approval-rules", data, token),
  adminAnalytics: (token) => request("GET", "/admin/analytics", null, token),
};
