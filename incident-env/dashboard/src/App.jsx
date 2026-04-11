import { useEffect, useMemo, useState } from "react";
import { Activity, Play, Square, Wifi, WifiOff } from "lucide-react";

import { useEpisodeStream } from "./hooks/useEpisodeStream";
import { ServiceGraph } from "./components/ServiceGraph";
import { MetricsFeed } from "./components/MetricsFeed";
import { AgentLog } from "./components/AgentLog";
import { ScoreCard } from "./components/ScoreCard";

const API_BASE =
  import.meta.env.VITE_API_BASE ??
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");
const FALLBACK_SCENARIOS = [
  { id: "bad_deploy", name: "Bad Deploy" },
  { id: "memory_leak", name: "Memory Leak" },
  { id: "cascade_timeout", name: "Cascade Timeout" },
  { id: "thundering_herd", name: "Thundering Herd" },
  { id: "split_brain", name: "Split Brain" },
  { id: "multi_fault", name: "Multi Fault" },
];
const FALLBACK_AGENTS = [
  { id: "random", label: "Random Agent" },
  { id: "greedy", label: "Greedy Heuristic" },
  { id: "four_stage", label: "4-Stage Agent" },
  { id: "trained", label: "Trained PPO" },
];
const FALLBACK_EXECUTION_MODES = [
  { id: "benchmark", label: "Benchmark Mode" },
  { id: "reality", label: "Reality Mode" },
];

