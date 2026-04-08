import { useEffect, useState } from "react";

const HUMAN_AVG_SECONDS = 4.2 * 3600;

function pretty(value, digits = 2) {
  return Number.isFinite(value) ? value.toFixed(digits) : "0.00";
}

function useCountUp(target, durationMs = 500) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const safeTarget = Number.isFinite(target) ? target : 0;
    const startValue = value;
    const delta = safeTarget - startValue;
    const start = performance.now();
    let raf = 0;

    const step = (now) => {
      const t = Math.min(1, (now - start) / durationMs);
      setValue(startValue + delta * t);
      if (t < 1) {
        raf = requestAnimationFrame(step);
      }
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  return value;
}

export function ScoreCard({ frame }) {
  const mttr = frame?.scores?.mttr ?? 0;
  const blast = frame?.scores?.blast_radius ?? 0;
  const falseAlarms = frame?.scores?.false_alarm_count ?? 0;
  const ticks = frame?.tick ?? 0;
  const agentSeconds = Math.max(0.1, ticks * 0.1);
  const speedup = HUMAN_AVG_SECONDS / agentSeconds;

  const mttrAnimated = useCountUp(mttr, 350);
  const blastAnimated = useCountUp(blast, 350);
  const falseAnimated = useCountUp(falseAlarms, 350);
  const speedupAnimated = useCountUp(speedup, 450);

  return (
    <div className="rounded-xl border border-zinc-700/80 bg-black/30 p-4">
      <h2 className="mb-3 text-lg font-semibold text-terminal-cyan">
        Score Card
      </h2>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-[#070b16] p-3">
          <p className="text-xs text-zinc-400">MTTR</p>
          <p className="text-xl font-bold text-terminal-green">
            {pretty(mttrAnimated)}
          </p>
        </div>
        <div className="rounded-lg bg-[#070b16] p-3">
          <p className="text-xs text-zinc-400">Blast</p>
          <p className="text-xl font-bold text-terminal-yellow">
            {pretty(blastAnimated)}
          </p>
        </div>
        <div className="rounded-lg bg-[#070b16] p-3">
          <p className="text-xs text-zinc-400">False Alarms</p>
          <p className="text-xl font-bold text-terminal-red">
            {pretty(falseAnimated, 0)}
          </p>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-terminal-cyan/40 bg-[#071327] p-4">
        <p className="text-sm text-zinc-300">Human SRE average: 4.2 hours</p>
        <p className="text-sm text-zinc-300">
          Agent time: {pretty(agentSeconds, 1)} seconds
        </p>
        <p className="mt-2 text-2xl font-bold text-terminal-cyan">
          {speedupAnimated.toFixed(0)}x speedup
        </p>
      </div>
    </div>
  );
}
