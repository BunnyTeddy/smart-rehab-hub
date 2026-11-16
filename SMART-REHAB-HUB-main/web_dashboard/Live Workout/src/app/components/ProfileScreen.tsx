import {
  Bell,
  Volume2,
  HelpCircle,
  RefreshCw,
  ChevronRight,
  LogOut,
  Edit3,
  Wifi,
  Activity,
} from "lucide-react";

export function ProfileScreen() {
  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: "#F8FAFC" }}>
      <div className="flex-1 overflow-y-auto pb-24" style={{ scrollbarWidth: "none" }}>
        {/* Header */}
        <div
          className="px-4 pt-14 pb-6 flex flex-col items-center relative"
          style={{
            background: "linear-gradient(160deg, #065F46 0%, #0F766E 50%, #10B981 100%)",
          }}
        >
          {/* Avatar */}
          <div className="relative mb-3">
            <div
              className="w-24 h-24 rounded-full flex items-center justify-center"
              style={{
                background: "rgba(255,255,255,0.2)",
                border: "3px solid rgba(255,255,255,0.5)",
                boxShadow: "0 4px 24px rgba(0,0,0,0.2), 0 0 0 6px rgba(255,255,255,0.1)",
                fontSize: "38px",
              }}
            >
              👴
            </div>
            {/* Edit button on avatar */}
            <div
              className="absolute bottom-0 right-0 w-7 h-7 rounded-full flex items-center justify-center"
              style={{
                background: "#ffffff",
                boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
              }}
            >
              <Edit3 size={13} color="#10B981" />
            </div>
          </div>

          <h1 style={{ color: "#ffffff", fontSize: "22px", fontWeight: 700, letterSpacing: "-0.02em" }}>
            Uncle Hung
          </h1>
          <p style={{ color: "rgba(255,255,255,0.75)", fontSize: "13px", fontFamily: "monospace", marginTop: "2px" }}>
            +84 091 234 5678
          </p>

          {/* using <button> instead of <Button>: needs translucent white pill on colored header, no kit variant matches */}
          <button
            className="mt-4 flex items-center gap-2 px-4 py-2 rounded-full"
            style={{
              background: "rgba(255,255,255,0.2)",
              border: "1px solid rgba(255,255,255,0.35)",
              color: "#ffffff",
              fontSize: "13px",
              fontWeight: 600,
              backdropFilter: "blur(8px)",
            }}
          >
            <Edit3 size={13} />
            Edit Profile
          </button>
        </div>

        <div className="px-4 pt-4 flex flex-col gap-4">
          {/* Medical Summary Card */}
          <div>
            <p
              style={{
                color: "#64748B",
                fontSize: "11px",
                fontFamily: "monospace",
                letterSpacing: "0.08em",
                marginBottom: "8px",
              }}
            >
              MEDICAL SUMMARY
            </p>
            <div
              className="rounded-2xl p-4"
              style={{
                background: "#ffffff",
                boxShadow: "0 1px 8px rgba(0,0,0,0.06)",
                border: "1px solid rgba(30,41,59,0.06)",
              }}
            >
              <div className="flex items-start gap-3 mb-3">
                <div
                  className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ background: "#D1FAE5" }}
                >
                  <Activity size={16} color="#10B981" />
                </div>
                <div>
                  <p style={{ color: "#64748B", fontSize: "11px", fontFamily: "monospace" }}>CONDITION</p>
                  <p style={{ color: "#1E293B", fontSize: "14px", fontWeight: 600 }}>Post-Stroke Recovery</p>
                </div>
              </div>
              <div
                className="h-px w-full"
                style={{ background: "rgba(30,41,59,0.06)" }}
              />
              <div className="flex gap-6 pt-3">
                <div>
                  <p style={{ color: "#64748B", fontSize: "11px", fontFamily: "monospace" }}>HEIGHT</p>
                  <p style={{ color: "#1E293B", fontSize: "18px", fontWeight: 700, fontFamily: "monospace" }}>
                    165
                    <span style={{ color: "#64748B", fontSize: "11px", fontWeight: 400 }}> cm</span>
                  </p>
                </div>
                <div>
                  <p style={{ color: "#64748B", fontSize: "11px", fontFamily: "monospace" }}>WEIGHT</p>
                  <p style={{ color: "#1E293B", fontSize: "18px", fontWeight: 700, fontFamily: "monospace" }}>
                    60
                    <span style={{ color: "#64748B", fontSize: "11px", fontWeight: 400 }}> kg</span>
                  </p>
                </div>
                <div>
                  <p style={{ color: "#64748B", fontSize: "11px", fontFamily: "monospace" }}>BMI</p>
                  <p style={{ color: "#10B981", fontSize: "18px", fontWeight: 700, fontFamily: "monospace" }}>
                    22.0
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* IoT / Raspberry Pi Settings */}
          <div>
            <p
              style={{
                color: "#64748B",
                fontSize: "11px",
                fontFamily: "monospace",
                letterSpacing: "0.08em",
                marginBottom: "8px",
              }}
            >
              IOT DEVICE SETTINGS
            </p>
            <div
              className="rounded-2xl p-4"
              style={{
                background: "#ffffff",
                boxShadow: "0 1px 8px rgba(0,0,0,0.06)",
                border: "1px solid rgba(30,41,59,0.06)",
              }}
            >
              <p style={{ color: "#1E293B", fontSize: "14px", fontWeight: 600, marginBottom: "12px" }}>
                Raspberry Pi Settings
              </p>

              {/* Device Graphic */}
              <div className="flex items-center gap-4 mb-4">
                <div
                  className="relative w-16 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{
                    background: "linear-gradient(135deg, #1E293B 0%, #0F172A 100%)",
                    border: "1px solid rgba(16,185,129,0.3)",
                    boxShadow: "0 0 12px rgba(16,185,129,0.15)",
                  }}
                >
                  {/* Pi board visual */}
                  <div className="absolute top-1.5 left-1.5 w-2 h-1.5 rounded-sm" style={{ background: "#10B981", opacity: 0.8 }} />
                  <div className="absolute top-1.5 right-1.5 w-1 h-1 rounded-full" style={{ background: "#34D399" }} />
                  <div className="absolute bottom-1.5 left-1.5 right-1.5 h-0.5 rounded-full" style={{ background: "rgba(16,185,129,0.3)" }} />
                  <svg width="24" height="20" viewBox="0 0 24 20">
                    <rect x="2" y="4" width="20" height="12" rx="2" fill="rgba(16,185,129,0.15)" stroke="rgba(16,185,129,0.5)" strokeWidth="0.8" />
                    <rect x="5" y="7" width="4" height="3" rx="0.5" fill="rgba(16,185,129,0.4)" />
                    <rect x="11" y="7" width="3" height="3" rx="0.5" fill="rgba(16,185,129,0.4)" />
                    <rect x="16" y="7" width="2" height="3" rx="0.5" fill="rgba(16,185,129,0.4)" />
                    <circle cx="12" cy="15.5" r="1.5" fill="#10B981" />
                  </svg>
                </div>
                <div>
                  <div className="flex items-center gap-1.5 mb-1">
                    <div className="w-2 h-2 rounded-full" style={{ background: "#10B981", boxShadow: "0 0 6px #10B981" }} />
                    <span style={{ color: "#10B981", fontSize: "12px", fontWeight: 600, fontFamily: "monospace" }}>
                      Online
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Wifi size={11} color="#10B981" />
                    <span style={{ color: "#10B981", fontSize: "11px", fontFamily: "monospace" }}>5G URLLC</span>
                  </div>
                  <p style={{ color: "#64748B", fontSize: "11px", marginTop: "2px" }}>
                    Device ID: RPI-4B-HU01
                  </p>
                </div>
              </div>

              <div
                className="h-px w-full mb-3"
                style={{ background: "rgba(30,41,59,0.06)" }}
              />

              {/* using <button> instead of <Button>: needs full-width outlined action button with icon */}
              <button
                className="w-full flex items-center justify-center gap-2 rounded-xl py-2.5"
                style={{
                  background: "#F1F5F9",
                  border: "1px solid rgba(30,41,59,0.1)",
                  color: "#1E293B",
                  fontSize: "13px",
                  fontWeight: 600,
                }}
              >
                <RefreshCw size={14} color="#10B981" />
                Re-sync Device
              </button>
            </div>
          </div>

          {/* App Settings */}
          <div>
            <p
              style={{
                color: "#64748B",
                fontSize: "11px",
                fontFamily: "monospace",
                letterSpacing: "0.08em",
                marginBottom: "8px",
              }}
            >
              APP SETTINGS
            </p>
            <div
              className="rounded-2xl overflow-hidden"
              style={{
                background: "#ffffff",
                boxShadow: "0 1px 8px rgba(0,0,0,0.06)",
                border: "1px solid rgba(30,41,59,0.06)",
              }}
            >
              {[
                {
                  icon: <Bell size={16} color="#10B981" />,
                  label: "Notifications",
                  sub: "Session reminders, alerts",
                },
                {
                  icon: <Volume2 size={16} color="#10B981" />,
                  label: "Text-to-Speech Voice",
                  sub: "Voice coaching settings",
                },
                {
                  icon: <HelpCircle size={16} color="#10B981" />,
                  label: "Help & Support",
                  sub: "FAQ, contact team",
                },
              ].map((item, i, arr) => (
                <div key={item.label}>
                  {/* using <button> instead of <Button>: list-row tap target with leading icon, trailing chevron */}
                  <button
                    className="w-full flex items-center gap-3 px-4 py-3.5 text-left"
                    style={{ background: "transparent" }}
                  >
                    <div
                      className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ background: "#D1FAE5" }}
                    >
                      {item.icon}
                    </div>
                    <div className="flex-1">
                      <p style={{ color: "#1E293B", fontSize: "14px", fontWeight: 500 }}>
                        {item.label}
                      </p>
                      <p style={{ color: "#94A3B8", fontSize: "11px" }}>{item.sub}</p>
                    </div>
                    <ChevronRight size={16} color="#CBD5E1" />
                  </button>
                  {i < arr.length - 1 && (
                    <div className="h-px mx-4" style={{ background: "rgba(30,41,59,0.05)" }} />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Log Out Button */}
          {/* using <button> instead of <Button>: needs full-width outlined destructive, no exact kit destructive-outline variant */}
          <button
            className="w-full flex items-center justify-center gap-2 rounded-2xl py-3.5"
            style={{
              background: "#FEF2F2",
              border: "1.5px solid #FECACA",
              color: "#DC2626",
              fontSize: "15px",
              fontWeight: 600,
            }}
          >
            <LogOut size={17} color="#DC2626" />
            Log Out
          </button>
        </div>
      </div>
    </div>
  );
}
