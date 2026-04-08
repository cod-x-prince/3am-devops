import { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function MetricsFeed({ frames }) {
  const series = useMemo(() => {
    return (frames ?? []).slice(-40).map((frame) => {
      const services = frame.services ?? [];
      const avg = (picker) => {
        if (!services.length) return 0;
        return (
          services.reduce((sum, service) => sum + picker(service), 0) /
          services.length
        );
      };

      return {
        tick: frame.tick,
        error_rate: avg((s) => s.error_rate),
        latency_p99: avg((s) => s.latency_p99),
        cpu: avg((s) => s.cpu),
      };
    });
  }, [frames]);

  return (
    <div className="rounded-xl border border-zinc-700/80 bg-black/30 p-4">
      <h2 className="mb-3 text-lg font-semibold text-terminal-cyan">
        Metrics Feed
      </h2>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="h-52 rounded-lg bg-[#070b16] p-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series}>
              <CartesianGrid stroke="#1f2937" strokeDasharray="2 2" />
              <XAxis dataKey="tick" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip />
              <Legend />
              <Area
                type="monotone"
                dataKey="error_rate"
                stroke="#ff3333"
                fill="#ff333344"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="h-52 rounded-lg bg-[#070b16] p-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series}>
              <CartesianGrid stroke="#1f2937" strokeDasharray="2 2" />
              <XAxis dataKey="tick" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="latency_p99"
                stroke="#00ccff"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="h-52 rounded-lg bg-[#070b16] p-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={series}>
              <CartesianGrid stroke="#1f2937" strokeDasharray="2 2" />
              <XAxis dataKey="tick" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip />
              <Legend />
              <Bar dataKey="cpu" fill="#00ff88" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
