"use client";

import { commonPipelineStyles, predictionPageStyles } from "./pipelineStyles";

export interface BpmPointDiff {
  x: number;
  diff: number;
}

export interface BpmSummaryDiffRow {
  rideIndex: number;
  datetime: string;
  nPoints: number;
  meanDiff: number;
}

interface BpmDiffVisualizerProps {
  sectionTitle: string;
  sectionSubtitle?: string;
  pointChartTitle: string;
  pointSeries: BpmPointDiff[];
  pointXAxisLabel?: string;
  summaryChartTitle?: string;
  summarySubtitle?: string;
  summaryRows?: BpmSummaryDiffRow[];
}

const formatDateLabel = (value: string): string => {
  const trimmed = value.trim();
  if (!trimmed) {
    return "-";
  }
  if (trimmed.includes("T")) {
    return trimmed.split("T")[0];
  }
  return trimmed.length > 10 ? trimmed.slice(0, 10) : trimmed;
};

export default function BpmDiffVisualizer({
  sectionTitle,
  sectionSubtitle,
  summaryChartTitle,
  summarySubtitle,
  summaryRows,
}: BpmDiffVisualizerProps) {
  const hasSummary = Array.isArray(summaryRows) && summaryRows.length > 0;

  return (
    <div className={commonPipelineStyles.card}>
      <h2 className={commonPipelineStyles.sectionTitle}>{sectionTitle}</h2>
      {sectionSubtitle && (
        <p className={commonPipelineStyles.bodyText}>{sectionSubtitle}</p>
      )}

      {summaryChartTitle && (
        <div className="mt-6 rounded-2xl border border-[#d6e1ee] bg-white p-6 shadow-[0_20px_50px_rgba(0,0,0,0.14)]">
          <h3 className="mb-4 text-lg font-semibold text-[#250902]">
            {summaryChartTitle}
          </h3>
          {summarySubtitle && (
            <p className="mb-3 text-sm text-[#7c5a5d]">{summarySubtitle}</p>
          )}

          <svg width={900} height={470} className="bg-transparent">
            <title>Diff BPM moyen par ride</title>
            {(() => {
              if (!hasSummary || !summaryRows) {
                return (
                  <text
                    x={450}
                    y={210}
                    textAnchor="middle"
                    className="text-sm fill-[#335372]"
                  >
                    Pas de différences disponibles.
                  </text>
                );
              }

              const sorted = [...summaryRows].sort(
                (a, b) => a.rideIndex - b.rideIndex,
              );

              const minDiff = Math.min(...sorted.map((r) => r.meanDiff));
              const maxDiff = Math.max(...sorted.map((r) => r.meanDiff));
              const pad = Math.max(1, (maxDiff - minDiff) * 0.15 || 1);
              const yMin = minDiff - pad;
              const yMax = maxDiff + pad;
              const yRange = Math.max(1e-9, yMax - yMin);

              const scaleX = (index: number) => {
                if (sorted.length === 1) {
                  return 450;
                }
                return 75 + (index / (sorted.length - 1)) * 750;
              };
              const scaleY = (value: number) =>
                350 - ((value - yMin) / yRange) * 300;

              const linePath = sorted
                .map((ride, idx) => {
                  const x = scaleX(idx);
                  const y = scaleY(ride.meanDiff);
                  return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
                })
                .join(" ");

              const yTicks = [0, 0.25, 0.5, 0.75, 1].map((tick) => {
                const value = yMin + tick * (yMax - yMin);
                return { value, y: scaleY(value) };
              });

              const zeroInRange = yMin <= 0 && yMax >= 0;

              return (
                <>
                  {yTicks.map((tick) => (
                    <line
                      key={`mean-h-${tick.value.toFixed(2)}`}
                      x1={75}
                      y1={tick.y}
                      x2={825}
                      y2={tick.y}
                      stroke="#cfdbe8"
                      strokeWidth="1"
                    />
                  ))}

                  <line
                    x1={75}
                    y1={50}
                    x2={75}
                    y2={350}
                    stroke="#001d3d"
                    strokeWidth="2"
                  />
                  <line
                    x1={75}
                    y1={350}
                    x2={825}
                    y2={350}
                    stroke="#001d3d"
                    strokeWidth="2"
                  />

                  {zeroInRange && (
                    <line
                      x1={75}
                      y1={scaleY(0)}
                      x2={825}
                      y2={scaleY(0)}
                      stroke="#6b87a4"
                      strokeWidth="1"
                      strokeDasharray="5,5"
                    />
                  )}

                  <path
                    d={linePath}
                    fill="none"
                    stroke="#ffc300"
                    strokeWidth="2.5"
                  />

                  {sorted.map((ride, idx) => {
                    const x = scaleX(idx);
                    const y = scaleY(ride.meanDiff);
                    return (
                      <g key={`mean-point-${ride.rideIndex}-${ride.datetime}`}>
                        <circle cx={x} cy={y} r={4} fill="#ffd60a" />
                        <text
                          x={x + 6}
                          y={y - 6}
                          className="text-xs font-semibold fill-[#001d3d]"
                        >
                          {ride.meanDiff.toFixed(2)}
                        </text>
                        <text
                          x={x}
                          y={360}
                          textAnchor="end"
                          transform={`rotate(-35 ${x} 360)`}
                          className="text-xs fill-[#335372]"
                        >
                          {formatDateLabel(ride.datetime)}
                        </text>
                      </g>
                    );
                  })}

                  {yTicks.map((tick) => (
                    <text
                      key={`mean-yl-${tick.value.toFixed(2)}`}
                      x={65}
                      y={tick.y + 4}
                      textAnchor="end"
                      className="text-xs fill-[#335372]"
                    >
                      {tick.value.toFixed(1)}
                    </text>
                  ))}

                  <text
                    x={450}
                    y={422}
                    textAnchor="middle"
                    className="text-xs font-semibold fill-[#001d3d]"
                  >
                    Date de la sortie
                  </text>
                  <text
                    x={20}
                    y={200}
                    textAnchor="middle"
                    transform="rotate(-90 20 200)"
                    className="text-xs font-semibold fill-[#001d3d]"
                  >
                    Diff BPM moyenne
                  </text>
                </>
              );
            })()}
          </svg>

          {hasSummary && summaryRows && (
            <div
              className={predictionPageStyles.tableWrapper}
              style={{ marginTop: "20px" }}
            >
              <table className={predictionPageStyles.table}>
                <thead>
                  <tr className={predictionPageStyles.tableHeadRow}>
                    <th className={predictionPageStyles.tableHeaderCell}>
                      Sortie
                    </th>
                    <th className={predictionPageStyles.tableHeaderCell}>
                      Date/Heure
                    </th>
                    <th className={predictionPageStyles.tableHeaderCell}>
                      Points
                    </th>
                    <th className={predictionPageStyles.tableHeaderCell}>
                      Δ BPM moyen
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {summaryRows.map((ride) => (
                    <tr
                      key={`mean-row-${ride.rideIndex}-${ride.datetime}`}
                      className={predictionPageStyles.tableRow}
                    >
                      <td className={predictionPageStyles.tableCell}>
                        {ride.rideIndex}
                      </td>
                      <td className={predictionPageStyles.tableCell}>
                        {ride.datetime}
                      </td>
                      <td className={predictionPageStyles.tableCell}>
                        {ride.nPoints}
                      </td>
                      <td
                        className={predictionPageStyles.tableCell}
                        style={{
                          color: ride.meanDiff >= 0 ? "#3b82f6" : "#ef4444",
                          fontWeight: "bold",
                        }}
                      >
                        {ride.meanDiff.toFixed(2)} BPM
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
