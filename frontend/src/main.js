import { api } from "./api.js";
import { resetSession, setToken, store } from "./store.js";

const app = document.getElementById("app");
const DEMO_EMAIL = "demo@odoo.local";
const DEMO_PASSWORD = "demo123";
const DEMO_TOKEN = "demo-mode-token";

function normalizeCurrencyOptions(raw) {
  const seen = new Set();
  return (raw || [])
    .map((item) => {
      const code = String(item?.currency_code || "").toUpperCase().trim();
      const country = String(item?.name || "").trim();
      const symbol = String(item?.symbol || "").trim();
      if (!code || seen.has(code)) {
        return null;
      }
      seen.add(code);
      return { code, country, symbol };
    })
    .filter(Boolean)
    .sort((a, b) => a.code.localeCompare(b.code));
}

function seedFallbackCurrencies() {
  const companyCurrency = String(store.company?.currency_code || "USD").toUpperCase();
  const fallback = [
    { code: companyCurrency, country: "Company Currency", symbol: "" },
    { code: "USD", country: "United States", symbol: "$" },
    { code: "INR", country: "India", symbol: "Rs" },
    { code: "EUR", country: "Eurozone", symbol: "EUR" },
    { code: "GBP", country: "United Kingdom", symbol: "GBP" },
    { code: "JPY", country: "Japan", symbol: "JPY" },
  ];
  store.currencyOptions = normalizeCurrencyOptions(fallback);
}

async function loadCurrencyOptions() {
  if (store.currencyOptions.length) {
    return;
  }
  if (store.isDemoMode) {
    seedFallbackCurrencies();
    return;
  }
  try {
    const countries = await api.countries();
    const normalized = normalizeCurrencyOptions(countries);
    if (!normalized.length) {
      seedFallbackCurrencies();
      return;
    }
    store.currencyOptions = normalized;
  } catch {
    seedFallbackCurrencies();
  }
}

function currencyOptionsHtml() {
  const selectedCurrency = String(store.company?.currency_code || "USD").toUpperCase();
  if (!store.currencyOptions.length) {
    return `<option value="${escapeHtml(selectedCurrency)}">${escapeHtml(selectedCurrency)}</option>`;
  }
  return store.currencyOptions
    .map((item) => {
      const selected = item.code === selectedCurrency ? "selected" : "";
      const label = item.symbol
        ? `${item.code} (${item.symbol}) - ${item.country}`
        : `${item.code} - ${item.country}`;
      return `<option value="${escapeHtml(item.code)}" ${selected}>${escapeHtml(label)}</option>`;
    })
    .join("");
}

function categoryOptionsHtml() {
  return store.categories
    .map((category, index) => {
      const selected = index === 0 ? "selected" : "";
      return `<option value="${escapeHtml(category)}" ${selected}>${escapeHtml(category)}</option>`;
    })
    .join("");
}

function managerNameById(managerId) {
  if (!managerId) {
    return "-";
  }
  const manager = store.users.find((user) => Number(user.id) === Number(managerId));
  return manager ? `${manager.name} (#${manager.id})` : `#${managerId}`;
}

function formatQueueAmount(item) {
  const baseCurrency = store.company?.currency_code || "USD";
  const localAmount = formatCurrency(item.amount, item.currency);
  const hasBaseAmount = Number.isFinite(Number(item.amount_in_base));
  const baseAmount = hasBaseAmount
    ? formatCurrency(item.amount_in_base, baseCurrency)
    : "Base amount pending backend";
  return `${localAmount}<br/><span class="muted small-text">Base: ${escapeHtml(baseAmount)}</span>`;
}

function approverOptionsHtml(selectedId = null) {
  return store.users
    .filter((user) => user.role === "manager" || user.role === "admin")
    .map((user) => {
      const isSelected = Number(user.id) === Number(selectedId) ? "selected" : "";
      return `<option value="${user.id}" ${isSelected}>${escapeHtml(user.name)} (#${user.id}) - ${escapeHtml(user.role)}</option>`;
    })
    .join("");
}

function managerOptionsForUser(user) {
  return store.users
    .filter((candidate) => candidate.role === "manager" && Number(candidate.id) !== Number(user.id))
    .map((candidate) => {
      const selected = Number(candidate.id) === Number(user.manager_id) ? "selected" : "";
      return `<option value="${candidate.id}" ${selected}>${escapeHtml(candidate.name)} (#${candidate.id})</option>`;
    })
    .join("");
}

function ruleModeLabel(rule) {
  if (rule.is_hybrid) {
    return "Hybrid";
  }
  if (rule.specific_approver_id) {
    return "Specific Approver";
  }
  if (rule.threshold_pct != null) {
    return "Percentage";
  }
  return "Sequential";
}

function renderRuleRows() {
  if (!store.approvalRules.length) {
    return '<tr><td colspan="6" class="muted">No approval rules configured yet.</td></tr>';
  }

  return store.approvalRules
    .map((rule) => {
      const stepText = (rule.steps || []).length
        ? rule.steps
            .slice()
            .sort((a, b) => Number(a.step_order) - Number(b.step_order))
            .map((step) => `#${step.approver_id} (S${step.step_order})`)
            .join(", ")
        : "-";
      return `
        <tr>
          <td>${escapeHtml(rule.name)}</td>
          <td>${escapeHtml(ruleModeLabel(rule))}</td>
          <td>${rule.threshold_pct != null ? `${rule.threshold_pct}%` : "-"}</td>
          <td>${rule.specific_approver_id ?? "-"}</td>
          <td>${rule.is_manager_first ? "Yes" : "No"}</td>
          <td>${escapeHtml(stepText)}</td>
        </tr>
      `;
    })
    .join("");
}

