"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
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
        <TrainingRidePreview
          cyclist={selectedCyclist}
          rideIndex={selectedTrainRide1}
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

          {/* Diff Chart */}
          {comparisonResult && (
            <div className={commonPipelineStyles.card}>
              <h2 className={commonPipelineStyles.sectionTitle}>
                Différence de BPM entre les modèles (Sortie de test #
                {selectedTestRide})
              </h2>
              <div className="bg-white rounded-lg shadow p-6">
                <svg width={800} height={300} className="bg-white">
                  <title>Diff BPM: Model A - Model B</title>
                  <defs>
                    <clipPath id="diff-clip">
                      <rect x={60} y={30} width={740} height={240} />
                    </clipPath>
                  </defs>

                  {/* Grid */}
                  {[0, 0.25, 0.5, 0.75, 1].map((t) => (
                    <line
                      key={`diff-vgrid-${t}`}
                      x1={60 + t * 740}
                      y1={30}
                      x2={60 + t * 740}
                      y2={270}
                      stroke="#e5e7eb"
                      strokeWidth="1"
                    />
                  ))}
                  {[0, 0.25, 0.5, 0.75, 1].map((t) => (
                    <line
                      key={`diff-hgrid-${t}`}
                      x1={60}
                      y1={30 + (1 - t) * 240}
                      x2={800}
                      y2={30 + (1 - t) * 240}
                      stroke="#e5e7eb"
                      strokeWidth="1"
                    />
                  ))}

                  {/* Axes */}
                  <line
                    x1={60}
                    y1={30}
                    x2={60}
                    y2={270}
                    stroke="#000"
                    strokeWidth="2"
                  />
                  <line
                    x1={60}
                    y1={270}
                    x2={800}
                    y2={270}
                    stroke="#000"
                    strokeWidth="2"
                  />

                  {/* Diff line */}
                  {(() => {
                    const diffs = comparisonResult.model1_predictions.map(
                      (m1, idx) =>
                        m1 - (comparisonResult.model2_predictions[idx] || 0),
                    );
                    const finiteDiffs = diffs.filter(Number.isFinite);
                    if (finiteDiffs.length === 0) {
                      return null;
                    }

                    const minDiff = Math.min(...finiteDiffs);
                    const maxDiff = Math.max(...finiteDiffs);
                    const pad = Math.max(1, (maxDiff - minDiff) * 0.1);
                    const yMin = minDiff - pad;
                    const yMax = maxDiff + pad;
                    const yRange = Math.max(1e-9, yMax - yMin);

                    const scaleY = (value: number) =>
                      270 - ((value - yMin) / yRange) * 240;

                    let path = "";
                    for (let i = 0; i < diffs.length; i++) {
                      const x = 60 + (i / Math.max(1, diffs.length - 1)) * 740;
                      const y = scaleY(diffs[i]);
                      if (i === 0) {
                        path += `M ${x} ${y}`;
                      } else {
                        path += ` L ${x} ${y}`;
                      }
                    }

                    const yTicks = [0, 0.25, 0.5, 0.75, 1].map((t) => {
                      const value = yMin + t * (yMax - yMin);
                      const y = scaleY(value);
                      return { value, y };
                    });

                    const zeroInRange = yMin <= 0 && yMax >= 0;
                    const zeroY = zeroInRange ? scaleY(0) : null;

                    return (
                      <>
                        {yTicks.map((tick) => (
                          <text
                            key={`diff-y-tick-${tick.value.toFixed(2)}`}
                            x={50}
                            y={tick.y + 4}
                            textAnchor="end"
                            className="text-xs text-gray-600"
                          >
                            {tick.value.toFixed(1)}
                          </text>
                        ))}

                        <path
                          d={path}
                          fill="none"
                          stroke="#8b5cf6"
                          strokeWidth="2"
                          clipPath="url(#diff-clip)"
                        />
                        {zeroY !== null && (
                          <line
                            x1={60}
                            y1={zeroY}
                            x2={800}
                            y2={zeroY}
                            stroke="#ccc"
                            strokeWidth="1"
                            strokeDasharray="5,5"
                          />
                        )}
                      </>
                    );
                  })()}

                  {/* Axis labels */}
                  <text x={400} y={290} textAnchor="middle" className="text-xs">
                    Points
                  </text>
                  <text x={15} y={150} textAnchor="middle" className="text-xs">
                    BPM
                  </text>
                </svg>
              </div>
            </div>
          )}

          {/* All Rides Diffs Chart */}
          {applyToAllRides &&
            allRidesDiffs &&
            Array.isArray(allRidesDiffs) &&
            allRidesDiffs.length > 0 && (
              <div className={commonPipelineStyles.card}>
                <h2 className={commonPipelineStyles.sectionTitle}>
                  Différences moyennes de BPM par sortie
                </h2>
                <p className={commonPipelineStyles.bodyText}>
                  Moyenne des différences : (Modèle A - Modèle B) / nombre de
                  points
                </p>
                <div className="bg-white rounded-lg shadow p-6">
                  <svg width={900} height={400} className="bg-white">
                    <title>Diff BPM moyennes par sortie</title>
                    {(() => {
                      const rides = allRidesDiffs;
                      const diffs = rides.map((r) => r.mean_bpm_diff);
                      const minDiff = Math.min(...diffs);
                      const maxDiff = Math.max(...diffs);
                      const pad = Math.max(1, (maxDiff - minDiff) * 0.15 || 1);
                      const yMin = minDiff - pad;
                      const yMax = maxDiff + pad;
                      const yRange = Math.max(1e-9, yMax - yMin);
                      const xMin = Math.min(...rides.map((r) => r.ride_index));
                      const xMax = Math.max(...rides.map((r) => r.ride_index));
                      const xRange = Math.max(1, xMax - xMin);

                      const scaleX = (rideIndex: number) =>
                        75 + ((rideIndex - xMin) / xRange) * 750;
                      const scaleY = (value: number) =>
                        350 - ((value - yMin) / yRange) * 300;

                      const sortedRides = [...rides].sort(
                        (a, b) => a.ride_index - b.ride_index,
                      );

                      const linePath = sortedRides
                        .map((ride, idx) => {
                          const x = scaleX(ride.ride_index);
                          const y = scaleY(ride.mean_bpm_diff);
                          return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
                        })
                        .join(" ");

                      const yTicks = [0, 0.25, 0.5, 0.75, 1].map((t) => {
                        const value = yMin + t * (yMax - yMin);
                        return { value, y: scaleY(value) };
                      });

                      const xTicks = sortedRides.map((ride) => ({
                        value: ride.ride_index,
                        x: scaleX(ride.ride_index),
                      }));

                      return (
                        <>
                          {/* Grid and axes */}
                          {yTicks.map((tick) => (
                            <line
                              key={`all-hgrid-${tick.value.toFixed(2)}`}
                              x1={75}
                              y1={tick.y}
                              x2={825}
                              y2={tick.y}
                              stroke="#e5e7eb"
                              strokeWidth="1"
                            />
                          ))}

                          <line
                            x1={75}
                            y1={50}
                            x2={75}
                            y2={350}
                            stroke="#000"
                            strokeWidth="2"
                          />
                          <line
                            x1={75}
                            y1={350}
                            x2={825}
                            y2={350}
                            stroke="#000"
                            strokeWidth="2"
                          />

                          {/* Y tick labels */}
                          {yTicks.map((tick) => (
                            <text
                              key={`all-y-label-${tick.value.toFixed(2)}`}
                              x={65}
                              y={tick.y + 4}
                              textAnchor="end"
                              className="text-xs text-gray-600"
                            >
                              {tick.value.toFixed(1)}
                            </text>
                          ))}

                          {/* Connected line */}
                          <path
                            d={linePath}
                            fill="none"
                            stroke="#2563eb"
                            strokeWidth="2.5"
                          />

                          {/* Points + value labels */}
                          {sortedRides.map((ride) => {
                            const x = scaleX(ride.ride_index);
                            const y = scaleY(ride.mean_bpm_diff);
                            return (
                              <g key={`point-${ride.ride_index}`}>
                                <circle cx={x} cy={y} r={4} fill="#1d4ed8" />
                                <text
                                  x={x + 6}
                                  y={y - 6}
                                  className="text-xs font-semibold fill-blue-700"
                                >
                                  {ride.mean_bpm_diff.toFixed(2)}
                                </text>
                              </g>
                            );
                          })}

                          {/* X tick labels */}
                          {xTicks.map((tick) => (
                            <text
                              key={`all-x-label-${tick.value}`}
                              x={tick.x}
                              y={366}
                              textAnchor="middle"
                              className="text-xs text-gray-600"
                            >
                              {tick.value}
                            </text>
                          ))}

                          {/* Labels */}
                          <text
                            x={450}
                            y={380}
                            textAnchor="middle"
                            className="text-xs font-semibold"
                          >
                            Numéro de sortie
                          </text>
                          <text
                            x={20}
                            y={200}
                            textAnchor="middle"
                            transform="rotate(-90 20 200)"
                            className="text-xs font-semibold"
                          >
                            Valeur BPM
                          </text>
                        </>
                      );
                    })()}
                  </svg>
                </div>

                {/* Rides Differences Table */}
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
                      {(
                        allRidesDiffs as Array<{
                          ride_index: number;
                          datetime: string;
                          n_points: number;
                          mean_bpm_diff: number;
                        }>
                      ).map((ride) => (
                        <tr
                          key={`ride-${ride.ride_index}`}
                          className={predictionPageStyles.tableRow}
                        >
                          <td className={predictionPageStyles.tableCell}>
                            {ride.ride_index}
                          </td>
                          <td className={predictionPageStyles.tableCell}>
                            {ride.datetime}
                          </td>
                          <td className={predictionPageStyles.tableCell}>
                            {ride.n_points}
                          </td>
                          <td
                            className={predictionPageStyles.tableCell}
                            style={{
                              color:
                                ride.mean_bpm_diff >= 0 ? "#3b82f6" : "#ef4444",
                              fontWeight: "bold",
                            }}
                          >
                            {ride.mean_bpm_diff.toFixed(2)} BPM
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

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
