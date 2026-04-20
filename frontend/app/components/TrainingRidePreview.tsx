"use client";

import { useEffect, useState } from "react";

interface TrainingRideData {
  cyclist: string;
  ride_index: number;
  datetime: string;
  n_points: number;
  columns: string[];
  data: TrainingRideRow[];
  stats: {
    hr_mean: number | null;
    hr_min: number | null;
    hr_max: number | null;
    po_mean: number | null;
    po_max: number | null;
  };
}

interface TrainingRideRow {
  t_min?: number | null;
  hr?: number | null;
  po?: number | null;
  work?: number | null;
  [key: string]: string | number | boolean | null | undefined;
}

interface TrainingRidePreviewProps {
  cyclist: string;
  rideIndex: number;
}

export default function TrainingRidePreview({
  cyclist,
  rideIndex,
}: TrainingRidePreviewProps) {
  const [rideData, setRideData] = useState<TrainingRideData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatNumber = (value: unknown, decimals: number): string => {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value.toFixed(decimals);
    }
    return (0).toFixed(decimals);
  };

  useEffect(() => {
    const fetchRideData = async () => {
      if (!cyclist) {
        setRideData(null);
        setError(
          "Selectionne un cycliste pour charger la ride d'entrainement.",
        );
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL;
        const response = await fetch(
          `${apiUrl}/rides/training-ride?cyclist=${cyclist}&ride_index=${rideIndex}`,
          {
            credentials: "include",
          },
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const data: TrainingRideData = await response.json();
        setRideData(data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Erreur lors du chargement",
        );
      } finally {
        setLoading(false);
      }
    };

    fetchRideData();
  }, [cyclist, rideIndex]);

  return (
    <div className="rounded-2xl border border-white/10 bg-[#fff7f4] p-6 shadow-[0_20px_50px_rgba(0,0,0,0.18)]">
      <h3 className="mb-4 text-xl font-bold text-[#250902]">
        📊 Ride d&apos;entraînement - Modèle
      </h3>

      {loading && (
        <div className="text-center py-8">
          <p className="text-[#7c5a5d]">Chargement des données...</p>
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-red-800 font-medium">Erreur:</p>
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {rideData && (
        <div className="space-y-4">
          {/* Header Info */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs font-medium text-[#7c5a5d]">CYCLISTE</p>
              <p className="text-lg font-bold text-[#250902]">
                {rideData.cyclist.replace("cyclist", "Cycliste ")}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-[#7c5a5d]">RIDE #</p>
              <p className="text-lg font-bold text-[#250902]">
                {rideData.ride_index}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-[#7c5a5d]">DATE/HEURE</p>
              <p className="text-sm font-mono text-[#250902]">
                {rideData.datetime}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-[#7c5a5d]">POINTS</p>
              <p className="text-lg font-bold text-[#250902]">
                {rideData.n_points}
              </p>
            </div>
          </div>

          {/* Statistics Grid */}
          <div className="border-t border-[#f0d3cf] pt-4">
            <p className="mb-3 text-sm font-semibold text-[#4f1b1e]">
              Statistiques
            </p>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {rideData.stats.hr_mean !== null && (
                <StatsBox
                  label="FC Moyenne"
                  value={rideData.stats.hr_mean.toFixed(1)}
                  unit="bpm"
                  color="red"
                />
              )}
              {rideData.stats.hr_min !== null && (
                <StatsBox
                  label="FC Min"
                  value={rideData.stats.hr_min.toFixed(0)}
                  unit="bpm"
                  color="blue"
                />
              )}
              {rideData.stats.hr_max !== null && (
                <StatsBox
                  label="FC Max"
                  value={rideData.stats.hr_max.toFixed(0)}
                  unit="bpm"
                  color="orange"
                />
              )}
              {rideData.stats.po_mean !== null && (
                <StatsBox
                  label="Puissance Moyenne"
                  value={rideData.stats.po_mean.toFixed(0)}
                  unit="W"
                  color="green"
                />
              )}
              {rideData.stats.po_max !== null && (
                <StatsBox
                  label="Puissance Max"
                  value={rideData.stats.po_max.toFixed(0)}
                  unit="W"
                  color="purple"
                />
              )}
            </div>
          </div>

          {/* Data Summary */}
          <div className="border-t border-[#f0d3cf] pt-4">
            <p className="mb-2 text-sm font-semibold text-[#4f1b1e]">
              Colonnes disponibles
            </p>
            <div className="flex flex-wrap gap-2">
              {rideData.columns.slice(0, 10).map((col) => (
                <span
                  key={col}
                  className="inline-block rounded border border-[#640d14]/20 bg-[#f8d7d2]/40 px-2 py-1 font-mono text-xs font-semibold text-[#250902]"
                >
                  {col}
                </span>
              ))}
              {rideData.columns.length > 10 && (
                <span className="inline-block text-xs text-[#7c5a5d]">
                  +{rideData.columns.length - 10} autres
                </span>
              )}
            </div>
          </div>

          {/* Mini Data Preview Table */}
          <div className="border-t border-[#f0d3cf] pt-4 overflow-x-auto">
            <p className="mb-2 text-sm font-semibold text-[#4f1b1e]">
              Aperçu des données
            </p>
            <table className="w-full overflow-hidden rounded-md border border-[#f0d3cf] text-xs">
              <thead>
                <tr className="border-b border-[#640d14]/30 bg-[#38040e] text-[#fff4f1]">
                  <th className="px-3 py-2 text-left font-semibold tracking-wide">
                    t_min
                  </th>
                  <th className="px-3 py-2 text-left font-semibold tracking-wide">
                    hr
                  </th>
                  <th className="px-3 py-2 text-left font-semibold tracking-wide">
                    po
                  </th>
                  <th className="px-3 py-2 text-left font-semibold tracking-wide">
                    work
                  </th>
                </tr>
              </thead>
              <tbody>
                {rideData.data.slice(0, 5).map((row, idx) => (
                  <tr
                    key={`${String(row.t_min ?? "na")}-${String(row.hr ?? "na")}-${String(row.po ?? "na")}`}
                    className={
                      idx % 2 === 0
                        ? "bg-[#000814]/55 border-b border-[#003566]"
                        : "bg-[#001d3d]/75 border-b border-[#003566]"
                    }
                  >
                    <td className="px-3 py-2 font-mono text-[#fff8d6]">
                      {formatNumber(row.t_min, 2)}
                    </td>
                    <td className="px-3 py-2 font-mono text-[#fff8d6]">
                      {formatNumber(row.hr, 0)}
                    </td>
                    <td className="px-3 py-2 font-mono text-[#fff8d6]">
                      {formatNumber(row.po, 0)}
                    </td>
                    <td className="px-3 py-2 font-mono text-[#fff8d6]">
                      {formatNumber(row.work, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-[#9fb4d2]">
              Affichage des 5 premiers points
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function StatsBox({
  label,
  value,
  unit,
  color,
}: {
  label: string;
  value: string;
  unit: string;
  color: string;
}) {
  const colorClasses: Record<string, string> = {
    red: "bg-[#003566]/60 border-[#ffc300]/20",
    blue: "bg-[#001d3d] border-[#003566]",
    orange: "bg-[#003566]/70 border-[#ffc300]/30",
    green: "bg-[#001d3d] border-[#003566]",
    purple: "bg-[#003566]/65 border-[#ffc300]/25",
  };

  const textColors: Record<string, string> = {
    red: "text-[#fff8d6]",
    blue: "text-[#dbeafe]",
    orange: "text-[#ffd60a]",
    green: "text-[#fff8d6]",
    purple: "text-[#ffd60a]",
  };

  return (
    <div
      className={`border rounded p-2 ${colorClasses[color] || colorClasses.red}`}
    >
      <p className="truncate text-xs text-[#9fb4d2]">{label}</p>
      <p className={`text-base font-bold ${textColors[color]} truncate`}>
        {value} <span className="text-xs text-[#9fb4d2]">{unit}</span>
      </p>
    </div>
  );
}
