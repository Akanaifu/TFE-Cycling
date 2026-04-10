"use client";

import React, { useEffect, useState } from "react";

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
      setLoading(true);
      setError(null);
      try {
        const apiUrl =
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(
          `${apiUrl}/rides/training-ride?cyclist=${cyclist}&ride_index=${rideIndex}`,
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
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-xl font-bold text-gray-900 mb-4">
        📊 Ride d&apos;entraînement - Modèle
      </h3>

      {loading && (
        <div className="text-center py-8">
          <p className="text-gray-500">Chargement des données...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-800 font-medium">Erreur:</p>
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {rideData && (
        <div className="space-y-4">
          {/* Header Info */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-600 font-medium">CYCLISTE</p>
              <p className="text-lg font-bold text-gray-900">
                {rideData.cyclist.replace("cyclist", "Cycliste ")}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 font-medium">RIDE #</p>
              <p className="text-lg font-bold text-gray-900">
                {rideData.ride_index}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 font-medium">DATE/HEURE</p>
              <p className="text-sm font-mono text-gray-900">
                {rideData.datetime}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 font-medium">POINTS</p>
              <p className="text-lg font-bold text-gray-900">
                {rideData.n_points}
              </p>
            </div>
          </div>

          {/* Statistics Grid */}
          <div className="border-t pt-4">
            <p className="text-sm font-semibold text-gray-700 mb-3">
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
          <div className="border-t pt-4">
            <p className="text-sm font-semibold text-gray-700 mb-2">
              Colonnes disponibles
            </p>
            <div className="flex flex-wrap gap-2">
              {rideData.columns.slice(0, 10).map((col) => (
                <span
                  key={col}
                  className="inline-block bg-slate-200 text-slate-900 border border-slate-400 px-2 py-1 rounded text-xs font-mono font-semibold"
                >
                  {col}
                </span>
              ))}
              {rideData.columns.length > 10 && (
                <span className="inline-block text-gray-500 text-xs">
                  +{rideData.columns.length - 10} autres
                </span>
              )}
            </div>
          </div>

          {/* Mini Data Preview Table */}
          <div className="border-t pt-4 overflow-x-auto">
            <p className="text-sm font-semibold text-gray-700 mb-2">
              Aperçu des données
            </p>
            <table className="w-full text-xs border border-slate-300 rounded-md overflow-hidden">
              <thead>
                <tr className="bg-slate-800 text-white border-b border-slate-900">
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
                    key={idx}
                    className={
                      idx % 2 === 0
                        ? "bg-white border-b border-slate-200"
                        : "bg-slate-100 border-b border-slate-200"
                    }
                  >
                    <td className="px-3 py-2 font-mono text-slate-900">
                      {formatNumber(row.t_min, 2)}
                    </td>
                    <td className="px-3 py-2 font-mono text-slate-900">
                      {formatNumber(row.hr, 0)}
                    </td>
                    <td className="px-3 py-2 font-mono text-slate-900">
                      {formatNumber(row.po, 0)}
                    </td>
                    <td className="px-3 py-2 font-mono text-slate-900">
                      {formatNumber(row.work, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-500 mt-2">
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
    red: "bg-red-50 border-red-200",
    blue: "bg-blue-50 border-blue-200",
    orange: "bg-orange-50 border-orange-200",
    green: "bg-green-50 border-green-200",
    purple: "bg-purple-50 border-purple-200",
  };

  const textColors: Record<string, string> = {
    red: "text-red-700",
    blue: "text-blue-700",
    orange: "text-orange-700",
    green: "text-green-700",
    purple: "text-purple-700",
  };

  return (
    <div
      className={`border rounded p-2 ${colorClasses[color] || colorClasses.red}`}
    >
      <p className="text-xs text-gray-600 truncate">{label}</p>
      <p className={`text-base font-bold ${textColors[color]} truncate`}>
        {value} <span className="text-xs">{unit}</span>
      </p>
    </div>
  );
}
