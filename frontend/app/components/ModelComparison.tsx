"use client";

import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent } from "react";
import BpmDiffVisualizer from "./BpmDiffVisualizer";
import PredictionChart from "./PredictionChart";
import InterpretationGuide from "./InterpretationGuide";
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
  all_rides_diffs?: Array<{
    ride_index: number;
    datetime: string;
    n_points: number;
    mean_bpm_diff: number;
  }>;
}

interface AuthUser {
  id: string;
  email: string;
  display_name?: string | null;
  role: string;
}

interface ModelComparisonProps {
  apiUrl: string;
}

export default function ModelComparison({ apiUrl }: ModelComparisonProps) {
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
  const [previewModel, setPreviewModel] = useState<"A" | "B">("A");
  const [applyToAllRides, setApplyToAllRides] = useState(false);
  const [allRidesDiffs, setAllRidesDiffs] = useState<Array<{
    ride_index: number;
    datetime: string;
    n_points: number;
    mean_bpm_diff: number;
  }> | null>(null);

  const handleApplyToAllRidesChange = (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const checked = event.target.checked;
    setApplyToAllRides(checked);
    if (!checked) {
      setAllRidesDiffs(null);
    }
  };

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

  const pointDiffSeries = useMemo(() => {
    if (!comparisonResult) {
      return [] as Array<{ x: number; diff: number }>;
    }

    return comparisonResult.model1_predictions
      .map((modelA, idx) => {
        const modelB = comparisonResult.model2_predictions[idx];
        const point = comparisonResult.ride_data.data[idx];
        const tMinRaw = point?.t_min;
        const tMin =
          typeof tMinRaw === "number"
            ? tMinRaw
            : typeof tMinRaw === "string"
              ? Number(tMinRaw)
              : idx;

        if (!Number.isFinite(modelA) || !Number.isFinite(modelB)) {
          return null;
        }
        return {
          x: Number.isFinite(tMin) ? tMin : idx,
          diff: modelA - modelB,
        };
      })
      .filter((point): point is { x: number; diff: number } => point !== null);
  }, [comparisonResult]);

  const summaryDiffRows = useMemo(() => {
    if (!allRidesDiffs || !Array.isArray(allRidesDiffs)) {
      return [] as Array<{
        rideIndex: number;
        datetime: string;
        nPoints: number;
        meanDiff: number;
      }>;
    }

    return allRidesDiffs.map((ride) => ({
      rideIndex: ride.ride_index,
      datetime: ride.datetime,
      nPoints: ride.n_points,
      meanDiff: ride.mean_bpm_diff,
    }));
  }, [allRidesDiffs]);

  const getFiniteExtrema = (values: number[]) => {
    const finiteValues = values.filter((value) => Number.isFinite(value));
    if (finiteValues.length === 0) {
      return { min: null as number | null, max: null as number | null };
    }

    return {
      min: Math.min(...finiteValues),
      max: Math.max(...finiteValues),
    };
  };

  const isAdmin = authUser?.role === "admin";

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const response = await fetch(`${apiUrl}/auth/me`, {
          credentials: "include",
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

    fetchUser();
  }, [apiUrl]);

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
    setAllRidesDiffs(null);

    try {
      const dirPath = `../DB/rides/${selectedCyclist}`;
      const response = await fetch(
        `${apiUrl}/pipeline/compare-models-trained`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            dir_path: dirPath,
            train_ride_index_1: selectedTrainRide1,
            train_ride_index_2: selectedTrainRide2,
            test_ride_index: selectedTestRide,
            apply_to_all_rides: applyToAllRides,
          }),
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload?.detail || `Erreur HTTP ${response.status}`);
      }

      setComparisonResult(payload);
      if (payload.all_rides_diffs) {
        setAllRidesDiffs(payload.all_rides_diffs);
      } else {
        setAllRidesDiffs(null);
      }
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
                min="1"
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

          {/* Apply to All Rides Option */}
          {selectedCyclist && (
            <div>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={applyToAllRides}
                  onChange={handleApplyToAllRidesChange}
                  className="w-4 h-4"
                />
                <span className={commonPipelineStyles.formLabel}>
                  Appliquer les modèles à toutes les sorties et calculer les
                  diffs moyennes
                </span>
              </label>
              <p className={commonPipelineStyles.mutedText}>
                Cela calculera la différence moyenne de BPM pour chaque sortie
                du cycliste
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
        <div className={commonPipelineStyles.card}>
          <h3 className={commonPipelineStyles.subSectionTitle}>
            Apercu de la sortie d&apos;entrainement
          </h3>
          <div className="mt-3 mb-4 flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm text-[#dbeafe]/90">
              <input
                type="radio"
                name="preview-model"
                value="A"
                checked={previewModel === "A"}
                onChange={() => setPreviewModel("A")}
                className="h-4 w-4"
              />
              Modele A (sortie {selectedTrainRide1})
            </label>
            <label className="flex items-center gap-2 text-sm text-[#dbeafe]/90">
              <input
                type="radio"
                name="preview-model"
                value="B"
                checked={previewModel === "B"}
                onChange={() => setPreviewModel("B")}
                className="h-4 w-4"
              />
              Modele B (sortie {selectedTrainRide2})
            </label>
          </div>

          <TrainingRidePreview
            cyclist={selectedCyclist}
            rideIndex={
              previewModel === "A" ? selectedTrainRide1 : selectedTrainRide2
            }
            modelLabel={previewModel}
          />
        </div>
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
              <div className="rounded-lg border border-[#003566] bg-[#000814]/55 p-4">
                <p className="mb-2 text-sm font-semibold text-[#fff8d6]">
                  RMSE
                </p>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-xs text-[#dbeafe]/80">
                      Sortie {selectedTrainRide1} (Mod A)
                    </span>
                    <span className="text-sm font-mono font-bold text-[#ffc300]">
                      {comparisonResult.metrics.rmse_model1.toFixed(3)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-[#dbeafe]/80">
                      Sortie {selectedTrainRide2} (Mod B)
                    </span>
                    <span className="text-sm font-mono font-bold text-[#ffd60a]">
                      {comparisonResult.metrics.rmse_model2.toFixed(3)}
                    </span>
                  </div>
                  <div className="mt-2 border-t border-[#003566] pt-2">
                    <span className="text-xs text-[#9fb4d2]">
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
              <div className="rounded-lg border border-[#003566] bg-[#000814]/55 p-4">
                <p className="mb-2 text-sm font-semibold text-[#fff8d6]">
                  FC min (bpm)
                </p>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-xs text-[#dbeafe]/80">
                      Sortie {selectedTrainRide1} (Mod A)
                    </span>
                    <span className="text-sm font-mono font-bold text-[#ffc300]">
                      {(() => {
                        const extrema = getFiniteExtrema(
                          comparisonResult.model1_predictions,
                        );
                        return extrema.min !== null
                          ? extrema.min.toFixed(1)
                          : "-";
                      })()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-[#dbeafe]/80">
                      Sortie {selectedTrainRide2} (Mod B)
                    </span>
                    <span className="text-sm font-mono font-bold text-[#ffd60a]">
                      {(() => {
                        const extrema = getFiniteExtrema(
                          comparisonResult.model2_predictions,
                        );
                        return extrema.min !== null
                          ? extrema.min.toFixed(1)
                          : "-";
                      })()}
                    </span>
                  </div>
                  <div className="mt-2 border-t border-[#003566] pt-2">
                    <span className="text-xs text-[#9fb4d2]">
                      Diff:{" "}
                      {(() => {
                        const modelA = getFiniteExtrema(
                          comparisonResult.model1_predictions,
                        );
                        const modelB = getFiniteExtrema(
                          comparisonResult.model2_predictions,
                        );
                        if (modelA.min === null || modelB.min === null) {
                          return "-";
                        }
                        return (modelA.min - modelB.min).toFixed(1);
                      })()}
                    </span>
                  </div>
                </div>
              </div>

              {/* R² Comparison */}
              <div className="rounded-lg border border-[#003566] bg-[#000814]/55 p-4">
                <p className="mb-2 text-sm font-semibold text-[#fff8d6]">
                  FC max (bpm)
                </p>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-xs text-[#dbeafe]/80">
                      Sortie {selectedTrainRide1} (Mod A)
                    </span>
                    <span className="text-sm font-mono font-bold text-[#ffc300]">
                      {(() => {
                        const extrema = getFiniteExtrema(
                          comparisonResult.model1_predictions,
                        );
                        return extrema.max !== null
                          ? extrema.max.toFixed(1)
                          : "-";
                      })()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-[#dbeafe]/80">
                      Sortie {selectedTrainRide2} (Mod B)
                    </span>
                    <span className="text-sm font-mono font-bold text-[#ffd60a]">
                      {(() => {
                        const extrema = getFiniteExtrema(
                          comparisonResult.model2_predictions,
                        );
                        return extrema.max !== null
                          ? extrema.max.toFixed(1)
                          : "-";
                      })()}
                    </span>
                  </div>
                  <div className="mt-2 border-t border-[#003566] pt-2">
                    <span className="text-xs text-[#9fb4d2]">
                      Diff:{" "}
                      {(() => {
                        const modelA = getFiniteExtrema(
                          comparisonResult.model1_predictions,
                        );
                        const modelB = getFiniteExtrema(
                          comparisonResult.model2_predictions,
                        );
                        if (modelA.max === null || modelB.max === null) {
                          return "-";
                        }
                        return (modelA.max - modelB.max).toFixed(1);
                      })()}
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
                      ? "bg-[#ffc300] text-[#000814]"
                      : "bg-[#003566] text-[#fff8d6] hover:bg-[#00467f]"
                  }`}
                >
                  Tous les deux
                </button>
                <button
                  type="button"
                  onClick={() => setModelDisplay("A")}
                  className={`px-3 py-1.5 text-sm font-semibold rounded transition-colors ${
                    modelDisplay === "A"
                      ? "bg-[#ffc300] text-[#000814]"
                      : "bg-[#003566] text-[#fff8d6] hover:bg-[#00467f]"
                  }`}
                >
                  Modèle A
                </button>
                <button
                  type="button"
                  onClick={() => setModelDisplay("B")}
                  className={`px-3 py-1.5 text-sm font-semibold rounded transition-colors ${
                    modelDisplay === "B"
                      ? "bg-[#ffc300] text-[#000814]"
                      : "bg-[#003566] text-[#fff8d6] hover:bg-[#00467f]"
                  }`}
                >
                  Modèle B
                </button>
              </div>
            </div>

            {chartRideData && (
              <PredictionChart rideData={chartRideData} models={chartModels} />
            )}

            <InterpretationGuide context="compare" />
          </div>

          {comparisonResult && (
            <BpmDiffVisualizer
              sectionTitle={`Différence de BPM entre les modèles (Sortie de test #${selectedTestRide})`}
              pointChartTitle="Différence point par point (Modèle A - Modèle B)"
              pointSeries={pointDiffSeries}
              pointXAxisLabel="Temps (min)"
              summaryChartTitle={
                applyToAllRides && summaryDiffRows.length > 0
                  ? "Différences moyennes de BPM par sortie"
                  : undefined
              }
              summarySubtitle={
                applyToAllRides && summaryDiffRows.length > 0
                  ? "Moyenne des différences : (Modèle A - Modèle B) / nombre de points"
                  : undefined
              }
              summaryRows={
                applyToAllRides && summaryDiffRows.length > 0
                  ? summaryDiffRows
                  : undefined
              }
            />
          )}
        </div>
      )}
    </div>
  );
}
