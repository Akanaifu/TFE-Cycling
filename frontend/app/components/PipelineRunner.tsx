"use client";

import React, { useState } from "react";
import PredictionChart from "./PredictionChart";
import RideSelector from "./RideSelector";
import CyclistSelector from "./CyclistSelector";
import TrainingRidePreview from "./TrainingRidePreview";

interface RideData {
  datetime: string;
  n_points: number;
  columns: string[];
  data: Record<string, any>[];
}

interface PipelineResponse {
  ok: boolean;
  n_rides: number;
  models_requested: string[];
  models_computed: string[];
  rides: RideData[];
}

export default function PipelineRunner() {
  const [selectedCyclist, setSelectedCyclist] = useState("cyclist9");
  const [selectedModels, setSelectedModels] = useState<string[]>([
    "pred_arx_selected",
  ]);
  const [selectedTrainRide, setSelectedTrainRide] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResponse | null>(null);
  const [selectedRideIndex, setSelectedRideIndex] = useState(0);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const dirPath = `../../notebook/rides/${selectedCyclist}`;

      const response = await fetch(`${apiUrl}/pipeline/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          dir_path: dirPath,
          selected_models_compute: selectedModels,
          prev_ride: 1,
          nan_ratio: 1.0,
          selected_train_ride: selectedTrainRide,
          selected_target_rides: null,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data: PipelineResponse = await response.json();
      setResult(data);
      setSelectedRideIndex(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
    } finally {
      setLoading(false);
    }
  };

  const availableModels = [
    { id: "pred_hist", label: "Historique" },
    { id: "pred_default", label: "Régression simple" },
    { id: "pred_no_fuite", label: "ARX sans fuite" },
    { id: "pred_arx_selected", label: "ARX sélectionné" },
  ];

  const toggleModel = (modelId: string) => {
    setSelectedModels((prev) =>
      prev.includes(modelId)
        ? prev.filter((m) => m !== modelId)
        : [...prev, modelId],
    );
  };

  const currentRide = result?.rides[selectedRideIndex];

  return (
    <div className="w-full max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">
          Pipeline de Prédictions HR
        </h1>
        <p className="text-gray-600 mt-2">
          Sélectionnez un cycliste, configurez le modèle d'entrainement, puis
          lancez l'analyse prédictive
        </p>
      </div>

      {/* Section 1: Cyclist Selection */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          1. Sélectionner le cycliste
        </h2>
        <CyclistSelector
          selectedCyclist={selectedCyclist}
          onSelectCyclist={setSelectedCyclist}
          fromRideIndex={selectedTrainRide}
          onRideIndexChange={setSelectedTrainRide}
        />
      </div>

      {/* Section 2: Training Ride Preview */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          2. Ride d'entraînement
        </h2>
        <TrainingRidePreview
          cyclist={selectedCyclist}
          rideIndex={selectedTrainRide}
        />
      </div>

      {/* Section 3: Model Configuration & Run */}
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          3. Configuration et exécution
        </h2>

        {/* Model Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Modèles à calculer
          </label>
          <div className="grid grid-cols-2 gap-3">
            {availableModels.map((model) => (
              <label
                key={model.id}
                className="flex items-center space-x-2 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedModels.includes(model.id)}
                  onChange={() => toggleModel(model.id)}
                  className="w-4 h-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">{model.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Run Button */}
        <button
          onClick={handleRun}
          disabled={loading || selectedModels.length === 0}
          className="w-full bg-blue-600 text-white py-3 px-4 rounded-md font-semibold hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Exécution en cours..." : "Exécuter le pipeline"}
        </button>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-800 font-medium">Erreur:</p>
            <p className="text-red-700 text-sm mt-1">{error}</p>
          </div>
        )}
      </div>

      {/* Results Panel */}
      {result && (
        <div className="space-y-6">
          {/* Results Summary */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              Résultats de l'analyse
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 bg-gray-50 rounded">
                <p className="text-gray-600 text-sm">Nombre de rides</p>
                <p className="text-2xl font-bold text-gray-900">
                  {result.n_rides}
                </p>
              </div>
              <div className="p-4 bg-gray-50 rounded">
                <p className="text-gray-600 text-sm">Modèles calculés</p>
                <p className="text-sm font-mono font-semibold">
                  {result.models_computed.join(", ")}
                </p>
              </div>
              <div className="p-4 bg-gray-50 rounded">
                <p className="text-gray-600 text-sm">Points par ride</p>
                <p className="text-2xl font-bold text-gray-900">
                  {currentRide?.n_points || "-"}
                </p>
              </div>
            </div>
          </div>

          {/* Ride Selector */}
          <RideSelector
            rides={result.rides}
            selectedIndex={selectedRideIndex}
            onSelectRide={setSelectedRideIndex}
          />

          {/* Charts and Data */}
          {currentRide && (
            <div className="space-y-6">
              {/* Prediction Chart */}
              <PredictionChart
                rideData={currentRide}
                models={result.models_computed}
              />

              {/* Data Table */}
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Données détaillées
                </h3>
                <DataTable
                  rideData={currentRide}
                  models={result.models_computed}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DataTable({
  rideData,
  models,
}: {
  rideData: RideData;
  models: string[];
}) {
  const displayColumns = ["t", "t_min", "po", "hr", ...models];
  const filteredColumns = displayColumns.filter((col) =>
    rideData.columns.includes(col),
  );

  // Show every nth row to keep table manageable
  const step = Math.ceil(rideData.data.length / 50);
  const displayedData = rideData.data.filter((_, i) => i % step === 0);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-100 border-b">
            {filteredColumns.map((col) => (
              <th
                key={col}
                className="px-4 py-2 text-left font-semibold text-gray-900"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayedData.map((row, idx) => (
            <tr key={idx} className="border-b hover:bg-gray-50">
              {filteredColumns.map((col) => (
                <td
                  key={`${idx}-${col}`}
                  className="px-4 py-2 text-gray-700 font-mono text-xs"
                >
                  {typeof row[col] === "number"
                    ? row[col].toFixed(2)
                    : row[col]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-gray-500 mt-2">
        Affichage de {displayedData.length} points sur {rideData.data.length}
        (tous les {step} points)
      </p>
    </div>
  );
}