function receiptEvidenceHtml(expense) {
  const receiptUrl = String(expense?.receipt_url || "").trim();
  if (!receiptUrl) {
    return '<p class="muted">No receipt link available yet. If employee used OCR upload without storage, backend must persist the file URL.</p>';
  }
  const isImage = /\.(png|jpg|jpeg|gif|webp|bmp|svg)(\?|#|$)/i.test(receiptUrl);
  return `
    <div class="receipt-box">
      <a class="receipt-link" href="${escapeHtml(receiptUrl)}" target="_blank" rel="noopener noreferrer">Open receipt evidence</a>
      ${
        isImage
          ? `<img class="receipt-preview" src="${escapeHtml(receiptUrl)}" alt="Receipt preview" />`
          : '<p class="muted">Preview unavailable for this file type. Use the link to open.</p>'
      }
    </div>
  `;
}

function buildDemoSession() {
  const today = new Date().toISOString().slice(0, 10);
  return {
    user: {
      id: 1,
      company_id: 1,
      name: "Demo Admin",
      email: DEMO_EMAIL,
      role: "admin",
      manager_id: null,
      created_at: new Date().toISOString(),
    },
    company: {
      id: 1,
      name: "Odoo Demo Co",
      country_code: "IN",
      currency_code: "INR",
      created_at: new Date().toISOString(),
    },
    expenses: [
      {
        id: 101,
        employee_id: 2,
        amount: 1800,
        currency: "INR",
        amount_in_base: 1800,
        category: "Travel",
        description: "Airport transfer",
        date: today,
        receipt_url: null,
        status: "pending",
        current_step_order: 0,
        created_at: new Date().toISOString(),
      },
    ],
    queue: [
      {
        expense_id: 101,
        step_order: 0,
        status: "pending",
        created_at: new Date().toISOString(),
        amount: 1800,
        currency: "INR",
        category: "Travel",
        date: today,
        employee_id: 2,
        employee_name: "Demo Employee",
      },
    ],
    users: [
      {
        id: 1,
        company_id: 1,
        name: "Demo Admin",
        email: DEMO_EMAIL,
        role: "admin",
        manager_id: null,
        created_at: new Date().toISOString(),
      },
      {
        id: 2,
        company_id: 1,
        name: "Demo Employee",
        email: "employee@odoo.local",
        role: "employee",
        manager_id: 3,
        created_at: new Date().toISOString(),
      },
      {
        id: 3,
        company_id: 1,
        name: "Demo Manager",
        email: "manager@odoo.local",
        role: "manager",
        manager_id: null,
        created_at: new Date().toISOString(),
      },
    ],
    analytics: {
      total_pending: 1,
      total_approved: 0,
      total_rejected: 0,
      by_category: [{ category: "Travel", total: 1800 }],
      top_spenders: [{ name: "Demo Employee", total: 1800 }],
    },
  };
}

function enterDemoMode() {
  const demo = buildDemoSession();
  setToken(DEMO_TOKEN);
  store.isDemoMode = true;
  seedFallbackCurrencies();
  store.demoDecisionByExpense = {};
  store.user = demo.user;
  store.company = demo.company;
  store.expenses = demo.expenses;
  store.queue = demo.queue;
  store.users = demo.users;
  store.analytics = demo.analytics;
  store.approvalRules = [
    {
      id: 1,
      company_id: 1,
      name: "Default Hybrid Rule",
      threshold_pct: 60,
      specific_approver_id: 3,
      is_hybrid: true,
      is_manager_first: true,
      created_at: new Date().toISOString(),
      steps: [
        { approver_id: 3, step_order: 1 },
        { approver_id: 1, step_order: 2 },
      ],
    },
  ];
  store.currentView = "dashboard";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatCurrency(amount, currency) {
  const safeAmount = Number.isFinite(Number(amount)) ? Number(amount) : 0;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: (currency || "USD").toUpperCase(),
      maximumFractionDigits: 2,
    }).format(safeAmount);
  } catch {
    return `${safeAmount.toFixed(2)} ${(currency || "USD").toUpperCase()}`;
  }
}

function toast(kind, message) {
  store.toast = { kind, message };
  render();
  window.setTimeout(() => {
    if (store.toast?.message === message) {
      store.toast = null;
      render();
    }
  }, 2800);
}

function setView(view) {
  store.currentView = view;
  render();
}

function apiMessage(error) {
  return error?.detail || "Something went wrong. Please try again.";
}

function setInlineHint(id, message, tone = "muted") {
  const node = document.querySelector(`#${id}`);
  if (!node) {
    return;
  }
  node.textContent = message;
  node.className = `inline-hint ${tone}`;
}

function isPrivileged() {
  return store.user?.role === "admin" || store.user?.role === "manager";
}

async function bootstrapSession() {
  if (!store.token) {
    setView("login");
    return;
  }
  if (store.token === DEMO_TOKEN) {
    enterDemoMode();
    render();
    return;
  }
  try {
    const me = await api.me(store.token);
    store.user = me.user;
    store.company = me.company;
    await loadCurrencyOptions();
    store.currentView = "dashboard";
    await hydrateDashboard();
    render();
  } catch {
    resetSession();
    toast("error", "Session expired. Please login again.");
    render();
  }
}

