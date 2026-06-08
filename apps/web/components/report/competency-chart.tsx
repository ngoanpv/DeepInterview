"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { CompetencyScore } from "@deepinterview/shared";

const ACCENT = "#4338ca";
const LINE = "#e7e3da";
const MUTED = "#73737b";

/**
 * Calm radar of competency scores on a fixed 0-5 domain. Client island —
 * recharts needs the DOM. The parent passes plain serializable
 * `competency_scores`; we map to recharts' row shape here.
 *
 * ResponsiveContainer collapses to 0 inside auto-height parents, so the wrapper
 * has an explicit height.
 */
export function CompetencyChart({
  competencies,
}: {
  competencies: CompetencyScore[];
}) {
  const data = competencies.map((c) => ({
    competency: c.competency,
    score: c.score,
  }));

  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke={LINE} />
          <PolarAngleAxis
            dataKey="competency"
            tick={{ fill: MUTED, fontSize: 11 }}
          />
          <PolarRadiusAxis
            domain={[0, 5]}
            tickCount={6}
            tick={{ fill: "#9a9aa1", fontSize: 10 }}
            axisLine={false}
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke={ACCENT}
            fill={ACCENT}
            fillOpacity={0.14}
            strokeWidth={2}
            dot={{ r: 2.5, fill: ACCENT, strokeWidth: 0 }}
          />
          <Tooltip
            formatter={(value: number | string) => [`${value} / 5`, "Score"]}
            contentStyle={{
              borderRadius: 10,
              border: `1px solid ${LINE}`,
              fontSize: 12,
              boxShadow: "0 12px 28px -18px rgba(20,20,30,0.25)",
            }}
            labelStyle={{ color: "#17171a", fontWeight: 600 }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
