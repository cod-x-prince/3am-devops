import { useEffect, useMemo, useRef } from "react";

export function AgentLog({ frames }) {
  const listRef = useRef(null);
  const logs = useMemo(() => {
    return (frames ?? []).slice(-80).map((frame) => {
      const status = frame.resolution_status;
      const action = frame.last_action ?? "none";
      const target = frame.last_action_target ?? "n/a";
      return `[t${frame.tick}] action=${action} target=${target} status=${status} reward=${frame.cumulative_reward.toFixed(3)}`;
    });
  }, [frames]);

  const finalReasoning = useMemo(() => {
    const doneFrame = [...(frames ?? [])]
      .reverse()
      .find((f) => f.episode_done && f.llm_reasoning);
    return doneFrame?.llm_reasoning ?? null;
  }, [frames]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="rounded-xl border border-zinc-700/80 bg-black/30 p-4">
      <h2 className="mb-3 text-lg font-semibold text-terminal-cyan">
        Agent Log
      </h2>
      <div
        ref={listRef}
        className="h-[260px] overflow-auto rounded-lg border border-zinc-800 bg-[#05070f] p-2 text-xs text-zinc-200"
      >
        {logs.length === 0 ? (
          <p className="text-zinc-400">Waiting for streamed actions...</p>
        ) : (
          logs.map((line, idx) => (
            <p key={`${idx}-${line}`} className="mb-1 font-mono">
              {line}
            </p>
          ))
        )}
      </div>
      <div className="mt-3 rounded-lg border border-zinc-800 bg-[#09101e] p-3 text-sm text-zinc-300">
        <p className="mb-1 font-semibold text-terminal-yellow">Reasoning</p>
        <p>
          {finalReasoning ?? "Reasoning will appear when episode_done=true"}
        </p>
      </div>
    </div>
  );
}
