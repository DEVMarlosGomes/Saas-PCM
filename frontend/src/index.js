import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import { register as registerSW } from "@/lib/serviceWorkerRegistration";
import { flushQueue } from "@/lib/offlineQueue";
import { getAccessToken } from "@/contexts/AuthContext";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Register PWA service worker — flushes offline queue when connectivity returns
registerSW(async () => {
  const token = getAccessToken();
  if (token) {
    const result = await flushQueue(token);
    if (result.synced > 0) {
      console.log(`[AURIX] Synced ${result.synced} offline operation(s)`);
    }
    if (result.conflicts.length > 0) {
      console.warn(`[AURIX] ${result.conflicts.length} conflict(s) — server version used`);
    }
  }
});
