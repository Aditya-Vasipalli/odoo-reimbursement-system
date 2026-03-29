export const store = {
  token: localStorage.getItem("token") || null,
  user: null,
  company: null,
  isDemoMode: false,
  currencyOptions: [],
  categories: ["Travel", "Food", "Office", "Medical", "Lodging", "Client Meeting", "Software", "Other"],
  demoDecisionByExpense: {},
  currentView: "login",
  loading: false,
  toast: null,
  expenses: [],
  queue: [],
  users: [],
  approvalRules: [],
  analytics: null,
  selectedExpense: null,
};

export function setToken(token) {
  store.token = token;
  if (token) {
    localStorage.setItem("token", token);
    return;
  }
  localStorage.removeItem("token");
}

export function resetSession() {
  setToken(null);
  store.user = null;
  store.company = null;
  store.isDemoMode = false;
  store.currencyOptions = [];
  store.demoDecisionByExpense = {};
  store.currentView = "login";
  store.expenses = [];
  store.queue = [];
  store.users = [];
  store.approvalRules = [];
  store.analytics = null;
  store.selectedExpense = null;
}
