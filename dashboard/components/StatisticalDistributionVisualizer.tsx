"use client";

import React, { useId } from "react";
import { AlertCircle, CheckCircle, Layers } from "lucide-react";
import { BOOTSTRAP_REPORT, HOLM_BONFERRONI_TASKS } from "@/lib/sample-data";

export default function StatisticalDistributionVisualizer() {
  const gradientId = useId();

  // Generate coordinates for an empirical bell-shaped bootstrap distribution
  // centered at -0.40 with standard deviation approx 0.12
  const points = [];
  const mean = BOOTSTRAP_REPORT.deltaMean;
  const std = 0.12;
  const minX = -0.85;
  const maxX = 0.15;
  const steps = 60;

  for (let i = 0; i <= steps; i++) {
    const x = minX + (i / steps) * (maxX - minX);
    const exponent = -0.5 * Math.pow((x - mean) / std, 2);
    const y = (1 / (std * Math.sqrt(2 * Math.PI))) * Math.exp(exponent);
    points.push({ x, y });
  }

  // Scale to SVG viewBox 0 0 700 220
  const svgWidth = 700;
  const svgHeight = 220;
  const paddingX = 40;
  const paddingBottom = 40;
  const paddingTop = 20;

  const mapX = (val: number) =>
    paddingX + ((val - minX) / (maxX - minX)) * (svgWidth - 2 * paddingX);
  const maxY = Math.max(...points.map((p) => p.y));
  const mapY = (val: number) =>
    svgHeight - paddingBottom - (val / maxY) * (svgHeight - paddingBottom - paddingTop);

  const pathD = points.reduce((acc, p, idx) => {
    const cmd = idx === 0 ? "M" : "L";
    return `${acc} ${cmd} ${mapX(p.x).toFixed(1)} ${mapY(p.y).toFixed(1)}`;
  }, "");

  // Area under curve
  const areaD = `${pathD} L ${mapX(points[points.length - 1].x).toFixed(1)} ${svgHeight - paddingBottom} L ${mapX(points[0].x).toFixed(1)} ${svgHeight - paddingBottom} Z`;

  // Specific markers
  const xNull = mapX(0.0);
  const xMean = mapX(mean);
  const xCiLower = mapX(BOOTSTRAP_REPORT.ciLower);
  const xCiUpper = mapX(BOOTSTRAP_REPORT.ciUpper);

  return (
    <div className="rounded-lg border border-[#27272a] bg-[#121214] p-5 shadow-sm">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#27272a] gap-2">
        <div className="flex items-center gap-2.5">
          <Layers className="h-4 w-4 text-zinc-400" />
          <h2 className="text-sm font-semibold font-mono text-zinc-100 uppercase tracking-wide">
            Paired Bootstrap Hypothesis Testing &amp; Regression Gate (N=10,000)
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {BOOTSTRAP_REPORT.isRegression ? (
            <span className="px-2.5 py-1 rounded bg-red-950/50 border border-red-800/80 text-red-300 font-mono text-xs font-semibold flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5" />
              REGRESSION CONFIRMED (CI Upper &lt; 0)
            </span>
          ) : (
            <span className="px-2.5 py-1 rounded bg-emerald-950/50 border border-emerald-800/80 text-emerald-300 font-mono text-xs font-semibold flex items-center gap-1.5">
              <CheckCircle className="h-3.5 w-3.5" />
              NO REGRESSION DETECTED
            </span>
          )}
        </div>
      </div>

      {/* Top 4 Statistical Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 py-4">
        <div className="p-3.5 rounded border border-[#27272a] bg-[#18181b] font-mono">
          <div className="text-[11px] text-zinc-500 uppercase tracking-wider mb-1">
            Empirical Delta Mean
          </div>
          <div className="text-xl font-bold text-red-400">
            {BOOTSTRAP_REPORT.deltaMean > 0 ? "+" : ""}
            {(BOOTSTRAP_REPORT.deltaMean * 100).toFixed(1)}%
          </div>
          <div className="text-[10px] text-zinc-500 mt-1">
            Candidate ({BOOTSTRAP_REPORT.candidateSuccessRate * 100}%) vs Base ({BOOTSTRAP_REPORT.baselineSuccessRate * 100}%)
          </div>
        </div>

        <div className="p-3.5 rounded border border-[#27272a] bg-[#18181b] font-mono">
          <div className="text-[11px] text-zinc-500 uppercase tracking-wider mb-1">
            95% Bootstrap CI
          </div>
          <div className="text-xl font-bold text-zinc-200">
            [{BOOTSTRAP_REPORT.ciLower.toFixed(3)}, {BOOTSTRAP_REPORT.ciUpper.toFixed(3)}]
          </div>
          <div className="text-[10px] text-red-400/90 mt-1">
            Upper bound strictly negative
          </div>
        </div>

        <div className="p-3.5 rounded border border-[#27272a] bg-[#18181b] font-mono">
          <div className="text-[11px] text-zinc-500 uppercase tracking-wider mb-1">
            Empirical p-value
          </div>
          <div className="text-xl font-bold text-indigo-400">
            {BOOTSTRAP_REPORT.pValue.toFixed(4)}
          </div>
          <div className="text-[10px] text-zinc-500 mt-1">
            alpha = 0.05 threshold
          </div>
        </div>

        <div className="p-3.5 rounded border border-[#27272a] bg-[#18181b] font-mono">
          <div className="text-[11px] text-zinc-500 uppercase tracking-wider mb-1">
            Monte Carlo Resamples
          </div>
          <div className="text-xl font-bold text-zinc-200">
            {BOOTSTRAP_REPORT.nResamples.toLocaleString()}
          </div>
          <div className="text-[10px] text-zinc-500 mt-1">
            Paired unit resampling
          </div>
        </div>
      </div>

      {/* Bootstrap Density Chart (SVG) */}
      <div className="rounded border border-[#27272a] bg-[#18181b] p-4">
        <div className="flex items-center justify-between text-xs font-mono text-zinc-400 mb-2">
          <span>Resampled Difference Distribution (\u0394 = Candidate - Baseline)</span>
          <div className="flex items-center gap-4 text-[11px]">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-red-400" /> Delta Mean (-0.400)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-400" /> 95% CI Range
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-zinc-400" /> Null (\u0394 = 0)
            </span>
          </div>
        </div>

        <div className="w-full overflow-x-auto">
          <svg
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            className="w-full h-48 select-none"
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#ef4444" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Baseline axis grid */}
            <line
              x1={paddingX}
              y1={svgHeight - paddingBottom}
              x2={svgWidth - paddingX}
              y2={svgHeight - paddingBottom}
              stroke="#2e2e33"
              strokeWidth="1"
            />

            {/* 95% Confidence Interval Shaded Area */}
            <rect
              x={xCiLower}
              y={paddingTop}
              width={xCiUpper - xCiLower}
              height={svgHeight - paddingBottom - paddingTop}
              fill="#f59e0b"
              fillOpacity="0.08"
            />

            {/* Distribution Curve and Fill */}
            <path d={areaD} fill={`url(#${gradientId})`} />
            <path d={pathD} fill="none" stroke="#ef4444" strokeWidth="2" />

            {/* CI Lower Bound line */}
            <line
              x1={xCiLower}
              y1={paddingTop}
              x2={xCiLower}
              y2={svgHeight - paddingBottom}
              stroke="#f59e0b"
              strokeWidth="1.5"
              strokeDasharray="4 3"
            />
            <text
              x={xCiLower}
              y={paddingTop + 12}
              fill="#f59e0b"
              fontSize="10"
              fontFamily="monospace"
              textAnchor="middle"
            >
              -0.667
            </text>

            {/* CI Upper Bound line */}
            <line
              x1={xCiUpper}
              y1={paddingTop}
              x2={xCiUpper}
              y2={svgHeight - paddingBottom}
              stroke="#f59e0b"
              strokeWidth="1.5"
              strokeDasharray="4 3"
            />
            <text
              x={xCiUpper}
              y={paddingTop + 12}
              fill="#f59e0b"
              fontSize="10"
              fontFamily="monospace"
              textAnchor="middle"
            >
              -0.133
            </text>

            {/* Delta Mean line */}
            <line
              x1={xMean}
              y1={paddingTop}
              x2={xMean}
              y2={svgHeight - paddingBottom}
              stroke="#ef4444"
              strokeWidth="2"
            />
            <text
              x={xMean}
              y={svgHeight - paddingBottom + 16}
              fill="#ef4444"
              fontSize="11"
              fontFamily="monospace"
              fontWeight="bold"
              textAnchor="middle"
            >
              Mean \u0394: -0.400
            </text>

            {/* Null Hypothesis line at 0 */}
            <line
              x1={xNull}
              y1={paddingTop}
              x2={xNull}
              y2={svgHeight - paddingBottom}
              stroke="#71717a"
              strokeWidth="1.5"
              strokeDasharray="3 3"
            />
            <text
              x={xNull}
              y={svgHeight - paddingBottom + 16}
              fill="#a1a1aa"
              fontSize="11"
              fontFamily="monospace"
              textAnchor="middle"
            >
              Null (\u0394 = 0)
            </text>
          </svg>
        </div>

        <div className="mt-2 text-xs font-mono text-zinc-400 leading-relaxed">
          <span className="font-semibold text-zinc-200">Mathematical Interpretation:</span> Because the upper boundary of the 95% bootstrap confidence interval ($-0.1333$) lies strictly below zero, and $p = 0.0012 &lt; 0.05$, we reject the null hypothesis of equal performance. The CI regression gate terminates with exit code 1 to prevent degraded agent models from merging.
        </div>
      </div>

      {/* Multi-Task Holm-Bonferroni Correction Table */}
      <div className="mt-5">
        <div className="flex items-center justify-between mb-2.5">
          <div className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-300">
            Multi-Task Holm-Bonferroni FWER Control Table
          </div>
          <div className="text-[11px] font-mono text-zinc-500">
            Family-Wise Error Rate controlled at \u03b1 = 0.05 across 5 benchmark tasks
          </div>
        </div>

        <div className="rounded border border-[#27272a] overflow-x-auto bg-[#18181b]">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <thead>
              <tr className="border-b border-[#27272a] bg-[#121214] text-zinc-400">
                <th className="py-2.5 px-3 font-medium">Task Identifier</th>
                <th className="py-2.5 px-3 font-medium">Description</th>
                <th className="py-2.5 px-3 font-medium">Base Pass</th>
                <th className="py-2.5 px-3 font-medium">Cand Pass</th>
                <th className="py-2.5 px-3 font-medium">Raw p-value</th>
                <th className="py-2.5 px-3 font-medium">Holm-Bonferroni p</th>
                <th className="py-2.5 px-3 font-medium">Null Rejected?</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#232328] text-zinc-300">
              {HOLM_BONFERRONI_TASKS.map((task) => (
                <tr key={task.taskId} className="hover:bg-[#1f1f24] transition-colors">
                  <td className="py-2.5 px-3 font-semibold text-zinc-200">{task.taskId}</td>
                  <td className="py-2.5 px-3 text-zinc-400">{task.description}</td>
                  <td className="py-2.5 px-3 text-emerald-400">{(task.baselinePassRate * 100).toFixed(0)}%</td>
                  <td className="py-2.5 px-3 text-amber-400">{(task.candidatePassRate * 100).toFixed(0)}%</td>
                  <td className="py-2.5 px-3 text-zinc-300">{task.rawPValue.toFixed(4)}</td>
                  <td className="py-2.5 px-3 text-indigo-300 font-semibold">{task.adjustedPValue.toFixed(4)}</td>
                  <td className="py-2.5 px-3">
                    {task.rejectedNull ? (
                      <span className="px-2 py-0.5 rounded bg-red-950/60 text-red-300 border border-red-800/80 text-[10px] font-bold">
                        REJECTED (REGRESSION)
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-zinc-800/60 text-zinc-400 border border-zinc-700/60 text-[10px]">
                        ACCEPTED (INCONCLUSIVE)
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
