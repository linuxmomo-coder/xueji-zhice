import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import GlobalAccountCenter from "./GlobalAccountCenter";
import GlobalOcrCenter from "./GlobalOcrCenter";
import GlobalQuestionAdminCenter from "./GlobalQuestionAdminCenter";
import GlobalRecoveryCenter from "./GlobalRecoveryCenter";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
    <GlobalAccountCenter />
    <GlobalRecoveryCenter />
    <GlobalOcrCenter />
    <GlobalQuestionAdminCenter />
  </React.StrictMode>
);
