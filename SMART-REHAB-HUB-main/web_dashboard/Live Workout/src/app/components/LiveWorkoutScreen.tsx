import { useState, useEffect, useRef } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { ArrowLeft, Wifi, Activity } from "lucide-react";
import { Badge } from "./ui/badge";

interface LiveWorkoutScreenProps {
  onBack?: () => void;
}

const generateAngleData = () => {
  const base = [
    { t: "0s", angle: 30 },
    { t: "2s", angle: 55 },
    { t: "4s", angle: 90 },
    { t: "6s", angle: 130 },
    { t: "8s", angle: 145 },
    { t: "10s", angle: 120 },
    { t: "12s", angle: 80 },
    { t: "14s", angle: 45 },
    { t: "16s", angle: 30 },
    { t: "18s", angle: 60 },
    { t: "20s", angle: 105 },
    { t: "22s", angle: 145 },
  ];
  return base;
};

const joints = [
  { cx: "38%", cy: "18%", r: 5, label: "shoulder-l" },
  { cx: "62%", cy: "18%", r: 5, label: "shoulder-r" },
  { cx: "28%", cy: "35%", r: 4, label: "elbow-l" },
  { cx: "72%", cy: "35%", r: 4, label: "elbow-r" },
  { cx: "24%", cy: "52%", r: 3.5, label: "wrist-l" },
  { cx: "76%", cy: "52%", r: 3.5, label: "wrist-r" },
  { cx: "50%", cy: "13%", r: 6, label: "neck" },
  { cx: "50%", cy: "28%", r: 7, label: "torso" },
];

const bones = [
  { x1: "50%", y1: "13%", x2: "38%", y2: "18%", label: "neck-shoulder-l" },
  { x1: "50%", y1: "13%", x2: "62%", y2: "18%", label: "neck-shoulder-r" },
  { x1: "38%", y1: "18%", x2: "28%", y2: "35%", label: "shoulder-elbow-l" },
  { x1: "62%", y1: "18%", x2: "72%", y2: "35%", label: "shoulder-elbow-r" },
  { x1: "28%", y1: "35%", x2: "24%", y2: "52%", label: "elbow-wrist-l" },
  { x1: "72%", y1: "35%", x2: "76%", y2: "52%", label: "elbow-wrist-r" },
  { x1: "50%", y1: "13%", x2: "50%", y2: "28%", label: "neck-torso" },
];

