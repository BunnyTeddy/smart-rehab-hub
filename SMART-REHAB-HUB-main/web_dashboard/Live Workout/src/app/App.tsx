import { useState } from "react";
import { Home, Dumbbell, History, User } from "lucide-react";
import { LiveWorkoutScreen } from "./components/LiveWorkoutScreen";
import { HistoryScreen } from "./components/HistoryScreen";
import { ProfileScreen } from "./components/ProfileScreen";
import { IntegrationDashboard } from "../integration/IntegrationDashboard";
import Dashboard from "../product/Dashboard";

{/* MARKER-MAKE-KIT-INVOKED */}

type Tab = "home" | "workout" | "history" | "profile";

function HomeScreen({ onStartWorkout }: { onStartWorkout: () => void }) {
  return (
    <div className="flex flex-col h-full" style={{ background: "#F8FAFC" }}>
      {/* Header */}
      <div className="px-5 pt-14 pb-4" style={{ background: "#F8FAFC" }}>
        <p style={{ color: "#64748B", fontSize: "13px", fontFamily: "monospace", letterSpacing: "0.06em" }}>
          GOOD MORNING
        </p>
        <h1 style={{ color: "#1E293B", fontSize: "26px", fontWeight: 700, letterSpacing: "-0.03em", lineHeight: 1.2, marginTop: "2px" }}>
          Uncle Hung 👋
        </h1>
      </div>

      <div className="flex-1 overflow-y-auto px-5 pb-24" style={{ scrollbarWidth: "none" }}>
        {/* Recovery Progress Card */}
        <div
          className="rounded-2xl p-5 mb-4"
          style={{
            background: "linear-gradient(135deg, #065F46 0%, #10B981 100%)",
            boxShadow: "0 8px 32px rgba(16,185,129,0.25)",
          }}
        >
          <p style={{ color: "rgba(255,255,255,0.75)", fontSize: "11px", fontFamily: "monospace", letterSpacing: "0.08em" }}>
            WEEKLY RECOVERY GOAL
          </p>
          <div className="flex items-end justify-between mt-1">
            <div>
              <span style={{ color: "#ffffff", fontSize: "40px", fontWeight: 700, letterSpacing: "-0.04em", lineHeight: 1 }}>
                82
              </span>
              <span style={{ color: "rgba(255,255,255,0.7)", fontSize: "16px", marginLeft: "4px" }}>%</span>
            </div>
            <div className="text-right">
              <p style={{ color: "rgba(255,255,255,0.7)", fontSize: "12px" }}>5 of 7 sessions</p>
              <p style={{ color: "#A7F3D0", fontSize: "12px", fontWeight: 600 }}>On track ✓</p>
            </div>
          </div>
          {/* Progress bar */}
          <div className="mt-3 h-2 rounded-full" style={{ background: "rgba(255,255,255,0.2)" }}>
            <div className="h-2 rounded-full" style={{ width: "82%", background: "rgba(255,255,255,0.9)", boxShadow: "0 0 8px rgba(255,255,255,0.6)" }} />
          </div>
        </div>

        {/* Today's Plan */}
        <p style={{ color: "#1E293B", fontSize: "16px", fontWeight: 700, marginBottom: "12px" }}>
          Today's Plan
        </p>

        <div className="flex flex-col gap-3">
          {[
            { name: "Bicep Curl", sets: "3 × 15 reps", muscle: "Biceps", done: false },
            { name: "Shoulder Raise", sets: "3 × 12 reps", muscle: "Deltoids", done: true },
            { name: "Wrist Flexion", sets: "2 × 20 reps", muscle: "Forearms", done: true },
          ].map((ex) => (
            <div
              key={ex.name}
              className="rounded-2xl p-4 flex items-center gap-3"
              style={{
                background: "#ffffff",
                boxShadow: "0 1px 8px rgba(0,0,0,0.05)",
                border: ex.done ? "1px solid #D1FAE5" : "1px solid rgba(30,41,59,0.06)",
                opacity: ex.done ? 0.7 : 1,
              }}
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ background: ex.done ? "#D1FAE5" : "#F1F5F9" }}
              >
                <Dumbbell size={18} color={ex.done ? "#10B981" : "#64748B"} />
              </div>
              <div className="flex-1">
                <p style={{ color: "#1E293B", fontSize: "14px", fontWeight: 600 }}>
                  {ex.done && <span style={{ textDecoration: "line-through", color: "#94A3B8" }}>{ex.name}</span>}
                  {!ex.done && ex.name}
                </p>
                <p style={{ color: "#64748B", fontSize: "12px" }}>{ex.sets} · {ex.muscle}</p>
              </div>
              {ex.done ? (
                <span style={{ color: "#10B981", fontSize: "16px" }}>✅</span>
              ) : (
                <button
                  onClick={onStartWorkout}
                  className="px-3 py-1.5 rounded-full"
                  style={{ background: "#10B981", color: "#ffffff", fontSize: "12px", fontWeight: 700 }}
                >
                  Start
                </button>
              )}
            </div>
          ))}
        </div>

        {/* Quick stats */}
        <p style={{ color: "#1E293B", fontSize: "16px", fontWeight: 700, marginTop: "20px", marginBottom: "12px" }}>
          Quick Stats
        </p>
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Sessions", value: "28", unit: "total" },
            { label: "Avg Accuracy", value: "82", unit: "%" },
            { label: "Streak", value: "5", unit: "days" },
          ].map((s) => (
            <div
              key={s.label}
              className="rounded-2xl p-3 text-center"
              style={{
                background: "#ffffff",
                boxShadow: "0 1px 6px rgba(0,0,0,0.05)",
              }}
            >
              <p style={{ color: "#1E293B", fontSize: "22px", fontWeight: 700, fontFamily: "monospace", letterSpacing: "-0.02em" }}>
                {s.value}
                <span style={{ color: "#10B981", fontSize: "12px" }}>{s.unit}</span>
              </p>
              <p style={{ color: "#64748B", fontSize: "10px", marginTop: "2px" }}>{s.label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const navItems: { id: Tab; label: string; Icon: typeof Home }[] = [
  { id: "home", label: "Home", Icon: Home },
  { id: "workout", label: "Workout", Icon: Dumbbell },
  { id: "history", label: "History", Icon: History },
  { id: "profile", label: "Profile", Icon: User },
];

export default function App() { return import.meta.env.VITE_REHAB_LEGACY === 'true' ? <IntegrationDashboard /> : <Dashboard />; }

export function LegacyPrototypeApp() {
  const [activeTab, setActiveTab] = useState<Tab>("home");

  return (
    <div className="size-full flex items-center justify-center" style={{ background: "#CBD5E1" }}>
      {/* Mobile Frame */}
      <div
        className="relative flex flex-col overflow-hidden"
        style={{
          width: "min(390px, 100%)",
          height: "min(844px, 100%)",
          background: "#F8FAFC",
          borderRadius: "clamp(0px, 4vw, 40px)",
          boxShadow: "0 32px 80px rgba(0,0,0,0.25), 0 8px 24px rgba(0,0,0,0.15), inset 0 0 0 1px rgba(255,255,255,0.2)",
        }}
      >
        {/* Screen Content */}
        <div className="flex-1 overflow-hidden relative">
          {activeTab === "home" && (
            <HomeScreen onStartWorkout={() => setActiveTab("workout")} />
          )}
          {activeTab === "workout" && (
            <LiveWorkoutScreen onBack={() => setActiveTab("home")} />
          )}
          {activeTab === "history" && <HistoryScreen />}
          {activeTab === "profile" && <ProfileScreen />}
        </div>

        {/* Bottom Navigation Bar */}
        <div
          className="absolute bottom-0 left-0 right-0 flex items-center"
          style={{
            background: "rgba(255,255,255,0.95)",
            backdropFilter: "blur(16px)",
            borderTop: "1px solid rgba(30,41,59,0.08)",
            paddingBottom: "env(safe-area-inset-bottom, 12px)",
            paddingTop: "8px",
            zIndex: 50,
          }}
        >
          {navItems.map(({ id, label, Icon }) => {
            const isActive = activeTab === id;
            return (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className="flex-1 flex flex-col items-center gap-1 py-1"
                style={{ background: "transparent", border: "none" }}
              >
                <div
                  className="w-12 h-7 rounded-full flex items-center justify-center"
                  style={{
                    background: isActive ? "#D1FAE5" : "transparent",
                    transition: "background 0.2s ease",
                  }}
                >
                  <Icon
                    size={20}
                    color={isActive ? "#10B981" : "#94A3B8"}
                    style={{ transition: "color 0.2s ease" }}
                  />
                </div>
                <span
                  style={{
                    fontSize: "10px",
                    fontWeight: isActive ? 600 : 400,
                    color: isActive ? "#10B981" : "#94A3B8",
                    fontFamily: "monospace",
                    letterSpacing: "0.04em",
                    transition: "color 0.2s ease",
                  }}
                >
                  {label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