async function hydrateDashboard() {
  if (store.isDemoMode || !store.token) {
    return;
  }
  try {
    await loadCurrencyOptions();
    const [expenses, queue, analytics, users, approvalRules] = await Promise.all([
      api.myExpenses(store.token),
      isPrivileged() ? api.approvalQueue(store.token) : Promise.resolve([]),
      store.user?.role === "admin" ? api.adminAnalytics(store.token) : Promise.resolve(null),
      store.user?.role === "admin" ? api.adminUsers(store.token) : Promise.resolve([]),
      store.user?.role === "admin" ? api.adminApprovalRules(store.token) : Promise.resolve([]),
    ]);
    store.expenses = expenses;
    store.queue = queue;
    store.analytics = analytics;
    store.users = users;
    store.approvalRules = approvalRules;
  } catch (error) {
    toast("error", apiMessage(error));
  }
}

async function doLogin(formData) {
  const email = String(formData.get("email") || "").trim().toLowerCase();
  const password = String(formData.get("password") || "");

  try {
    const response = await api.login({
      email,
      password,
    });
    setToken(response.token);
    store.user = response.user;
    store.company = response.company;
    await loadCurrencyOptions();
    store.currentView = "dashboard";
    await hydrateDashboard();
    toast("success", "Welcome back.");
    render();
  } catch (error) {
    if (email === DEMO_EMAIL && password === DEMO_PASSWORD) {
      enterDemoMode();
      toast("success", "Demo mode active. Backend not required.");
      render();
      return;
    }
    toast("error", apiMessage(error));
  }
}

async function doSignup(formData) {
  try {
    const payload = {
      name: formData.get("name"),
      email: formData.get("email"),
      password: formData.get("password"),
      country_code: formData.get("country_code") || "IN",
      company_name: formData.get("company_name") || null,
    };
    const response = await api.signup(payload);
    setToken(response.token);
    store.user = response.user;
    store.company = response.company;
    await loadCurrencyOptions();
    store.currentView = "dashboard";
    await hydrateDashboard();
    toast("success", "Account created successfully.");
    render();
  } catch (error) {
    toast("error", apiMessage(error));
  }
}

async function doCreateExpense(formData) {
  const amount = Number(formData.get("amount"));
  const currency = String(formData.get("currency") || "USD").toUpperCase();
  const category = String(formData.get("category") || "").trim();
  const description = String(formData.get("description") || "").trim();
  const date = formData.get("date");
  const receiptUrl = String(formData.get("receipt_url") || "").trim();
  const receiptFile = document.querySelector("#receipt-file")?.files?.[0] || null;

  if (!Number.isFinite(amount) || amount <= 0 || !category || !description || !date) {
    toast("error", "Please complete all required expense fields.");
    return;
  }

  if (!receiptUrl && !receiptFile) {
    setInlineHint("ocr-hint", "Attach a receipt image for OCR or paste a Drive receipt URL.", "error");
    toast("error", "Receipt proof is required (OCR file or Drive link).");
    return;
  }

  if (!store.isDemoMode && !receiptUrl) {
    setInlineHint(
      "ocr-hint",
      "For approval visibility, paste a Drive/hosted receipt URL. OCR upload alone is not yet persisted by backend.",
      "warn"
    );
    toast("error", "Receipt URL is required for live submissions until backend file storage is enabled.");
    return;
  }

  const payload = {
    amount,
    currency,
    category,
    description,
    date,
    receipt_url: receiptUrl || null,
  };

  if (store.isDemoMode) {
    const nextId = (store.expenses.at(-1)?.id || 100) + 1;
    const expense = {
      id: nextId,
      employee_id: store.user?.id || 1,
      amount,
      currency,
      amount_in_base: amount,
      category,
      description,
      date,
      receipt_url: payload.receipt_url,
      status: "pending",
      current_step_order: 0,
      created_at: new Date().toISOString(),
    };
    store.expenses = [expense, ...store.expenses];
    store.queue = [
      {
        expense_id: expense.id,
        step_order: 0,
        status: "pending",
        created_at: new Date().toISOString(),
        amount: expense.amount,
        currency: expense.currency,
        category: expense.category,
        date: expense.date,
        employee_id: expense.employee_id,
        employee_name: store.user?.name || "Demo User",
      },
      ...store.queue,
    ];
    store.analytics = {
      ...(store.analytics || {}),
      total_pending: (store.analytics?.total_pending || 0) + 1,
      total_approved: store.analytics?.total_approved || 0,
      total_rejected: store.analytics?.total_rejected || 0,
      by_category: store.analytics?.by_category || [],
      top_spenders: store.analytics?.top_spenders || [],
    };
    toast("success", "Expense submitted (demo mode).");
    store.currentView = "history";
    render();
    return;
  }

  try {
    await api.createExpense(payload, store.token);
    toast("success", "Expense submitted.");
    store.currentView = "history";
    store.expenses = await api.myExpenses(store.token);
    render();
  } catch (error) {
    toast("error", apiMessage(error));
  }
}

async function doScanReceipt(fileInput) {
  const file = fileInput.files?.[0];
  if (!file) {
    toast("error", "Select an image to scan.");
    setInlineHint("ocr-hint", "Upload a clear receipt image before scanning.", "warn");
    return;
  }
  if (store.isDemoMode) {
    const amountInput = document.querySelector("#expense-amount");
    const descInput = document.querySelector("#expense-description");
    if (amountInput && !amountInput.value) {
      amountInput.value = "499.00";
    }
    if (descInput && !descInput.value) {
      descInput.value = "Demo OCR: Business meal";
    }
    setInlineHint("ocr-hint", "Demo OCR filled sample values.", "success");
    toast("success", "Demo OCR completed.");
    return;
  }
  try {
    const data = await api.scanReceipt(file, store.token);
    const amountInput = document.querySelector("#expense-amount");
    const dateInput = document.querySelector("#expense-date");
    const descInput = document.querySelector("#expense-description");
    const currInput = document.querySelector("#expense-currency");

    if (amountInput && data?.amount) {
      amountInput.value = data.amount;
    }
    if (dateInput && data?.date) {
      dateInput.value = data.date;
    }
    if (descInput) {
      const description = data?.vendor || data?.description || "";
      if (description) {
        descInput.value = description;
      }
    }
    if (currInput && data?.currency) {
      currInput.value = String(data.currency).toUpperCase();
    }
    const hasExtraction = Boolean(data?.amount || data?.date || data?.vendor || data?.description || data?.currency);
    if (!hasExtraction) {
      setInlineHint("ocr-hint", "OCR could not detect reliable fields. Please enter details manually.", "warn");
      toast("error", "OCR returned no usable fields.");
      return;
    }
    setInlineHint("ocr-hint", "Receipt fields extracted. Review values before submitting.", "success");
    toast("success", "Receipt scanned. Please review extracted fields.");
  } catch (error) {
    setInlineHint("ocr-hint", "OCR service unavailable right now. Use manual entry.", "error");
    toast("error", apiMessage(error));
  }
}

