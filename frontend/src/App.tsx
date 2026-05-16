import { useEffect } from "react";
import { Routes, Route } from "react-router-dom";

import { sessionState, useChatSession } from "@chainlit/react-client";
import { Playground } from "./components/playground";
import { useRecoilValue } from "recoil";
import LandingPage from "./pages/LandingPage";
import ExplorerPage from "./pages/ExplorerPage";

const userEnv = {};

function AppShell() {
  const { connect } = useChatSession();
  const session = useRecoilValue(sessionState);
  useEffect(() => {
    if (session?.socket.connected) {
      return;
    }
    fetch("http://localhost:8000/custom-auth", { credentials: "include" }).then(
      () => {
        connect({ userEnv });
      }
    );
  }, [connect]);

  return <Playground />;
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/app" element={<AppShell />} />
      <Route path="/explorer" element={<ExplorerPage />} />
    </Routes>
  );
}

export default App;
