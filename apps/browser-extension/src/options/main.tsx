import React from "react";
import { createRoot } from "react-dom/client";
import { OptionsApp } from "./OptionsApp.js";

const container = document.getElementById("root");
if (container) {
  createRoot(container).render(<OptionsApp />);
}
