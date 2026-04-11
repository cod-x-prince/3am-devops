import { useCallback, useEffect, useRef, useState } from "react";
import { normalizeEpisodeFrame } from "../utils/episodeFrameSchema";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const WS_BASE = API_BASE.replace("http://", "ws://").replace(
  "https://",
  "wss://",
);

export function useEpisodeStream() {
  const [episodeId, setEpisodeId] = useState(null);
  const [frames, setFrames] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [warning, setWarning] = useState(null);
  const [isRunning, setIsRunning] = useState(false);

  const wsRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(false);
  const completedRef = useRef(false);

  const closeSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connectSocket = useCallback((id) => {
    if (!id) {
      return;
    }

    setConnectionStatus("connecting");
    const ws = new WebSocket(`${WS_BASE}/episode/stream/${id}`);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0;
      setConnectionStatus("connected");
      setError(null);
    };

    ws.onmessage = (event) => {
      let frame;
      try {
        frame = JSON.parse(event.data);
      } catch {
        setError("Received non-JSON websocket payload");
        return;
      }

      const normalized = normalizeEpisodeFrame(frame);
      if (!normalized) {
        setError("Received malformed frame payload");
        return;
      }

      setFrames((prev) => {
        const next = [...prev, normalized];
        return next.slice(-200);
      });

      if (normalized.episode_done) {
        completedRef.current = true;
        shouldReconnectRef.current = false;
        setIsRunning(false);
        setConnectionStatus("completed");
      }
    };

    ws.onerror = () => {
      setError("WebSocket error while streaming episode data");
    };

    ws.onclose = () => {
      wsRef.current = null;
      if (!shouldReconnectRef.current || completedRef.current) {
        return;
      }

      reconnectAttemptsRef.current += 1;
      const delayMs = Math.min(1500 * reconnectAttemptsRef.current, 8000);
      setConnectionStatus("reconnecting");
      window.setTimeout(() => connectSocket(id), delayMs);
    };
  }, []);

  const startEpisode = useCallback(
    async ({ scenario, mode, executionMode, traceId }) => {
      closeSocket();
      shouldReconnectRef.current = true;
      completedRef.current = false;
      setFrames([]);
      setError(null);
      setWarning(null);
      setConnectionStatus("starting");

      try {
        const res = await fetch(`${API_BASE}/episode/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            scenario,
            mode,
            execution_mode: executionMode ?? "benchmark",
            trace_id: traceId ?? null,
          }),
        });
        if (!res.ok) {
          throw new Error("Failed to start episode");
        }

        const payload = await res.json();
        setWarning(
          typeof payload.warning === "string" && payload.warning.length
            ? payload.warning
            : null,
        );
        setEpisodeId(payload.episode_id);
        setIsRunning(true);
        connectSocket(payload.episode_id);
      } catch (e) {
        setConnectionStatus("error");
        setIsRunning(false);
        setError(e instanceof Error ? e.message : "Unknown error");
      }
    },
    [closeSocket, connectSocket],
  );

  const stopEpisode = useCallback(async () => {
    if (!episodeId) {
      return;
    }
    shouldReconnectRef.current = false;
    setIsRunning(false);
    setConnectionStatus("stopping");
    try {
      await fetch(`${API_BASE}/episode/stop/${episodeId}`, { method: "POST" });
    } catch {
      // Best-effort stop request; close locally either way.
    }
    closeSocket();
    setConnectionStatus("stopped");
  }, [closeSocket, episodeId]);

  useEffect(() => {
    return () => {
      shouldReconnectRef.current = false;
      closeSocket();
    };
  }, [closeSocket]);

  return {
    episodeId,
    frames,
    latestFrame: frames[frames.length - 1] ?? null,
    connectionStatus,
    error,
    warning,
    isRunning,
    startEpisode,
    stopEpisode,
  };
}
