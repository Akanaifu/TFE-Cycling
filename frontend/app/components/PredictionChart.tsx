"use client";

interface RideData {
  datetime: string;
  n_points: number;
  columns: string[];
  data: Record<string, unknown>[];
}

const MODEL_LABELS: Record<string, string> = {
  pred_hist: "Modèle historique",
  pred_default: "Modèle défaut",
  pred_no_fuite: "Modèle sans fuite",
  pred_arx_selected: "Modèle ARX sélectionné",
  compare_model_a: "Modèle A",
  compare_model_b: "Modèle B",
};

export default function PredictionChart({
  rideData,
  models,
}: {
  rideData: RideData;
  models: string[];
}) {
  if (!rideData.data.length) {
    return <div className="text-gray-500">Pas de données disponibles</div>;
  }

  const toNumberOrNull = (value: unknown): number | null => {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string" && value.trim() !== "") {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
  };

  // Extract data for plotting
  const timeData = rideData.data.map((d) => toNumberOrNull(d.t_min));
  const hrActual = rideData.data.map((d) => toNumberOrNull(d.hr));
  const predictionSeries = models.map((model) =>
    rideData.data.map((d) => toNumberOrNull(d[model])),
  );

  const validTimes = timeData.filter((t): t is number => t !== null);
  const allHRValues = [hrActual, ...predictionSeries]
    .flat()
    .filter((h): h is number => h !== null);

  if (validTimes.length === 0 || allHRValues.length === 0) {
    return <div className="text-gray-500">Pas de données exploitables</div>;
  }

  const minTime = Math.min(...validTimes);
  const maxTime = Math.max(...validTimes);
  const minHRRaw = Math.min(...allHRValues);
  const maxHRRaw = Math.max(...allHRValues);

  // Keep some visual headroom so peaks are not clipped at chart boundaries.
  const hrPadding = Math.max(3, (maxHRRaw - minHRRaw) * 0.05);
  const minHR = minHRRaw - hrPadding;
  const maxHR = maxHRRaw + hrPadding;

  // Chart dimensions
  const chartWidth = 800;
  const chartHeight = 400;
  const padding = 60;
  const innerWidth = chartWidth - padding * 2;
  const innerHeight = chartHeight - padding * 2;

  // Scale functions
  const timeRange = Math.max(1e-9, maxTime - minTime);
  const hrRange = Math.max(1e-9, maxHR - minHR);

  const scaleX = (value: number) =>
    padding + ((value - minTime) / timeRange) * innerWidth;
  const scaleY = (value: number) =>
    padding + innerHeight - ((value - minHR) / hrRange) * innerHeight;

  // Colors for different models
  const colors: Record<string, string> = {
    actual: "#ad2831",
    pred_hist: "#640d14",
    pred_default: "#800e13",
    pred_no_fuite: "#f59e0b",
    pred_arx_selected: "#38040e",
    compare_model_a: "#ad2831",
    compare_model_b: "#640d14",
  };

  // Generate path string for SVG line
  const generatePath = (values: (number | null)[]): string => {
    let path = "";
    let isDrawing = false;

    for (let i = 0; i < values.length; i++) {
      const t = timeData[i];
      const v = values[i];
      if (t !== null && v !== null) {
        const x = scaleX(t);
        const y = scaleY(v);

        if (!isDrawing) {
          path += `M ${x} ${y}`;
          isDrawing = true;
        } else {
          path += ` L ${x} ${y}`;
        }
      } else {
        isDrawing = false;
      }
    }
    return path;
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-[#fff7f4] p-6 shadow-[0_20px_50px_rgba(0,0,0,0.18)]">
      <h3 className="mb-4 text-lg font-semibold text-[#250902]">
        Fréquence Cardiaque - Prédictions vs Réalité
      </h3>

      <div className="overflow-x-auto">
        <svg width={chartWidth} height={chartHeight} className="bg-transparent">
          <title>Frequence cardiaque: predictions vs realite</title>
          <defs>
            <clipPath id="chart-clip">
              <rect
                x={padding}
                y={padding}
                width={innerWidth}
                height={innerHeight}
              />
            </clipPath>
          </defs>

          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((t) => {
            const x = padding + t * innerWidth;
            return (
              <line
                key={`vgrid-${t}`}
                x1={x}
                y1={padding}
                x2={x}
                y2={padding + innerHeight}
                stroke="#f0d3cf"
                strokeWidth="1"
              />
            );
          })}

          {[0, 0.25, 0.5, 0.75, 1].map((t) => {
            const y = padding + (1 - t) * innerHeight;
            return (
              <line
                key={`hgrid-${t}`}
                x1={padding}
                y1={y}
                x2={padding + innerWidth}
                y2={y}
                stroke="#f0d3cf"
                strokeWidth="1"
              />
            );
          })}

          {/* Axes */}
          <line
            x1={padding}
            y1={padding}
            x2={padding}
            y2={padding + innerHeight}
            stroke="#250902"
            strokeWidth="2"
          />
          <line
            x1={padding}
            y1={padding + innerHeight}
            x2={padding + innerWidth}
            y2={padding + innerHeight}
            stroke="#250902"
            strokeWidth="2"
          />

          {/* Axis labels */}
          <text
            x={chartWidth / 2}
            y={chartHeight - 10}
            textAnchor="middle"
            className="text-xs"
          >
            Temps (min)
          </text>
          <text
            x={15}
            y={chartHeight / 2}
            textAnchor="middle"
            transform={`rotate(-90 15 ${chartHeight / 2})`}
            className="text-xs"
          >
            FC (bpm)
          </text>

          {/* Scale labels on axes */}
          {[0, 0.25, 0.5, 0.75, 1].map((t) => {
            const time = minTime + t * (maxTime - minTime);
            const x = padding + t * innerWidth;
            return (
              <text
                key={`xlabel-${t}`}
                x={x}
                y={padding + innerHeight + 20}
                textAnchor="middle"
                className="text-xs text-[#7c5a5d]"
              >
                {time.toFixed(1)}
              </text>
            );
          })}

          {[0, 0.25, 0.5, 0.75, 1].map((t) => {
            const hr = minHR + t * (maxHR - minHR);
            const y = padding + (1 - t) * innerHeight;
            return (
              <text
                key={`ylabel-${t}`}
                x={padding - 10}
                y={y + 4}
                textAnchor="end"
                className="text-xs text-[#7c5a5d]"
              >
                {hr.toFixed(0)}
              </text>
            );
          })}

          {/* Plot actual HR */}
          <g clipPath="url(#chart-clip)">
            <path
              d={generatePath(hrActual)}
              fill="none"
              stroke={colors.actual}
              strokeWidth="2"
            />

            {/* Plot model predictions */}
            {models.map((model, modelIdx) => (
              <path
                key={`path-${model}`}
                d={generatePath(predictionSeries[modelIdx])}
                fill="none"
                stroke={colors[model] || "#999"}
                strokeWidth="2"
                strokeDasharray="4,4"
              />
            ))}
          </g>
        </svg>
      </div>

      {/* Legend */}
      <div className="mt-6 flex flex-wrap gap-6">
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-0.5"
            style={{ backgroundColor: colors.actual }}
          />
          <span className="text-sm text-gray-700">FC réelle</span>
        </div>
        {models.map((model) => (
          <div key={`legend-${model}`} className="flex items-center gap-2">
            <div
              className="w-4 h-0.5 opacity-60"
              style={{
                backgroundColor: colors[model] || "#999",
                borderTop: "2px dashed currentColor",
              }}
            />
            <span className="text-sm text-gray-700">
              {MODEL_LABELS[model] || model}
            </span>
          </div>
        ))}
      </div>

      {/* Statistics */}
      <StatisticsTable rideData={rideData} models={models} />
    </div>
  );
}

