import React from "react";
import { createRoot } from "react-dom/client";
import { PopupApp } from "./PopupApp.js";

const container = document.getElementById("root");
if (container) {
  createRoot(container).render(<PopupApp />);
}
