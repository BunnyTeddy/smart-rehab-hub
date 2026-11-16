import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
} from "recharts";
import {
  CheckCircle2,
  XCircle,
  ChevronDown,
  TrendingUp,
} from "lucide-react";

const postureData = [
  { day: "Mon", accuracy: 74 },
  { day: "Tue", accuracy: 79 },
  { day: "Wed", accuracy: 76 },
  { day: "Thu", accuracy: 85 },
  { day: "Fri", accuracy: 88 },
  { day: "Sat", accuracy: 83 },
  { day: "Sun", accuracy: 91 },
];

const sessions = [
  {
    id: 1,
    datetime: "Today, 09:30 AM",
    exercise: "Bicep Curl",
    duration: "15 mins",
    completed: true,
    accuracy: 91,
  },
  {
    id: 2,
    datetime: "Today, 07:15 AM",
    exercise: "Shoulder Raise",
    duration: "12 mins",
    completed: true,
    accuracy: 88,
  },
  {
    id: 3,
    datetime: "Yesterday, 04:00 PM",
    exercise: "Wrist Flexion",
    duration: "10 mins",
    completed: false,
    accuracy: 62,
  },
  {
    id: 4,
    datetime: "Wed, 10:00 AM",
    exercise: "Arm Extension",
    duration: "18 mins",
    completed: true,
    accuracy: 85,
  },
  {
    id: 5,
    datetime: "Tue, 09:00 AM",
    exercise: "Bicep Curl",
    duration: "15 mins",
    completed: true,
    accuracy: 79,
  },
  {
    id: 6,
    datetime: "Mon, 08:30 AM",
    exercise: "Shoulder Raise",
    duration: "14 mins",
    completed: false,
    accuracy: 58,
  },
];

const weeklyAvg = Math.round(
  postureData.reduce((s, d) => s + d.accuracy, 0) / postureData.length
);

export function HistoryScreen() {
  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: "#F8FAFC" }}>
      {/* Top Bar */}
      <div
        className="flex items-center justify-between px-4 pt-12 pb-4"
        style={{ background: "#F8FAFC" }}
      >
        <h1 style={{ color: "#1E293B", fontSize: "22px", fontWeight: 700, letterSpacing: "-0.03em" }}>
          Rehab History
        </h1>
        {/* using <button> instead of <Button>: needs custom dropdown-style pill with text + icon, no matching kit variant */}
        <button
          className="flex items-center gap-1.5 rounded-full px-3 py-1.5"
          style={{
            background: "#ffffff",
            border: "1px solid rgba(30,41,59,0.1)",
            boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
          }}
        >
          <span style={{ color: "#1E293B", fontSize: "13px", fontWeight: 500 }}>
            This Week
          </span>
          <ChevronDown size={14} color="#64748B" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-24" style={{ scrollbarWidth: "none" }}>
        {/* Hero Chart Card */}
        <div
          className="rounded-2xl p-4 mb-4"
          style={{
            background: "#ffffff",
            boxShadow: "0 2px 20px rgba(0,0,0,0.06), 0 1px 4px rgba(0,0,0,0.04)",
          }}
        >
          <div className="flex items-start justify-between mb-3">
            <div>
              <p style={{ color: "#64748B", fontSize: "11px", fontFamily: "monospace", letterSpacing: "0.08em" }}>
                POSTURE ACCURACY
              </p>
              <div className="flex items-baseline gap-2 mt-0.5">
                <span style={{ color: "#1E293B", fontSize: "28px", fontWeight: 700, letterSpacing: "-0.03em" }}>
                  {weeklyAvg}%
                </span>
                <span style={{ color: "#64748B", fontSize: "12px" }}>weekly avg</span>
              </div>
            </div>
            <div
              className="flex items-center gap-1 px-2.5 py-1 rounded-full"
              style={{ background: "#D1FAE5" }}
            >
              <TrendingUp size={12} color="#10B981" />
              <span style={{ color: "#065F46", fontSize: "12px", fontWeight: 600 }}>
                +9%
              </span>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={postureData} margin={{ top: 8, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="2.5" result="coloredBlur" />
                  <feMerge>
                    <feMergeNode in="coloredBlur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,41,59,0.05)" vertical={false} />
              <XAxis
                dataKey="day"
                tick={{ fill: "#94A3B8", fontSize: 10, fontFamily: "monospace" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#94A3B8", fontSize: 9, fontFamily: "monospace" }}
                domain={[50, 100]}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "#1E293B",
                  border: "none",
                  borderRadius: "10px",
                  fontSize: "12px",
                  color: "#F8FAFC",
                  fontFamily: "monospace",
                  boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
                }}
                formatter={(v: number) => [`${v}%`, "Accuracy"]}
              />
              <Line
                type="monotone"
                dataKey="accuracy"
                stroke="#10B981"
                strokeWidth={2.5}
                filter="url(#glow)"
                dot={(props: any) => {
                  const { cx, cy, value } = props;
                  const isMax = value === Math.max(...postureData.map((d) => d.accuracy));
                  return (
                    <circle
                      key={`dot-${cx}-${cy}`}
                      cx={cx}
                      cy={cy}
                      r={isMax ? 6 : 4}
                      fill="#10B981"
                      stroke={isMax ? "#D1FAE5" : "#ffffff"}
                      strokeWidth={isMax ? 2.5 : 2}
                      style={isMax ? { filter: "drop-shadow(0 0 6px rgba(16,185,129,0.8))" } : {}}
                    />
                  );
                }}
                activeDot={{ r: 6, fill: "#10B981", stroke: "#D1FAE5", strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Recent Sessions */}
        <div className="mb-3">
          <span style={{ color: "#1E293B", fontSize: "16px", fontWeight: 700 }}>
            Recent Sessions
          </span>
        </div>

        <div className="flex flex-col gap-3">
          {sessions.map((s) => (
            <div
              key={s.id}
              className="rounded-2xl p-4"
              style={{
                background: "#ffffff",
                boxShadow: "0 1px 8px rgba(0,0,0,0.05), 0 0 1px rgba(0,0,0,0.06)",
              }}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p style={{ color: "#64748B", fontSize: "11px", fontFamily: "monospace", letterSpacing: "0.04em" }}>
                    {s.datetime}
                  </p>
                  <p style={{ color: "#1E293B", fontSize: "15px", fontWeight: 600, marginTop: "2px" }}>
                    {s.exercise}
                  </p>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span style={{ color: "#64748B", fontSize: "12px" }}>
                      ⏱ {s.duration}
                    </span>
                    <span style={{ color: "#64748B", fontSize: "12px", fontFamily: "monospace" }}>
                      {s.accuracy}% accuracy
                    </span>
                  </div>
                </div>
                <div
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-full ml-3 flex-shrink-0"
                  style={{
                    background: s.completed ? "#D1FAE5" : "#FEE2E2",
                  }}
                >
                  {s.completed ? (
                    <CheckCircle2 size={12} color="#10B981" />
                  ) : (
                    <XCircle size={12} color="#EF4444" />
                  )}
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      color: s.completed ? "#065F46" : "#DC2626",
                    }}
                  >
                    {s.completed ? "Completed" : "Incomplete"}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