async function doConvertCurrency(formData) {
  const from = String(formData.get("currency") || "").toUpperCase();
  const amount = Number(formData.get("amount"));
  const to = store.company?.currency_code || "USD";

  if (!from || !Number.isFinite(amount) || amount <= 0) {
    toast("error", "Enter amount and source currency before conversion.");
    return;
  }

  if (store.isDemoMode) {
    const label = document.querySelector("#converted-preview");
    if (label) {
      label.textContent = `${formatCurrency(amount, to)} at rate 1.00`;
    }
    setInlineHint("currency-hint", "Demo conversion uses fixed rate 1.00.", "success");
    toast("success", "Demo currency conversion complete.");
    return;
  }

  try {
    const result = await api.convertCurrency({ from, to, amount });
    const label = document.querySelector("#converted-preview");
    if (label) {
      label.textContent = `${formatCurrency(result.converted_amount, to)} at rate ${result.rate}`;
    }
    setInlineHint("currency-hint", "Live conversion fetched successfully.", "success");
    toast("success", "Currency converted.");
  } catch (error) {
    setInlineHint("currency-hint", "Live conversion unavailable. Submission will continue with entered amount.", "warn");
    toast("error", apiMessage(error));
  }
}

async function doCreateAdminUser(formData) {
  const role = String(formData.get("role") || "employee");
  const rawManagerId = formData.get("manager_id");
  const payload = {
    name: String(formData.get("name") || "").trim(),
    email: String(formData.get("email") || "").trim(),
    password: String(formData.get("password") || ""),
    role,
    manager_id: role === "employee" && rawManagerId ? Number(rawManagerId) : null,
  };

  if (!payload.name || !payload.email || payload.password.length < 6) {
    toast("error", "Provide valid name, email, and password (min 6 chars).");
    return;
  }

  if (store.isDemoMode) {
    const nextId = (store.users.at(-1)?.id || 3) + 1;
    store.users = [
      ...store.users,
      {
        id: nextId,
        company_id: store.company?.id || 1,
        name: payload.name,
        email: payload.email,
        role: payload.role,
        manager_id: payload.manager_id,
        created_at: new Date().toISOString(),
      },
    ];
    toast("success", "User created in demo mode.");
    render();
    return;
  }

  try {
    await api.adminCreateUser(payload, store.token);
    store.users = await api.adminUsers(store.token);
    toast("success", "User created successfully.");
    render();
  } catch (error) {
    toast("error", apiMessage(error));
  }
}

async function doUpdateUser(userId, role, managerId) {
  const payload = {
    role,
    manager_id: role === "employee" && managerId ? Number(managerId) : null,
  };

  if (store.isDemoMode) {
    store.users = store.users.map((user) => (Number(user.id) === Number(userId) ? { ...user, ...payload } : user));
    toast("success", "User role/manager updated in demo mode.");
    render();
    return;
  }

  try {
    await api.adminUpdateUser(userId, payload, store.token);
    store.users = await api.adminUsers(store.token);
    toast("success", "User updated successfully.");
    render();
  } catch (error) {
    toast("error", apiMessage(error));
  }
}

async function doCreateApprovalRule(formData) {
  const name = String(formData.get("name") || "").trim();
  const thresholdRaw = String(formData.get("threshold") || "").trim();
  const specificApproverRaw = String(formData.get("specific_approver_id") || "").trim();
  const isHybrid = formData.get("is_hybrid") === "on";
  const isManagerFirst = formData.get("is_manager_first") === "on";
  const stepsRaw = String(formData.get("steps") || "").trim();

  if (!name) {
    toast("error", "Approval rule name is required.");
    return;
  }

  const threshold = thresholdRaw ? Number(thresholdRaw) : null;
  if (threshold != null && (!Number.isFinite(threshold) || threshold < 1 || threshold > 100)) {
    toast("error", "Threshold must be between 1 and 100.");
    return;
  }

  const specificApproverId = specificApproverRaw ? Number(specificApproverRaw) : null;
  if (specificApproverRaw && !Number.isFinite(specificApproverId)) {
    toast("error", "Specific approver must be a valid user ID.");
    return;
  }

  const parsedSteps = stepsRaw
    ? stepsRaw
        .split(",")
        .map((chunk) => Number(chunk.trim()))
        .filter((id) => Number.isFinite(id) && id > 0)
        .map((id, index) => ({ approver_id: id, order: index + 1 }))
    : [];

  const payload = {
    name,
    threshold,
    specific_approver_id: specificApproverId,
    is_hybrid: isHybrid,
    is_manager_first: isManagerFirst,
    steps: parsedSteps,
  };

  if (store.isDemoMode) {
    const nextId = (store.approvalRules.at(-1)?.id || 0) + 1;
    store.approvalRules = [
      ...store.approvalRules,
      {
        id: nextId,
        company_id: store.company?.id || 1,
        name,
        threshold_pct: threshold,
        specific_approver_id: specificApproverId,
        is_hybrid: isHybrid,
        is_manager_first: isManagerFirst,
        created_at: new Date().toISOString(),
        steps: parsedSteps.map((step) => ({ approver_id: step.approver_id, step_order: step.order })),
      },
    ];
    toast("success", "Approval rule created in demo mode.");
    render();
    return;
  }

  try {
    await api.adminCreateApprovalRule(payload, store.token);
    store.approvalRules = await api.adminApprovalRules(store.token);
    toast("success", "Approval rule created successfully.");
    render();
  } catch (error) {
    toast("error", apiMessage(error));
  }
}

