export const store = {
  token: localStorage.getItem("token") || null,
  user: null,
  company: null,
  currentView: "login",
  toast: null,
};
