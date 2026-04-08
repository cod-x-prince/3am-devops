import { useMemo, useState } from "react";
import { Activity, Play, Square, Wifi, WifiOff } from "lucide-react";

import { useEpisodeStream } from "./hooks/useEpisodeStream";
import { ServiceGraph } from "./components/ServiceGraph";
import { MetricsFeed } from "./components/MetricsFeed";
import { AgentLog } from "./components/AgentLog";
import { ScoreCard } from "./components/ScoreCard";

const SCENARIOS = ["bad_deploy", "memory_leak", "cascade_timeout"];

export default function App() {
  const [scenario, setScenario] = useState("bad_deploy");
  const [mode, setMode] = useState("untrained");

  const {
    frames,
    latestFrame,
    connectionStatus,
    error,
    isRunning,
    startEpisode,
    stopEpisode,
  } = useEpisodeStream();

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
              Mock-first mode for Track B while Track A finishes engine handoff.
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

        <section className="mb-6 grid gap-3 rounded-xl border border-zinc-700/80 bg-black/30 p-4 md:grid-cols-[1fr_1fr_auto_auto] md:items-end">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-300">Scenario</span>
            <select
              className="rounded-md border border-zinc-600 bg-zinc-900 px-3 py-2"
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
            >
              {SCENARIOS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-300">Policy Mode</span>
            <select
              className="rounded-md border border-zinc-600 bg-zinc-900 px-3 py-2"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="untrained">untrained</option>
              <option value="trained">trained</option>
            </select>
          </label>

          <button
            className="inline-flex items-center justify-center gap-2 rounded-md bg-terminal-green px-4 py-2 font-semibold text-black transition hover:brightness-110"
            onClick={() => startEpisode({ scenario, mode })}
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
