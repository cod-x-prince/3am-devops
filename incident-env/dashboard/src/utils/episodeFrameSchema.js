function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function sanitizeService(service, index) {
  if (!service || typeof service !== "object") {
    return null;
  }

  const id = typeof service.id === "string" ? service.id : `service_${index}`;
  const health = isFiniteNumber(service.health) ? service.health : 0;
  const cpu = isFiniteNumber(service.cpu) ? service.cpu : 0;
  const memory = isFiniteNumber(service.memory) ? service.memory : 0;
  const errorRate = isFiniteNumber(service.error_rate) ? service.error_rate : 0;
  const latencyP99 = isFiniteNumber(service.latency_p99)
    ? service.latency_p99
    : 0;
  const status =
    typeof service.status === "string" ? service.status : "degraded";

  return {
    id,
    health,
    cpu,
    memory,
    error_rate: errorRate,
    latency_p99: latencyP99,
    status,
  };
}

function sanitizeConnection(connection) {
  if (!connection || typeof connection !== "object") {
    return null;
  }
  if (
    typeof connection.source !== "string" ||
    typeof connection.target !== "string"
  ) {
    return null;
  }

  return {
    source: connection.source,
    target: connection.target,
    strength: isFiniteNumber(connection.strength) ? connection.strength : 0.4,
  };
}

export function normalizeEpisodeFrame(rawFrame) {
  if (!rawFrame || typeof rawFrame !== "object") {
    return null;
  }
  if (
    !isFiniteNumber(rawFrame.tick) ||
    !isFiniteNumber(rawFrame.cumulative_reward)
  ) {
    return null;
  }
  if (
    !Array.isArray(rawFrame.services) ||
    !Array.isArray(rawFrame.connections)
  ) {
    return null;
  }
  if (typeof rawFrame.episode_done !== "boolean") {
    return null;
  }

  const services = rawFrame.services
    .map((service, index) => sanitizeService(service, index))
    .filter(Boolean);
  const connections = rawFrame.connections
    .map(sanitizeConnection)
    .filter(Boolean);

  if (!services.length) {
    return null;
  }

  return {
    tick: rawFrame.tick,
    services,
    connections,
    last_action:
      typeof rawFrame.last_action === "string" ? rawFrame.last_action : null,
    last_action_target:
      typeof rawFrame.last_action_target === "string"
        ? rawFrame.last_action_target
        : null,
    cumulative_reward: rawFrame.cumulative_reward,
    episode_done: rawFrame.episode_done,
    resolution_status:
      typeof rawFrame.resolution_status === "string"
        ? rawFrame.resolution_status
        : "in_progress",
    scores:
      rawFrame.scores && typeof rawFrame.scores === "object"
        ? rawFrame.scores
        : {},
    llm_reasoning:
      typeof rawFrame.llm_reasoning === "string"
        ? rawFrame.llm_reasoning
        : null,
  };
}
