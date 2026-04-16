"use client";

import { useEffect, useMemo, useState } from "react";
import PredictionChart from "./PredictionChart";
import CyclistSelector from "./CyclistSelector";
import TrainingRidePreview from "./TrainingRidePreview";
import { commonPipelineStyles, predictionPageStyles } from "./pipelineStyles";

interface RideData {
  datetime: string;
  n_points: number;
  columns: string[];
  data: Record<string, unknown>[];
}

interface ComparisonResponse {
  ok: boolean;
  train_ride_1: number;
  train_ride_2: number;
  test_ride: number;
  ride_data: RideData;
  model1_predictions: number[];
  model2_predictions: number[];
  metrics: {
    rmse_model1: number;
    rmse_model2: number;
    mae_model1: number;
    mae_model2: number;
    r2_model1: number;
    r2_model2: number;
  };
}

interface AuthUser {
  id: string;
  email: string;
  display_name?: string | null;
  role: string;
}

interface ModelComparisonProps {
  authToken: string;
  apiUrl: string;
}

export default function ModelComparison({
  authToken,
  apiUrl,
}: ModelComparisonProps) {
  const [selectedCyclist, setSelectedCyclist] = useState("");
  const [selectedTrainRide1, setSelectedTrainRide1] = useState(1);
  const [selectedTrainRide2, setSelectedTrainRide2] = useState(2);
  const [selectedTestRide, setSelectedTestRide] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comparisonResult, setComparisonResult] =
    useState<ComparisonResponse | null>(null);
  const [maxTrainRideIndex, setMaxTrainRideIndex] = useState(1);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [modelDisplay, setModelDisplay] = useState<"both" | "A" | "B">("both");

  const authHeaders = useMemo(() => {
    return { Authorization: `Bearer ${authToken}` };
  }, [authToken]);

  const chartModels = useMemo(() => {
    if (modelDisplay === "A") {
      return ["compare_model_a"];
    }
    if (modelDisplay === "B") {
      return ["compare_model_b"];
    }
    return ["compare_model_a", "compare_model_b"];
  }, [modelDisplay]);

  const chartRideData = useMemo(() => {
    if (!comparisonResult) {
      return null;
    }

    return {
      ...comparisonResult.ride_data,
      data: comparisonResult.ride_data.data.map((point, idx) => ({
        ...point,
        compare_model_a: comparisonResult.model1_predictions[idx] ?? null,
        compare_model_b: comparisonResult.model2_predictions[idx] ?? null,
      })),
    };
  }, [comparisonResult]);

  const isAdmin = authUser?.role === "admin";

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const response = await fetch(`${apiUrl}/auth/me`, {
          headers: authHeaders,
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || `HTTP ${response.status}`);
        }
        setAuthUser(payload.user as AuthUser);
      } catch {
        // Silently fail - user will just work with restricted cyclist list
      }
    };

    if (authToken) {
      fetchUser();
    }
  }, [apiUrl, authHeaders, authToken]);

  const handleSelectCyclist = (cyclist: string) => {
    setSelectedCyclist(cyclist);
  };

  const handleRunComparison = async () => {
    if (!selectedCyclist) {
      setError("Veuillez sélectionner un cycliste");
      return;
    }

    if (selectedTrainRide1 === selectedTrainRide2) {
      setError("Veuillez sélectionner deux sorties d'entraînement différentes");
      return;
    }

    if (
      selectedTrainRide1 === selectedTestRide ||
      selectedTrainRide2 === selectedTestRide
    ) {
      setError(
        "La sortie de test doit être différente des sorties d'entraînement",
      );
      return;
    }

    setLoading(true);
    setError(null);
    setComparisonResult(null);

    try {
      const dirPath = `../DB/rides/${selectedCyclist}`;
      const response = await fetch(
        `${apiUrl}/pipeline/compare-models-trained`,
        {
          method: "POST",
          headers: {
            ...authHeaders,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            dir_path: dirPath,
            train_ride_index_1: selectedTrainRide1,
            train_ride_index_2: selectedTrainRide2,
            test_ride_index: selectedTestRide,
          }),
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload?.detail || `Erreur HTTP ${response.status}`);
      }

      setComparisonResult(payload);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erreur lors de la comparaison",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={commonPipelineStyles.sectionStack}>
      {/* Configuration Section */}
      <div className={commonPipelineStyles.card}>
        <h2 className={commonPipelineStyles.sectionTitle}>Configuration</h2>
        <div className={commonPipelineStyles.blockStack}>
          {/* Cyclist Selection */}
          <div>
            <CyclistSelector
              onSelectCyclist={handleSelectCyclist}
              authToken={authToken}
              selectedCyclist={selectedCyclist}
              isAdmin={isAdmin}
              onMaxRideIndexChange={setMaxTrainRideIndex}
            />
          </div>

          {/* Training Rides Selection */}
          {selectedCyclist && (
            <div className={commonPipelineStyles.blockStack}>
              <h3 className={commonPipelineStyles.subSectionTitle}>
                Sorties d&apos;entraînement
              </h3>
              <p className={commonPipelineStyles.bodyText}>
                Sélectionnez deux sorties différentes pour entraîner deux
                modèles
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Training Ride 1 */}
                <div className="space-y-2">
                  <label
                    htmlFor="train-ride-1"
                    className={commonPipelineStyles.formLabel}
                  >
                    Sortie d&apos;entraînement 1 (Modèle A)
                  </label>
                  <input
                    id="train-ride-1"
                    type="number"
                    min="1"
                    max={maxTrainRideIndex}
                    value={selectedTrainRide1}
                    onChange={(e) =>
                      setSelectedTrainRide1(Number.parseInt(e.target.value, 10))
                    }
                    className={commonPipelineStyles.emphasizedInput}
                  />
                  <p className={commonPipelineStyles.mutedText}>
                    Max: {maxTrainRideIndex}
                  </p>
                </div>

                {/* Training Ride 2 */}
                <div className="space-y-2">
                  <label
                    htmlFor="train-ride-2"
                    className={commonPipelineStyles.formLabel}
                  >
                    Sortie d&apos;entraînement 2 (Modèle B)
                  </label>
                  <input
                    id="train-ride-2"
                    type="number"
                    min="1"
                    max={maxTrainRideIndex}
                    value={selectedTrainRide2}
                    onChange={(e) =>
                      setSelectedTrainRide2(Number.parseInt(e.target.value, 10))
                    }
                    className={commonPipelineStyles.emphasizedInput}
                  />
                  <p className={commonPipelineStyles.mutedText}>
                    Max: {maxTrainRideIndex}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Test Ride Selection */}
          {selectedCyclist && (
            <div>
              <label
                htmlFor="test-ride"
                className={commonPipelineStyles.formLabel}
              >
                Sortie de test (numéro)
              </label>
              <input
                id="test-ride"
                type="number"
                min="0"
                value={selectedTestRide}
                onChange={(e) =>
                  setSelectedTestRide(Number.parseInt(e.target.value, 10))
                }
                className={commonPipelineStyles.emphasizedInput}
              />
              <p className={commonPipelineStyles.mutedText}>
                Sortie à comparer
              </p>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className={predictionPageStyles.errorPanel}>
              <p className={predictionPageStyles.errorPanelTitle}>Erreur</p>
              <p className={predictionPageStyles.errorPanelBody}>{error}</p>
            </div>
          )}

          {/* Run Comparison Button */}
          <button
            type="button"
            onClick={handleRunComparison}
            disabled={loading || !selectedCyclist}
            className={predictionPageStyles.runButton}
          >
            {loading ? "Comparaison en cours..." : "Lancer la comparaison"}
          </button>
        </div>
      </div>

      {/* Training Ride Preview */}
      {selectedCyclist && (
        <TrainingRidePreview
          cyclist={selectedCyclist}
          rideIndex={selectedTrainRide1}
          authToken={authToken}
        />
      )}

      {/* Comparison Results */}
      {comparisonResult && (
        <div className={commonPipelineStyles.sectionStack}>
          {/* Metrics Comparison */}
          <div className={commonPipelineStyles.card}>
            <h2 className={commonPipelineStyles.sectionTitle}>
              Métriques de Comparaison
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* RMSE Comparison */}
              <div className="border rounded-lg p-4 bg-gray-50">
                <p className="text-sm font-semibold text-gray-600 mb-2">RMSE</p>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-700">
                      Sortie {selectedTrainRide1} (Mod A)
                    </span>
                    <span className="text-sm font-mono font-bold text-blue-600">
                      {comparisonResult.metrics.rmse_model1.toFixed(3)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-700">
                      Sortie {selectedTrainRide2} (Mod B)
                    </span>
                    <span className="text-sm font-mono font-bold text-emerald-600">
                      {comparisonResult.metrics.rmse_model2.toFixed(3)}
                    </span>
                  </div>
                  <div className="pt-2 border-t mt-2">
                    <span className="text-xs text-gray-500">
                      Diff:{" "}
                      {(
                        comparisonResult.metrics.rmse_model1 -
                        comparisonResult.metrics.rmse_model2
                      ).toFixed(3)}
                    </span>
                  </div>
                </div>
              </div>

              {/* MAE Comparison */}
              <div className="border rounded-lg p-4 bg-gray-50">
                <p className="text-sm font-semibold text-gray-600 mb-2">MAE</p>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-700">
                      Sortie {selectedTrainRide1} (Mod A)
                    </span>
                    <span className="text-sm font-mono font-bold text-blue-600">
                      {comparisonResult.metrics.mae_model1.toFixed(3)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-700">
                      Sortie {selectedTrainRide2} (Mod B)
                    </span>
                    <span className="text-sm font-mono font-bold text-emerald-600">
                      {comparisonResult.metrics.mae_model2.toFixed(3)}
                    </span>
                  </div>
                  <div className="pt-2 border-t mt-2">
                    <span className="text-xs text-gray-500">
                      Diff:{" "}
                      {(
                        comparisonResult.metrics.mae_model1 -
                        comparisonResult.metrics.mae_model2
                      ).toFixed(3)}
                    </span>
                  </div>
                </div>
              </div>

              {/* R² Comparison */}
              <div className="border rounded-lg p-4 bg-gray-50">
                <p className="text-sm font-semibold text-gray-600 mb-2">R²</p>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-700">
                      Sortie {selectedTrainRide1} (Mod A)
                    </span>
                    <span className="text-sm font-mono font-bold text-blue-600">
                      {comparisonResult.metrics.r2_model1.toFixed(3)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-700">
                      Sortie {selectedTrainRide2} (Mod B)
                    </span>
                    <span className="text-sm font-mono font-bold text-emerald-600">
                      {comparisonResult.metrics.r2_model2.toFixed(3)}
                    </span>
                  </div>
                  <div className="pt-2 border-t mt-2">
                    <span className="text-xs text-gray-500">
                      Diff:{" "}
                      {(
                        comparisonResult.metrics.r2_model1 -
                        comparisonResult.metrics.r2_model2
                      ).toFixed(3)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Predictions Charts */}
          <div className={commonPipelineStyles.card}>
            <div className="flex items-center justify-between mb-6">
              <h2 className={commonPipelineStyles.sectionTitle}>
                Visualisation des Prédictions (Sortie de test #
                {selectedTestRide})
              </h2>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setModelDisplay("both")}
                  className={`px-3 py-1.5 text-sm font-semibold rounded transition-colors ${
                    modelDisplay === "both"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                  }`}
                >
                  Tous les deux
                </button>
                <button
                  type="button"
                  onClick={() => setModelDisplay("A")}
                  className={`px-3 py-1.5 text-sm font-semibold rounded transition-colors ${
                    modelDisplay === "A"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                  }`}
                >
                  Modèle A
                </button>
                <button
                  type="button"
                  onClick={() => setModelDisplay("B")}
                  className={`px-3 py-1.5 text-sm font-semibold rounded transition-colors ${
                    modelDisplay === "B"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                  }`}
                >
                  Modèle B
                </button>
              </div>
            </div>

            {chartRideData && (
              <PredictionChart rideData={chartRideData} models={chartModels} />
            )}
          </div>

          {/* Data Table */}
          <div className={commonPipelineStyles.card}>
            <h2 className={commonPipelineStyles.sectionTitle}>
              Valeurs Détaillées
            </h2>

            <div className={predictionPageStyles.tableWrapper}>
              <table className={predictionPageStyles.table}>
                <thead>
                  <tr className={predictionPageStyles.tableHeadRow}>
                    <th className={predictionPageStyles.tableHeaderCell}>
                      Index
                    </th>
                    <th className={predictionPageStyles.tableHeaderCell}>
                      Réel
                    </th>
                    {(modelDisplay === "both" || modelDisplay === "A") && (
                      <th className={predictionPageStyles.tableHeaderCell}>
                        Mod A (sortie {selectedTrainRide1})
                      </th>
                    )}
                    {(modelDisplay === "both" || modelDisplay === "B") && (
                      <th className={predictionPageStyles.tableHeaderCell}>
                        Mod B (sortie {selectedTrainRide2})
                      </th>
                    )}
                    {modelDisplay === "both" && (
                      <th className={predictionPageStyles.tableHeaderCell}>
                        Diff
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {comparisonResult.ride_data.data
                    .slice(0, 50)
                    .map((point: Record<string, unknown>, idx: number) => {
                      const actual =
                        (point.heart_rate as number) ||
                        (point.hr as number) ||
                        0;
                      const pred1 =
                        comparisonResult.model1_predictions[idx] || 0;
                      const pred2 =
                        comparisonResult.model2_predictions[idx] || 0;
                      const rowKey = `${String(point.t_min ?? idx)}-${pred1}-${pred2}`;
                      return (
                        <tr
                          key={rowKey}
                          className={predictionPageStyles.tableRow}
                        >
                          <td className={predictionPageStyles.tableCell}>
                            {idx}
                          </td>
                          <td className={predictionPageStyles.tableCell}>
                            {actual.toFixed(2)}
                          </td>
                          {(modelDisplay === "both" ||
                            modelDisplay === "A") && (
                            <td className={predictionPageStyles.tableCell}>
                              {pred1.toFixed(2)}
                            </td>
                          )}
                          {(modelDisplay === "both" ||
                            modelDisplay === "B") && (
                            <td className={predictionPageStyles.tableCell}>
                              {pred2.toFixed(2)}
                            </td>
                          )}
                          {modelDisplay === "both" && (
                            <td className={predictionPageStyles.tableCell}>
                              {(pred1 - pred2).toFixed(2)}
                            </td>
                          )}
                        </tr>
                      );
                    })}
                </tbody>
              </table>
              <p className={predictionPageStyles.tableFooter}>
                Affichage des 50 premières lignes
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