export default function App() {
  const [scenario, setScenario] = useState("bad_deploy");
  const [agentMode, setAgentMode] = useState("random");
  const [scenarioOptions, setScenarioOptions] = useState(FALLBACK_SCENARIOS);
  const [agentOptions, setAgentOptions] = useState(FALLBACK_AGENTS);
  const [executionMode, setExecutionMode] = useState("benchmark");
  const [executionModeOptions, setExecutionModeOptions] = useState(
    FALLBACK_EXECUTION_MODES,
  );
  const [traceOptionsByScenario, setTraceOptionsByScenario] = useState({});
  const [traceId, setTraceId] = useState(null);
  const [optionsError, setOptionsError] = useState(null);

  const {
    frames,
    latestFrame,
    connectionStatus,
    error,
    warning,
    isRunning,
    startEpisode,
    stopEpisode,
  } = useEpisodeStream();

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function loadOptions() {
      try {
        const response = await fetch(`${API_BASE}/episode/options`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`Failed to fetch episode options (${response.status})`);
        }

        const payload = await response.json();
        if (cancelled) {
          return;
        }

        if (Array.isArray(payload.scenarios) && payload.scenarios.length > 0) {
          const normalizedScenarios = payload.scenarios
            .map((item) =>
              item && typeof item === "object" && typeof item.id === "string"
                ? {
                    id: item.id,
                    name:
                      typeof item.name === "string" && item.name.length
                        ? item.name
                        : item.id,
                  }
                : null,
            )
            .filter(Boolean);
          if (normalizedScenarios.length > 0) {
            setScenarioOptions(normalizedScenarios);
            setScenario((prev) =>
              normalizedScenarios.some((item) => item.id === prev)
                ? prev
                : normalizedScenarios[0].id,
            );
          }
        }

        if (Array.isArray(payload.agents) && payload.agents.length > 0) {
          const normalizedAgents = payload.agents
            .map((item) =>
              item && typeof item === "object" && typeof item.id === "string"
                ? {
                    id: item.id,
                    label:
                      typeof item.label === "string" && item.label.length
                        ? item.label
                        : item.id,
                  }
                : null,
            )
            .filter(Boolean);
          if (normalizedAgents.length > 0) {
            setAgentOptions(normalizedAgents);
            setAgentMode((prev) =>
              normalizedAgents.some((item) => item.id === prev)
                ? prev
                : typeof payload.default_agent === "string" &&
                    normalizedAgents.some((item) => item.id === payload.default_agent)
                  ? payload.default_agent
                  : normalizedAgents[0].id,
            );
          }
        }

        if (
          Array.isArray(payload.execution_modes) &&
          payload.execution_modes.length > 0
        ) {
          const normalizedModes = payload.execution_modes
            .map((item) =>
              item && typeof item === "object" && typeof item.id === "string"
                ? {
                    id: item.id,
                    label:
                      typeof item.label === "string" && item.label.length
                        ? item.label
                        : item.id,
                  }
                : null,
            )
            .filter(Boolean);
          if (normalizedModes.length > 0) {
            setExecutionModeOptions(normalizedModes);
            setExecutionMode((prev) =>
              normalizedModes.some((item) => item.id === prev)
                ? prev
                : typeof payload.default_execution_mode === "string" &&
                    normalizedModes.some(
                      (item) => item.id === payload.default_execution_mode,
                    )
                  ? payload.default_execution_mode
                  : normalizedModes[0].id,
            );
          }
        }

        if (payload.traces && typeof payload.traces === "object") {
          setTraceOptionsByScenario(payload.traces);
        }

        setOptionsError(null);
      } catch (loadError) {
        if (!cancelled) {
          setOptionsError(
            loadError instanceof Error ? loadError.message : "Failed to load options",
          );
        }
      }
    }

    loadOptions();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  const traceOptions = useMemo(() => {
    const options = traceOptionsByScenario?.[scenario];
    return Array.isArray(options) ? options : [];
  }, [scenario, traceOptionsByScenario]);

  useEffect(() => {
    if (executionMode !== "reality") {
      setTraceId(null);
      return;
    }
    if (!traceOptions.length) {
      setTraceId(null);
      return;
    }
    setTraceId((prev) =>
      traceOptions.some((item) => item.trace_id === prev)
        ? prev
        : traceOptions[0].trace_id,
    );
  }, [executionMode, traceOptions]);

  const statusTone = useMemo(() => {
    if (["connected", "completed"].includes(connectionStatus))
      return "text-terminal-green";
    if (["error", "stopped"].includes(connectionStatus))
      return "text-terminal-red";
    return "text-terminal-yellow";
  }, [connectionStatus]);

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top,#0a1120_0%,#080810_50%,#05050a_100%)] text-white">
      <div className="mx-auto max-w-[1400px] px-4 pb-8 pt-6">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-terminal-cyan/40 bg-black/30 p-4 shadow-[0_0_30px_rgba(0,204,255,0.1)]">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-terminal-cyan">
              IncidentEnv Live Ops Board
            </h1>
            <p className="text-sm text-zinc-300">
              Real IncidentEnv runtime with full scenario and agent strategy controls.
            </p>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span
              className={`flex items-center gap-2 font-semibold ${statusTone}`}
            >
              {connectionStatus === "connected" ? (
                <Wifi size={16} />
              ) : (
                <WifiOff size={16} />
              )}
              {connectionStatus}
            </span>
            <span className="inline-flex items-center gap-2 rounded-md border border-zinc-600 px-2 py-1 text-zinc-300">
              <Activity size={14} />
              {frames.length} frames
            </span>
          </div>
        </header>

        <section className="mb-6 grid gap-3 rounded-xl border border-zinc-700/80 bg-black/30 p-4 md:grid-cols-[1fr_1fr_1fr_1fr_auto_auto] md:items-end">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-300">Scenario</span>
            <select
              className="rounded-md border border-zinc-600 bg-zinc-900 px-3 py-2"
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
            >
              {scenarioOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-300">Agent Strategy</span>
            <select
              className="rounded-md border border-zinc-600 bg-zinc-900 px-3 py-2"
              value={agentMode}
              onChange={(e) => setAgentMode(e.target.value)}
            >
              {agentOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-300">Execution Mode</span>
            <select
              className="rounded-md border border-zinc-600 bg-zinc-900 px-3 py-2"
              value={executionMode}
              onChange={(e) => setExecutionMode(e.target.value)}
            >
              {executionModeOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-300">Trace</span>
            <select
              className="rounded-md border border-zinc-600 bg-zinc-900 px-3 py-2"
              value={traceId ?? ""}
              onChange={(e) => setTraceId(e.target.value || null)}
              disabled={executionMode !== "reality" || traceOptions.length === 0}
            >
              {executionMode !== "reality" ? (
                <option value="">Auto (benchmark)</option>
              ) : traceOptions.length === 0 ? (
                <option value="">Auto (config trace)</option>
              ) : (
                traceOptions.map((item) => (
                  <option key={item.trace_id} value={item.trace_id}>
                    {item.trace_id}
                  </option>
                ))
              )}
            </select>
          </label>

          <button
            className="inline-flex items-center justify-center gap-2 rounded-md bg-terminal-green px-4 py-2 font-semibold text-black transition hover:brightness-110"
            onClick={() =>
              startEpisode({
                scenario,
                mode: agentMode,
                executionMode,
                traceId,
              })
            }
            disabled={isRunning}
          >
            <Play size={16} /> Start
          </button>

          <button
            className="inline-flex items-center justify-center gap-2 rounded-md border border-terminal-red px-4 py-2 font-semibold text-terminal-red transition hover:bg-terminal-red/10"
            onClick={stopEpisode}
            disabled={!isRunning}
          >
            <Square size={16} /> Stop
          </button>
        </section>

        {error ? (
          <p className="mb-4 text-sm text-terminal-red">{error}</p>
        ) : null}
        {warning ? (
          <p className="mb-4 text-sm text-terminal-yellow">{warning}</p>
        ) : null}
        {optionsError ? (
          <p className="mb-4 text-sm text-terminal-yellow">
            Options fallback: {optionsError}
          </p>
        ) : null}

        <main className="grid gap-4 lg:grid-cols-12">
          <section className="lg:col-span-7">
            <ServiceGraph frame={latestFrame} />
          </section>
          <section className="lg:col-span-5">
            <ScoreCard frame={latestFrame} />
          </section>
          <section className="lg:col-span-8">
            <MetricsFeed frames={frames} />
          </section>
          <section className="lg:col-span-4">
            <AgentLog frames={frames} />
          </section>
        </main>
      </div>
    </div>
  );
}