async function doApprove(expenseId, action) {
  const entered = window.prompt(`Comment for ${action}:`, "") || "";
  const comment = entered.trim();
  if (action === "rejected" && !comment) {
    toast("error", "Rejection reason is required.");
    return;
  }
  const finalComment = comment || `Marked as ${action}.`;
  if (store.isDemoMode) {
    store.demoDecisionByExpense[expenseId] = {
      action,
      comment: finalComment,
      actor_name: store.user?.name || "Approver",
      acted_at: new Date().toISOString(),
    };
    store.queue = store.queue.filter((item) => Number(item.expense_id) !== Number(expenseId));
    store.expenses = store.expenses.map((item) =>
      Number(item.id) === Number(expenseId) ? { ...item, status: action } : item
    );
    if (store.analytics) {
      store.analytics.total_pending = Math.max((store.analytics.total_pending || 1) - 1, 0);
      if (action === "approved") {
        store.analytics.total_approved = (store.analytics.total_approved || 0) + 1;
      }
      if (action === "rejected") {
        store.analytics.total_rejected = (store.analytics.total_rejected || 0) + 1;
      }
    }
    toast("success", `Expense ${action} (demo mode).`);
    render();
    return;
  }
  try {
    await api.decideExpense(expenseId, { action, comment: finalComment }, store.token);
    store.queue = await api.approvalQueue(store.token);
    if (store.currentView === "history") {
      store.expenses = await api.myExpenses(store.token);
    }
    if (store.user?.role === "admin") {
      store.analytics = await api.adminAnalytics(store.token);
    }
    toast("success", `Expense ${action}.`);
    render();
  } catch (error) {
    toast("error", apiMessage(error));
  }
}

async function doLoadExpenseDetail(expenseId) {
  if (store.isDemoMode) {
    const item = store.expenses.find((expense) => Number(expense.id) === Number(expenseId));
    if (!item) {
      toast("error", "Expense not found.");
      return;
    }
    const decision = store.demoDecisionByExpense[expenseId] || null;
    store.selectedExpense = {
      ...item,
      approval_steps: [
        {
          id: 1,
          approver_id: 3,
          step_order: 0,
          status: item.status,
          comment: decision?.comment || null,
          acted_at: decision?.acted_at || null,
        },
      ],
      audit_logs: [
        {
          id: 1,
          actor_id: item.employee_id,
          action: "submitted",
          comment: "Demo submitted",
          created_at: item.created_at,
        },
        ...(decision
          ? [
              {
                id: 2,
                actor_id: store.user?.id || 1,
                action: decision.action,
                comment: decision.comment,
                created_at: decision.acted_at,
              },
            ]
          : []),
      ],
    };
    render();
    return;
  }
  try {
    store.selectedExpense = await api.getExpenseDetail(expenseId, store.token);
    render();
  } catch (error) {
    toast("error", apiMessage(error));
  }
}

function doLogout() {
  resetSession();
  toast("success", "You have been logged out.");
  render();
}

function authView() {
  return `
    <section class="auth-panel">
      <div class="brand-wrap">
        <h1>FlowFund</h1>
        <p>Expense approvals without spreadsheet chaos.</p>
      </div>
      <div class="auth-cards">
        <form id="login-form" class="card form-card">
          <h2>Login</h2>
          <label>Email<input name="email" type="email" required placeholder="you@company.com" /></label>
          <label>Password<input name="password" type="password" required minlength="6" /></label>
          <button type="submit" class="btn btn-primary" style="margin-top:0.5rem;">Sign In</button>
          <p class="muted" style="margin:0.5rem 0 0; font-size:0.82rem;">Offline demo: ${DEMO_EMAIL} / ${DEMO_PASSWORD}</p>
          <button type="button" id="demo-login-btn" class="btn" style="margin-top:0.5rem;">Use Demo Login</button>
          <p class="muted" style="margin:0.6rem 0 0; font-size:0.82rem;">Admin account creation has been disabled on this page.</p>
        </form>
      </div>
    </section>
  `;
}

function navTabs() {
  const tabs = [
    { key: "dashboard", label: "Dashboard" },
    { key: "submit", label: "Submit Expense" },
    { key: "history", label: "My Expenses" },
  ];

  if (isPrivileged()) {
    tabs.push({ key: "queue", label: "Approval Queue" });
  }
  if (store.user?.role === "admin") {
    tabs.push({ key: "admin", label: "Admin" });
  }

  return tabs
    .map(
      (tab) =>
        `<button data-nav="${tab.key}" class="tab ${store.currentView === tab.key ? "active" : ""}">${tab.label}</button>`
    )
    .join("");
}