export function LiveWorkoutScreen({ onBack }: LiveWorkoutScreenProps) {
  const [reps, setReps] = useState(8);
  const [formStatus, setFormStatus] = useState<"perfect" | "warning">("perfect");
  const [currentAngle, setCurrentAngle] = useState(145);
  const [angleData] = useState(generateAngleData);
  const [glowPulse, setGlowPulse] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setGlowPulse((p) => !p);
    }, 1200);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return (
    <div className="flex flex-col h-full bg-[#0A0F1E] overflow-hidden">
      {/* Top Bar */}
      <div className="flex items-center justify-between px-4 pt-12 pb-3 relative z-10">
        {/* using <button> instead of <Button>: needs custom icon-only circular tap target with no variant match */}
        <button
          onClick={onBack}
          className="w-9 h-9 rounded-full flex items-center justify-center"
          style={{ background: "rgba(255,255,255,0.08)" }}
        >
          <ArrowLeft size={18} color="#ffffff" />
        </button>

        <div className="flex flex-col items-center">
          <span style={{ color: "#94A3B8", fontSize: "11px", letterSpacing: "0.08em", fontFamily: "monospace" }}>
            LIVE SESSION
          </span>
          <span style={{ color: "#F8FAFC", fontSize: "17px", fontWeight: 600, letterSpacing: "-0.02em" }}>
            Bicep Curl
          </span>
        </div>

        {/* 5G URLLC Badge */}
        <div
          className="flex items-center gap-1 px-2 py-1 rounded-full"
          style={{
            background: glowPulse
              ? "rgba(16, 185, 129, 0.25)"
              : "rgba(16, 185, 129, 0.12)",
            border: `1px solid ${glowPulse ? "rgba(16,185,129,0.8)" : "rgba(16,185,129,0.4)"}`,
            boxShadow: glowPulse
              ? "0 0 12px rgba(16,185,129,0.6), 0 0 24px rgba(16,185,129,0.2)"
              : "0 0 6px rgba(16,185,129,0.2)",
            transition: "all 0.6s ease",
          }}
        >
          <Wifi size={10} color="#10B981" />
          <span style={{ color: "#10B981", fontSize: "10px", fontWeight: 700, fontFamily: "monospace", letterSpacing: "0.05em" }}>
            5G URLLC
          </span>
        </div>
      </div>

      {/* Live Camera View */}
      <div className="mx-4 rounded-2xl overflow-hidden relative flex-shrink-0" style={{ height: "340px" }}>
        {/* Dark gradient camera background */}
        <div
          className="absolute inset-0"
          style={{
            background: "linear-gradient(160deg, #0D1B2A 0%, #0A1628 40%, #061118 100%)",
            border: "1px solid rgba(16,185,129,0.2)",
          }}
        />

        {/* Scan line effect */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(16,185,129,0.015) 3px, rgba(16,185,129,0.015) 4px)",
          }}
        />

        {/* Corner brackets */}
        {[
          { top: "12px", left: "12px", borderTop: "2px solid #10B981", borderLeft: "2px solid #10B981" },
          { top: "12px", right: "12px", borderTop: "2px solid #10B981", borderRight: "2px solid #10B981" },
          { bottom: "12px", left: "12px", borderBottom: "2px solid #10B981", borderLeft: "2px solid #10B981" },
          { bottom: "12px", right: "12px", borderBottom: "2px solid #10B981", borderRight: "2px solid #10B981" },
        ].map((style, i) => (
          <div
            key={i}
            className="absolute w-5 h-5"
            style={style}
          />
        ))}

        {/* "LIVE" indicator */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5">
          <div
            className="w-2 h-2 rounded-full"
            style={{
              background: "#EF4444",
              boxShadow: glowPulse ? "0 0 8px #EF4444" : "0 0 3px #EF4444",
              transition: "all 0.6s ease",
            }}
          />
          <span style={{ color: "#EF4444", fontSize: "10px", fontWeight: 700, fontFamily: "monospace", letterSpacing: "0.1em" }}>
            LIVE
          </span>
        </div>

        {/* AI Pose Estimation SVG Overlay */}
        <svg
          viewBox="0 0 100 100"
          className="absolute inset-0 w-full h-full"
          preserveAspectRatio="xMidYMid meet"
          style={{ filter: `drop-shadow(0 0 ${glowPulse ? "8px" : "4px"} rgba(16,185,129,${glowPulse ? "0.9" : "0.6"}))`, transition: "filter 0.6s ease" }}
        >
          {/* Silhouette body hint */}
          <ellipse cx="50" cy="10" rx="6" ry="7" fill="rgba(16,185,129,0.08)" stroke="rgba(16,185,129,0.25)" strokeWidth="0.5" />
          <rect x="43" y="25" width="14" height="18" rx="3" fill="rgba(16,185,129,0.06)" stroke="rgba(16,185,129,0.2)" strokeWidth="0.5" />

          {/* Skeleton bones */}
          {bones.map((b) => (
            <line
              key={b.label}
              x1={b.x1}
              y1={b.y1}
              x2={b.x2}
              y2={b.y2}
              stroke="#10B981"
              strokeWidth="0.8"
              strokeLinecap="round"
              opacity="0.85"
            />
          ))}

          {/* Joint dots */}
          {joints.map((j) => (
            <g key={j.label}>
              <circle cx={j.cx} cy={j.cy} r={j.r + 2} fill="rgba(16,185,129,0.15)" />
              <circle cx={j.cx} cy={j.cy} r={j.r} fill="#10B981" opacity="0.95" />
              <circle cx={j.cx} cy={j.cy} r={j.r * 0.45} fill="#D1FAE5" />
            </g>
          ))}

          {/* Angle arc at right elbow */}
          <path
            d="M 68,30 Q 74,32 72,35"
            fill="none"
            stroke="#34D399"
            strokeWidth="0.6"
            opacity="0.8"
          />
          <text x="77" y="32" fill="#34D399" fontSize="2.8" fontFamily="monospace" fontWeight="bold">
            {currentAngle}°
          </text>
        </svg>

        {/* Patient label */}
        <div className="absolute bottom-4 left-4 right-4 flex items-end justify-between">
          <div>
            <div style={{ color: "rgba(148,163,184,0.8)", fontSize: "10px", fontFamily: "monospace", letterSpacing: "0.06em" }}>
              PATIENT CAM — AI POSE
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Activity size={12} color="#10B981" />
            <span style={{ color: "#10B981", fontSize: "10px", fontFamily: "monospace" }}>TRACKING</span>
          </div>
        </div>

        {/* Reps Counter Overlay */}
        <div
          className="absolute top-10 right-3 rounded-xl px-3 py-2 text-center"
          style={{
            background: "rgba(10,15,30,0.75)",
            backdropFilter: "blur(8px)",
            border: "1px solid rgba(16,185,129,0.3)",
          }}
        >
          <div style={{ color: "rgba(148,163,184,0.7)", fontSize: "9px", fontFamily: "monospace", letterSpacing: "0.1em" }}>
            REPS
          </div>
          <div style={{ color: "#F8FAFC", fontSize: "28px", fontWeight: 700, lineHeight: 1, letterSpacing: "-0.02em" }}>
            {reps}
          </div>
          <div style={{ color: "#10B981", fontSize: "11px", fontFamily: "monospace" }}>
            / 15
          </div>
        </div>
      </div>

      {/* Bottom White Card */}
      <div
        className="mx-4 mt-3 rounded-2xl flex-1 flex flex-col overflow-hidden"
        style={{
          background: "#ffffff",
          boxShadow: "0 -2px 24px rgba(0,0,0,0.12), 0 4px 32px rgba(0,0,0,0.08)",
          minHeight: 0,
        }}
      >
        <div className="px-4 pt-4 pb-2 flex items-center justify-between">
          <div>
            <span style={{ color: "#1E293B", fontSize: "13px", fontWeight: 600 }}>
              Real-time Joint Angle
            </span>
            <span style={{ color: "#64748B", fontSize: "11px", fontFamily: "monospace", marginLeft: "8px" }}>
              Elbow — Right
            </span>
          </div>
          <div
            className="px-2 py-0.5 rounded-full"
            style={{ background: "#D1FAE5" }}
          >
            <span style={{ color: "#065F46", fontSize: "12px", fontWeight: 700, fontFamily: "monospace" }}>
              {currentAngle}°
            </span>
          </div>
        </div>

        <div className="flex-1 px-2" style={{ minHeight: "80px" }}>
          <ResponsiveContainer width="100%" height={90}>
            <LineChart data={angleData} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,41,59,0.06)" />
              <XAxis
                dataKey="t"
                tick={{ fill: "#94A3B8", fontSize: 9, fontFamily: "monospace" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#94A3B8", fontSize: 9, fontFamily: "monospace" }}
                domain={[0, 160]}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "#1E293B",
                  border: "none",
                  borderRadius: "8px",
                  fontSize: "11px",
                  color: "#F8FAFC",
                  fontFamily: "monospace",
                }}
                formatter={(v: number) => [`${v}°`, "Angle"]}
              />
              <Line
                type="monotone"
                dataKey="angle"
                stroke="#10B981"
                strokeWidth={2.5}
                dot={{ fill: "#10B981", r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: "#10B981", stroke: "#D1FAE5", strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Form Feedback Banner */}
        <div
          className="mx-3 mb-4 mt-1 rounded-xl py-3 flex items-center justify-center gap-2"
          style={{
            background: formStatus === "perfect" ? "#10B981" : "#FEF2F2",
            border: formStatus === "perfect" ? "none" : "1px solid #FECACA",
          }}
        >
          {formStatus === "perfect" ? (
            <>
              <span style={{ fontSize: "16px" }}>✅</span>
              <span style={{ color: "#ffffff", fontSize: "14px", fontWeight: 700, letterSpacing: "-0.01em" }}>
                Perfect Form
              </span>
            </>
          ) : (
            <>
              <span style={{ fontSize: "16px" }}>⚠️</span>
              <span style={{ color: "#DC2626", fontSize: "14px", fontWeight: 600 }}>
                Keep back straight!
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
