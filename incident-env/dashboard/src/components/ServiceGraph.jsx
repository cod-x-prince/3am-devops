import { useEffect, useMemo, useRef } from "react";
import * as d3 from "d3";

const WIDTH = 760;
const HEIGHT = 420;

function colorFromStatus(status) {
  if (status === "healthy") return "#00ff88";
  if (status === "degraded") return "#ffcc00";
  if (status === "critical") return "#ff8800";
  return "#ff3333";
}

export function ServiceGraph({ frame }) {
  const svgRef = useRef(null);

  const data = useMemo(() => {
    const services = frame?.services ?? [];
    const connections = frame?.connections ?? [];
    return {
      nodes: services.map((s) => ({ ...s })),
      links: connections.map((c) => ({ ...c })),
    };
  }, [frame]);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    if (data.nodes.length === 0) {
      svg
        .append("text")
        .attr("x", WIDTH / 2)
        .attr("y", HEIGHT / 2)
        .attr("text-anchor", "middle")
        .attr("fill", "#9ca3af")
        .text("Start an episode to see service topology");
      return;
    }

    const link = svg
      .append("g")
      .attr("stroke", "#334155")
      .selectAll("line")
      .data(data.links)
      .join("line")
      .attr("stroke-width", (d) => Math.max(1.2, (d.strength ?? 0.4) * 3));

    const node = svg.append("g").selectAll("g").data(data.nodes).join("g");

    node
      .append("circle")
      .attr("r", 18)
      .attr("fill", (d) => colorFromStatus(d.status))
      .attr("stroke", "#111827")
      .attr("stroke-width", 2)
      .attr("opacity", 0.95);

    const pulseNodes = node
      .filter((d) => d.status === "critical" || d.status === "down")
      .append("circle")
      .attr("r", 18)
      .attr("fill", "none")
      .attr("stroke", (d) => colorFromStatus(d.status))
      .attr("stroke-width", 2)
      .attr("opacity", 0.7);

    const pulse = () => {
      pulseNodes
        .attr("r", 18)
        .attr("opacity", 0.7)
        .transition()
        .duration(900)
        .attr("r", 30)
        .attr("opacity", 0)
        .on("end", pulse);
    };
    pulse();

    node
      .append("text")
      .text((d) => d.id.replace("service_", "s"))
      .attr("text-anchor", "middle")
      .attr("dy", 4)
      .attr("font-size", 10)
      .attr("fill", "#020617")
      .attr("font-weight", 700);

    node.append("title").text((d) => {
      return `${d.id}\nstatus=${d.status}\nhealth=${d.health.toFixed(2)}\ncpu=${d.cpu.toFixed(2)}\nerr=${d.error_rate.toFixed(2)}`;
    });

    const simulation = d3
      .forceSimulation(data.nodes)
      .force(
        "link",
        d3
          .forceLink(data.links)
          .id((d) => d.id)
          .distance(90)
          .strength(0.5),
      )
      .force("charge", d3.forceManyBody().strength(-220))
      .force("center", d3.forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collision", d3.forceCollide().radius(26));

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);

      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => simulation.stop();
  }, [data]);

  return (
    <div className="rounded-xl border border-zinc-700/80 bg-black/30 p-4">
      <h2 className="mb-2 text-lg font-semibold text-terminal-cyan">
        Service Graph
      </h2>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-[420px] w-full rounded-lg bg-[#05070f]"
      />
    </div>
  );
}
