// components/AppShell.tsx
import React from "react";

type AppShellProps = {
  children: React.ReactNode;
  className?: string;
  outerClassName?: string;
};

export const AppShell: React.FC<AppShellProps> = ({
  children,
  className,
  outerClassName,
}) => {
  return (
    <div
      style={{ backgroundColor: "#000000", overflowX: "clip" }}
      className={`w-full text-gray-100 relative ${outerClassName ?? ""}`}
    >
      {/* Aurora halo */}
      <div
        aria-hidden
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 0,
          pointerEvents: "none",
          overflow: "hidden",
        }}
      >
        <div
          className="aurora"
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: "140vw",
            height: "140vw",
            marginTop: "-70vw",
            marginLeft: "-70vw",
            background: `
              radial-gradient(ellipse 55% 40% at 60% 35%, rgba(124,58,237,0.55) 0%, transparent 70%),
              radial-gradient(ellipse 45% 50% at 75% 65%, rgba(6,182,212,0.38) 0%, transparent 65%),
              radial-gradient(ellipse 50% 45% at 30% 70%, rgba(37,99,235,0.45) 0%, transparent 70%)
            `,
            filter: "blur(55px)",
          }}
        />
      </div>

      <div className={`relative z-10 mx-auto px-6 md:px-10 ${className ?? ""}`}>
        {children}
      </div>
    </div>
  );
};