function dashboardView() {
  const pending = store.expenses.filter((item) => item.status === "pending").length;
  const approved = store.expenses.filter((item) => item.status === "approved").length;
  const rejected = store.expenses.filter((item) => item.status === "rejected").length;

  return `
    <section class="grid-3">
      <article class="card metric"><p>Pending</p><h3>${pending}</h3></article>
      <article class="card metric"><p>Approved</p><h3>${approved}</h3></article>
      <article class="card metric"><p>Rejected</p><h3>${rejected}</h3></article>
    </section>
    <section class="card">
      <h3>Welcome, ${escapeHtml(store.user?.name || "")}</h3>
      <p>
        Company: <strong>${escapeHtml(store.company?.name || "-")}</strong>
        | Role: <strong>${escapeHtml(store.user?.role || "-")}</strong>
        | Base currency: <strong>${escapeHtml(store.company?.currency_code || "USD")}</strong>
      </p>
      <p>Use the tabs above to submit an expense, review history, and process approvals.</p>
    </section>
  `;
}

function submitView() {
  return `
    <section class="card form-card">
      <h3>Submit Expense</h3>
      <form id="expense-form" class="grid-form">
        <label>Amount<input id="expense-amount" name="amount" type="number" step="0.01" required /></label>
        <label>Currency
          <select id="expense-currency" name="currency" required>
            ${currencyOptionsHtml()}
          </select>
        </label>
        <label>Category
          <select name="category" required>
            ${categoryOptionsHtml()}
          </select>
        </label>
        <label>Date<input id="expense-date" name="date" type="date" required /></label>
        <label class="span-2">Description<textarea id="expense-description" name="description" rows="3" required></textarea></label>
        <label class="span-2">Receipt URL<input name="receipt_url" type="url" placeholder="Optional hosted receipt URL" /></label>
        <div class="span-2 split-row">
          <label class="grow">Receipt Scan Image<input id="receipt-file" type="file" accept="image/*" /></label>
          <button id="scan-receipt" type="button" class="btn">Scan OCR</button>
        </div>
        <p id="ocr-hint" class="inline-hint muted span-2">For live approvals, include a Drive/hosted receipt URL so approvers can open proof.</p>
        <div class="span-2 split-row">
          <button id="convert-btn" type="button" class="btn">Preview Base Currency</button>
          <span id="converted-preview" class="muted">Converted value will appear here.</span>
        </div>
        <p id="currency-hint" class="inline-hint muted span-2">Live conversion is best-effort and not mandatory.</p>
        <button class="btn btn-primary span-2" type="submit">Submit Expense</button>
      </form>
    </section>
  `;
}

function renderExpenseRows(expenses) {
  if (!expenses.length) {
    return `<tr><td colspan="7" class="muted">No expenses yet.</td></tr>`;
  }

  return expenses
    .map(
      (item) => `
        <tr>
          <td>#${item.id}</td>
          <td>${escapeHtml(item.category)}</td>
          <td>${formatCurrency(item.amount, item.currency)}</td>
          <td>${item.date}</td>
          <td><span class="badge ${item.status}">${item.status}</span></td>
          <td>${formatCurrency(item.amount_in_base, store.company?.currency_code || "USD")}</td>
          <td><button class="link-btn" data-detail="${item.id}">View</button></td>
        </tr>
      `
    )
    .join("");
}

function historyView() {
  const detail = store.selectedExpense;
  const detailSteps = (detail?.approval_steps || [])
    .map((step) => {
      const stepStatus = step.status || "pending";
      const note = step.comment ? escapeHtml(step.comment) : "No comment provided";
      return `<li><strong>Step ${step.step_order}</strong> - <span class="badge ${escapeHtml(stepStatus)}">${escapeHtml(stepStatus)}</span> - ${note}</li>`;
    })
    .join("");

  const detailAudit = (detail?.audit_logs || [])
    .map((log) => {
      const action = escapeHtml(log.action || "updated");
      const reason = log.comment ? escapeHtml(log.comment) : "No comment";
      return `<li><strong>${action}</strong> - ${reason}</li>`;
    })
    .join("");

  const finalDecision = detail
    ? detail.status === "approved"
      ? "Accepted"
      : detail.status === "rejected"
        ? "Denied"
        : "Pending"
    : "";

  const decisionReason = detail
    ? (detail.audit_logs || []).slice().reverse().find((entry) => ["approved", "rejected", "overridden"].includes(String(entry.action)))
        ?.comment || "No explicit reason captured yet."
    : "";

  return `
    <section class="card">
      <h3>My Expense History</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Category</th>
              <th>Amount</th>
              <th>Date</th>
              <th>Status</th>
              <th>Base Amount</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>${renderExpenseRows(store.expenses)}</tbody>
        </table>
      </div>
    </section>
    ${
      detail
        ? `<section class="card">
            <h4>Expense #${detail.id} Detail</h4>
            <p><strong>Description:</strong> ${escapeHtml(detail.description)}</p>
            <p><strong>Category:</strong> ${escapeHtml(detail.category)} | <strong>Status:</strong> <span class="badge ${detail.status}">${detail.status}</span></p>
            <p><strong>Decision:</strong> ${escapeHtml(finalDecision)} | <strong>Reason:</strong> ${escapeHtml(decisionReason)}</p>
            <div class="detail-block">
              <h5>Receipt Evidence</h5>
              ${receiptEvidenceHtml(detail)}
            </div>
            <div class="detail-block">
              <h5>Approval Steps</h5>
              <ul>${detailSteps || '<li class="muted">No approval steps available.</li>'}</ul>
            </div>
            <div class="detail-block">
              <h5>Audit Trail</h5>
              <ul>${detailAudit || '<li class="muted">No audit logs available.</li>'}</ul>
            </div>
          </section>`
        : ""
    }
  `;
}

