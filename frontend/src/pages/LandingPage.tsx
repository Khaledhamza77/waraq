import { useNavigate } from "react-router-dom";
import { ArrowLeft, BookOpen, Scale, Search, type LucideIcon } from "lucide-react";

const features: {
  iconBg: string;
  iconColor: string;
  Icon: LucideIcon;
  title: string;
  description: string;
}[] = [
  {
    iconBg: "rgba(124,58,237,0.15)",
    iconColor: "#8B5CF6",
    Icon: BookOpen,
    title: "تصفح الوثيقة",
    description:
      "استعرض معايير المحاسبة المصرية قسماً بقسم. لكل قسم تحديد دقيق لموضعه في الوثيقة الأصلية مع إمكانية عرض النص ومربعات التحديد والصفحة المصدر في آنٍ واحد.",
  },
  {
    iconBg: "rgba(59,130,246,0.15)",
    iconColor: "#60A5FA",
    Icon: Scale,
    title: "استشر الخبير",
    description:
      "اطرح أسئلتك القانونية والمحاسبية بالعربية. يبحث النظام بذكاء في الوثيقة ويُجيبك بأدلة مباشرة من النصوص — بدون نماذج تدريبية مسبقة، بل بالاستدلال الحقيقي على المصدر.",
  },
  {
    iconBg: "rgba(6,182,212,0.12)",
    iconColor: "#22D3EE",
    Icon: Search,
    title: "تحقق من الاستشهادات",
    description:
      "تحقق بنفسك من كل استشهاد قانوني: يُظهر لك النظام القسم المُشار إليه داخل الوثيقة الأصلية بتمييز بصري مباشر، فلا غموض ولا الحاجة لمراجعة يدوية.",
  },
];