function StatisticsTable({
  rideData,
  models,
}: {
  rideData: RideData;
  models: string[];
}) {
  const toNumberOrNull = (value: unknown): number | null => {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string" && value.trim() !== "") {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
  };

  const hr = rideData.data
    .map((d) => toNumberOrNull(d.hr))
    .filter((h): h is number => h !== null);

  const modelSeries = (model: string) =>
    rideData.data.map((d) => toNumberOrNull(d[model]));

  const calculateStats = (
    values: (number | null)[],
  ): { mean: number; rmse: number } => {
    const filtered = values.filter((v) => v !== null);
    if (filtered.length === 0) {
      return { mean: 0, rmse: 0 };
    }

    const mean =
      filtered.reduce((a, b) => a + (b as number), 0) / filtered.length;
    const rmse = Math.sqrt(
      filtered.reduce((acc, v) => acc + ((v as number) - mean) ** 2, 0) /
        filtered.length,
    );

    return { mean, rmse };
  };

  const calculateRMSE = (predicted: (number | null)[]): number => {
    const pairs = hr
      .map((h, i) => ({ actual: h, pred: predicted[i] }))
      .filter((p) => p.pred !== null);

    if (pairs.length === 0) return 0;

    const mse =
      pairs.reduce(
        (acc, p) => acc + ((p.actual as number) - (p.pred as number)) ** 2,
        0,
      ) / pairs.length;
    return Math.sqrt(mse);
  };

  return (
    <div className="mt-6">
      <h4 className="font-semibold text-gray-900 mb-3">Statistiques</h4>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-100 border-b">
            <th className="px-4 py-2 text-left font-semibold">Métrique</th>
            <th className="px-4 py-2 text-right font-semibold">FC réelle</th>
            {models.map((model) => (
              <th
                key={`header-${model}`}
                className="px-4 py-2 text-right font-semibold"
              >
                {MODEL_LABELS[model] || model}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="border-b">
            <td className="px-4 py-2 font-medium text-gray-700">Moyenne</td>
            <td className="px-4 py-2 text-right text-gray-700">
              {calculateStats(hr).mean.toFixed(1)}
            </td>
            {models.map((model) => (
              <td
                key={`mean-${model}`}
                className="px-4 py-2 text-right text-gray-700"
              >
                {calculateStats(modelSeries(model)).mean.toFixed(1)}
              </td>
            ))}
          </tr>
          <tr>
            <td className="px-4 py-2 font-medium text-gray-700">RMSE</td>
            <td className="px-4 py-2 text-right text-gray-700">-</td>
            {models.map((model) => (
              <td
                key={`rmse-${model}`}
                className="px-4 py-2 text-right text-gray-700"
              >
                {calculateRMSE(modelSeries(model)).toFixed(2)}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
