// components/ui/top-bar.tsx
import * as React from "react";
import { useNavigate } from "react-router-dom";

const font = "'Almarai', sans-serif";

export const TopBar: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div
      dir="rtl"
      style={{
        position: "sticky",
        top: 20,
        zIndex: 100,
        padding: "0 32px",
        display: "flex",
        justifyContent: "center",
      }}
    >
      <nav
        style={{
          height: 68,
          width: "100%",
          maxWidth: 1060,
          background: "rgba(0,0,0,0.55)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 8,
          boxShadow: "0 8px 32px rgba(0,0,0,0.5), 0 0 0 0.5px rgba(255,255,255,0.04)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 32px",
        }}
      >
        <img
          src="/powered_by_finaira.png"
          alt="Finaira"
          style={{ height: 30, width: "auto" }}
        />

        <button
          onClick={() => navigate("/")}
          style={{
            border: "none",
            background: "transparent",
            color: "rgba(255,255,255,0.5)",
            fontFamily: font,
            fontWeight: 600,
            fontSize: 15,
            padding: "8px 4px",
            cursor: "pointer",
            transition: "color 0.2s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "#ffffff";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "rgba(255,255,255,0.5)";
          }}
        >
          الرئيسية
        </button>
      </nav>
    </div>
  );
};