const font = "'Almarai', sans-serif";

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div
      dir="rtl"
      style={{
        backgroundColor: "#000000",
        color: "#F0F2FF",
        fontFamily: font,
        minHeight: "100vh",
        overflowX: "clip",
        position: "relative",
      }}
    >
      {/* ── Aurora halo ── */}
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

      {/* ── Content wrapper ── */}
      <div style={{ position: "relative", zIndex: 1 }}>

        {/* ── Navbar ── */}
        <div style={{ position: "sticky", top: 20, zIndex: 100, padding: "0 32px", display: "flex", justifyContent: "center" }}>
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
          {/* Brand */}
          <img
            src="/powered_by_finaira.png"
            alt="Finaira"
            style={{ height: 30, width: "auto" }}
          />

          {/* Nav CTA */}
          <NavButton onClick={() => navigate("/app")}>ادخل التطبيق</NavButton>
        </nav>
        </div>

        {/* ── Hero ── */}
        <section
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "0 40px",
            textAlign: "center",
          }}
        >
          <h1
            style={{
              fontWeight: 800,
              fontSize: "clamp(40px, 5.5vw, 64px)",
              lineHeight: 1.25,
              color: "#F0F2FF",
              margin: 0,
              maxWidth: 720,
            }}
          >
            مرجعك الذكي لمعايير
            <br />
            <strong style={{ color: "#ffffff", fontWeight: 800 }}>
              المحاسبة المصرية
            </strong>
          </h1>

          {/* Rule accent — white, centered */}
          <div
            style={{
              width: 52,
              height: 2,
              background: "rgba(255,255,255,0.25)",
              border: "none",
              margin: "20px auto",
            }}
          />

          <p
            style={{
              fontWeight: 300,
              fontSize: 18,
              lineHeight: 1.8,
              color: "#8A8FAD",
              maxWidth: 560,
              margin: "0 0 36px 0",
            }}
          >
            منصة متكاملة تجمع بين الاستعراض الدقيق للوثيقة الرسمية،
            والاستشارة القانونية الذكية، والتحقق البصري من الاستشهادات،{" "}
            <span style={{ whiteSpace: "nowrap" }}>كل ذلك <strong style={{ color: "#F0F2FF", fontWeight: 600 }}>بالعربية وبلا تعقيد</strong>.</span>
          </p>

          <HeroCTAButton onClick={() => navigate("/app")} />
        </section>

        {/* ── Feature Cards ── */}
        <section style={{ padding: "8px 40px 120px", maxWidth: 1200, margin: "0 auto" }}>
          <p
            style={{
              fontWeight: 700,
              fontSize: 22,
              color: "#F0F2FF",
              textAlign: "center",
              marginBottom: 40,
            }}
          >
            ما الذي تقدمه المنصة؟
          </p>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: 20,
              maxWidth: 1080,
              margin: "0 auto",
            }}
          >
            {features.map((f) => (
              <FeatureCard key={f.title} {...f} />
            ))}
          </div>
        </section>

        {/* ── Footer ── */}
        <footer style={{ padding: "0 32px 32px", display: "flex", flexDirection: "column", alignItems: "center", gap: 0 }}>
          {/* Separator — same width as navbar */}
          <div style={{ width: "100%", maxWidth: 1060, height: 1, background: "rgba(255,255,255,0.08)", marginBottom: 24 }} />

          <div style={{ width: "100%", maxWidth: 1060, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <img src="/powered_by_finaira.png" alt="Finaira" style={{ height: 22, width: "auto" }} />

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#F0F2FF", fontFamily: font }}>
                خالد إبراهيم
              </span>
              <span style={{ color: "rgba(255,255,255,0.2)", fontSize: 12 }}>·</span>
              <a
                href="mailto:khaled.ibrahim@finaira.ai"
                style={{ fontSize: 12, color: "rgba(255,255,255,0.6)", fontFamily: font, textDecoration: "none", letterSpacing: "0.02em" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "#ffffff")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.6)")}
              >
                khaled.ibrahim@finaira.ai
              </a>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function NavButton({
  onClick,
  children,
}: {
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
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
      {children}
    </button>
  );
}

function HeroCTAButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        borderRadius: 999,
        background: "#ffffff",
        color: "#000000",
        fontFamily: font,
        fontWeight: 700,
        fontSize: 14,
        letterSpacing: "0.04em",
        padding: "14px 32px",
        border: "none",
        cursor: "pointer",
        transition: "all 0.2s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "#e8e8e8";
        e.currentTarget.style.boxShadow = "0 0 28px rgba(255,255,255,0.18)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "#ffffff";
        e.currentTarget.style.boxShadow = "none";
      }}
      onMouseDown={(e) => (e.currentTarget.style.transform = "scale(0.97)")}
      onMouseUp={(e) => (e.currentTarget.style.transform = "scale(1)")}
    >
      ابدأ الآن
      <ArrowLeft size={16} strokeWidth={2} />
    </button>
  );
}

function FeatureCard({
  iconBg,
  iconColor,
  Icon,
  title,
  description,
}: (typeof features)[0]) {
  return (
    <div
      style={{
        background: "rgba(0,0,0,0.2)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 8,
        padding: "40px 32px",
        display: "flex",
        flexDirection: "column",
        gap: 0,
        minHeight: 280,
        transition: "transform 0.25s ease, border-color 0.25s ease",
        cursor: "default",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.18)";
        (e.currentTarget as HTMLDivElement).style.transform = "translateY(-4px)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.08)";
        (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 12,
          background: iconBg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: iconColor,
        }}
      >
        <Icon size={22} strokeWidth={1.5} />
      </div>

      <h3
        style={{
          fontWeight: 600,
          fontSize: 18,
          color: "#F0F2FF",
          margin: "16px 0 0 0",
          fontFamily: font,
        }}
      >
        {title}
      </h3>

      <p
        style={{
          fontWeight: 400,
          fontSize: 14,
          color: "#7A7F9D",
          lineHeight: 1.8,
          marginTop: 12,
          marginBottom: 0,
          fontFamily: font,
        }}
      >
        {description}
      </p>

    </div>
  );
}
