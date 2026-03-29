import { store } from "./store.js";

const app = document.getElementById("app");
if (app) {
  app.textContent = `Current view: ${store.currentView}`;
}