function queueView() {
  const detail = store.selectedExpense;
  if (!store.queue.length) {
    return `<section class="card"><h3>Approval Queue</h3><p class="muted">No pending approvals assigned to you.</p></section>`;
  }

  return `
    <section class="card">
      <h3>Approval Queue</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Expense</th>
              <th>Employee</th>
              <th>Category</th>
              <th>Amount</th>
              <th>Step</th>
              <th>Detail</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${store.queue
              .map(
                (item) => `
                  <tr>
                    <td>#${item.expense_id}</td>
                    <td>${escapeHtml(item.employee_name || "-")}</td>
                    <td>${escapeHtml(item.category || "-")}</td>
                    <td>${formatQueueAmount(item)}</td>
                    <td>${item.step_order}</td>
                    <td><button class="link-btn" data-queue-detail="${item.expense_id}">View</button></td>
                    <td class="actions">
                      <button class="btn btn-success" data-approve="${item.expense_id}">Approve</button>
                      <button class="btn btn-danger" data-reject="${item.expense_id}">Reject</button>
                    </td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
    ${
      detail
        ? `<section class="card">
            <h4>Approval Detail for Expense #${detail.id}</h4>
            <p><strong>Description:</strong> ${escapeHtml(detail.description)}</p>
            <p><strong>Category:</strong> ${escapeHtml(detail.category)} | <strong>Status:</strong> <span class="badge ${detail.status}">${detail.status}</span></p>
            <div class="detail-block">
              <h5>Receipt Evidence</h5>
              ${receiptEvidenceHtml(detail)}
            </div>
          </section>`
        : ""
    }
  `;
}

function adminView() {
  const analytics = store.analytics;
  const managerChoices = store.users
    .filter((user) => user.role === "manager")
    .map((user) => `<option value="${user.id}">${escapeHtml(user.name)} (#${user.id})</option>`)
    .join("");

  return `
    <section class="grid-3">
      <article class="card metric"><p>Pending</p><h3>${analytics?.total_pending ?? 0}</h3></article>
      <article class="card metric"><p>Approved</p><h3>${analytics?.total_approved ?? 0}</h3></article>
      <article class="card metric"><p>Rejected</p><h3>${analytics?.total_rejected ?? 0}</h3></article>
    </section>
    <section class="admin-layout">
      <section class="card form-card">
        <h3>Create User</h3>
        <form id="admin-user-form" class="grid-form">
          <label>Name<input name="name" required /></label>
          <label>Email<input name="email" type="email" required /></label>
          <label>Password<input name="password" type="password" minlength="6" required /></label>
          <label>Role
            <select name="role">
              <option value="employee">employee</option>
              <option value="manager">manager</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <label class="span-2">Manager (only for employee)
            <select name="manager_id" id="admin-manager-select">
              <option value="">None</option>
              ${managerChoices}
            </select>
          </label>
          <button class="btn btn-primary span-2" type="submit">Create User</button>
        </form>
      </section>
      <section class="card">
        <h3>Users</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Manager</th><th>Update</th></tr></thead>
            <tbody>
              ${
                store.users.length
                  ? store.users
                      .map(
                        (user) => `
                          <tr>
                            <td>${escapeHtml(user.name)}</td>
                            <td>${escapeHtml(user.email)}</td>
                            <td>
                              <select class="mini-select" data-user-role="${user.id}">
                                <option value="employee" ${user.role === "employee" ? "selected" : ""}>employee</option>
                                <option value="manager" ${user.role === "manager" ? "selected" : ""}>manager</option>
                                <option value="admin" ${user.role === "admin" ? "selected" : ""}>admin</option>
                              </select>
                            </td>
                            <td>
                              <select class="mini-select" data-user-manager="${user.id}">
                                <option value="">None</option>
                                ${managerOptionsForUser(user)}
                              </select>
                            </td>
                            <td><button class="btn" data-save-user="${user.id}">Save</button></td>
                          </tr>
                        `
                      )
                      .join("")
                  : '<tr><td colspan="5" class="muted">No users found.</td></tr>'
              }
            </tbody>
          </table>
        </div>
      </section>
      <section class="card form-card span-2">
        <h3>Approval Rules</h3>
        <form id="approval-rule-form" class="grid-form">
          <label>Rule Name<input name="name" required placeholder="Ex: Travel > 10k" /></label>
          <label>Threshold % (optional)<input name="threshold" type="number" min="1" max="100" step="1" placeholder="60" /></label>
          <label>Specific Approver
            <select name="specific_approver_id">
              <option value="">None</option>
              ${approverOptionsHtml()}
            </select>
          </label>
          <label>Step Sequence (approver IDs, comma-separated)
            <input name="steps" placeholder="3,1,8" />
          </label>
          <label><input name="is_manager_first" type="checkbox" /> Manager first</label>
          <label><input name="is_hybrid" type="checkbox" /> Hybrid mode (threshold OR specific)</label>
          <button class="btn btn-primary span-2" type="submit">Create Approval Rule</button>
        </form>

        <div class="table-wrap" style="margin-top:0.9rem;">
          <table>
            <thead><tr><th>Name</th><th>Mode</th><th>Threshold</th><th>Specific</th><th>Manager First</th><th>Steps</th></tr></thead>
            <tbody>${renderRuleRows()}</tbody>
          </table>
        </div>
      </section>
    </section>
  `;
}

function shellView() {
  let content = "";
  if (store.currentView === "dashboard") {
    content = dashboardView();
  } else if (store.currentView === "submit") {
    content = submitView();
  } else if (store.currentView === "history") {
    content = historyView();
  } else if (store.currentView === "queue") {
    content = queueView();
  } else if (store.currentView === "admin") {
    content = adminView();
  } else {
    content = dashboardView();
  }

  return `
    <header class="app-header">
      <div>
        <h1>FlowFund Console</h1>
        <p>Smarter reimbursements for fast-moving teams.</p>
      </div>
      <div class="header-meta">
        <span>${escapeHtml(store.user?.name || "")}</span>
        <button id="logout-btn" class="btn">Logout</button>
      </div>
    </header>
    <nav class="tabs">${navTabs()}</nav>
    <main>${content}</main>
  `;
}

function bindEvents() {
  const loginForm = document.querySelector("#login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", (event) => {
      event.preventDefault();
      doLogin(new FormData(loginForm));
    });
  }

  const demoLoginBtn = document.querySelector("#demo-login-btn");
  if (demoLoginBtn) {
    demoLoginBtn.addEventListener("click", () => {
      enterDemoMode();
      toast("success", "Demo mode active. Backend not required.");
      render();
    });
  }

  const expenseForm = document.querySelector("#expense-form");
  if (expenseForm) {
    expenseForm.addEventListener("submit", (event) => {
      event.preventDefault();
      doCreateExpense(new FormData(expenseForm));
    });
  }

  const scanBtn = document.querySelector("#scan-receipt");
  if (scanBtn) {
    scanBtn.addEventListener("click", () => {
      const input = document.querySelector("#receipt-file");
      doScanReceipt(input);
    });
  }

  const convertBtn = document.querySelector("#convert-btn");
  if (convertBtn && expenseForm) {
    convertBtn.addEventListener("click", () => {
      doConvertCurrency(new FormData(expenseForm));
    });
  }

  const logoutBtn = document.querySelector("#logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", doLogout);
  }

  document.querySelectorAll("[data-nav]").forEach((node) => {
    node.addEventListener("click", async (event) => {
      const nextView = event.currentTarget.getAttribute("data-nav");
      try {
        store.currentView = nextView;
        if (store.isDemoMode) {
          render();
          return;
        }
        if (nextView === "history") {
          store.expenses = await api.myExpenses(store.token);
        }
        if (nextView === "queue" && isPrivileged()) {
          store.queue = await api.approvalQueue(store.token);
        }
        if (nextView === "admin" && store.user?.role === "admin") {
          const [users, analytics, approvalRules] = await Promise.all([
            api.adminUsers(store.token),
            api.adminAnalytics(store.token),
            api.adminApprovalRules(store.token),
          ]);
          store.users = users;
          store.analytics = analytics;
          store.approvalRules = approvalRules;
        }
      } catch (error) {
        toast("error", apiMessage(error));
      }
      render();
    });
  });

  const adminUserForm = document.querySelector("#admin-user-form");
  if (adminUserForm) {
    const roleSelect = adminUserForm.querySelector('select[name="role"]');
    const managerSelect = adminUserForm.querySelector("#admin-manager-select");

    const syncManagerSelect = () => {
      if (!roleSelect || !managerSelect) {
        return;
      }
      const requiresManager = roleSelect.value === "employee";
      managerSelect.disabled = !requiresManager;
      if (!requiresManager) {
        managerSelect.value = "";
      }
    };

    syncManagerSelect();
    if (roleSelect) {
      roleSelect.addEventListener("change", syncManagerSelect);
    }

    adminUserForm.addEventListener("submit", (event) => {
      event.preventDefault();
      doCreateAdminUser(new FormData(adminUserForm));
    });
  }

  const approvalRuleForm = document.querySelector("#approval-rule-form");
  if (approvalRuleForm) {
    approvalRuleForm.addEventListener("submit", (event) => {
      event.preventDefault();
      doCreateApprovalRule(new FormData(approvalRuleForm));
    });
  }

  document.querySelectorAll("[data-save-user]").forEach((node) => {
    node.addEventListener("click", (event) => {
      const userId = Number(event.currentTarget.getAttribute("data-save-user"));
      const roleSelect = document.querySelector(`[data-user-role="${userId}"]`);
      const managerSelect = document.querySelector(`[data-user-manager="${userId}"]`);
      const role = roleSelect ? roleSelect.value : "employee";
      const managerId = managerSelect ? managerSelect.value : "";
      doUpdateUser(userId, role, managerId);
    });
  });

  document.querySelectorAll("[data-detail]").forEach((node) => {
    node.addEventListener("click", (event) => {
      const expenseId = Number(event.currentTarget.getAttribute("data-detail"));
      doLoadExpenseDetail(expenseId);
    });
  });

  document.querySelectorAll("[data-queue-detail]").forEach((node) => {
    node.addEventListener("click", (event) => {
      const expenseId = Number(event.currentTarget.getAttribute("data-queue-detail"));
      doLoadExpenseDetail(expenseId);
    });
  });

  document.querySelectorAll("[data-approve]").forEach((node) => {
    node.addEventListener("click", (event) => {
      const expenseId = Number(event.currentTarget.getAttribute("data-approve"));
      doApprove(expenseId, "approved");
    });
  });

  document.querySelectorAll("[data-reject]").forEach((node) => {
    node.addEventListener("click", (event) => {
      const expenseId = Number(event.currentTarget.getAttribute("data-reject"));
      doApprove(expenseId, "rejected");
    });
  });
}

function render() {
  if (!app) {
    return;
  }

  const toastHtml = store.toast
    ? `<div class="toast ${store.toast.kind}">${escapeHtml(store.toast.message)}</div>`
    : "";

  if (!store.token) {
    app.innerHTML = `${authView()}${toastHtml}`;
    bindEvents();
    return;
  }

  app.innerHTML = `${shellView()}${toastHtml}`;
  bindEvents();
}

bootstrapSession().then(render);
