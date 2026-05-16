import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.tsx";
import { RecoilRoot } from "recoil";
import "./index.css";
import { ChainlitAPI, ChainlitContext } from "@chainlit/react-client";

const CHAINLIT_SERVER = "http://localhost:8000/chainlit";

const apiClient = new ChainlitAPI(CHAINLIT_SERVER, "webapp");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ChainlitContext.Provider value={apiClient}>
        <RecoilRoot>
          <App />
        </RecoilRoot>
      </ChainlitContext.Provider>
    </BrowserRouter>
  </React.StrictMode>
);
