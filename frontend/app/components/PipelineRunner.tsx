"use client";

import { useEffect, useMemo, useState } from "react";
import BpmDiffVisualizer from "./BpmDiffVisualizer";
import CyclistSelector from "./CyclistSelector";
import PredictionChart from "./PredictionChart";
import RideSelector from "./RideSelector";
import TrainingRidePreview from "./TrainingRidePreview";
import { commonPipelineStyles, predictionPageStyles } from "./pipelineStyles";

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

interface AuthUser {
  id: string;
  email: string;
  display_name?: string | null;
  role: string;
}

interface RideData {
  datetime: string;
  n_points: number;
  columns: string[];
  data: Record<string, unknown>[];
}

interface PipelineResponse {
  ok: boolean;
  n_rides: number;
  models_requested: string[];
  models_computed: string[];
  rides: RideData[];
}

export default function PipelineRunner() {
  const apiUrl = useMemo(() => process.env.NEXT_PUBLIC_API_URL || "", []);

  const [selectedCyclist, setSelectedCyclist] = useState("");
  const [selectedModels, setSelectedModels] = useState<string[]>([
    "pred_arx_selected",
  ]);
  const [selectedTrainRide, setSelectedTrainRide] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResponse | null>(null);
  const [selectedRideIndex, setSelectedRideIndex] = useState(0);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [maxTrainRideIndex, setMaxTrainRideIndex] = useState(1);
  const [selectedDiffModel, setSelectedDiffModel] = useState<string>("");

  useEffect(() => {
    const fetchMe = async () => {
      try {
        const response = await fetch(`${apiUrl}/auth/me`, {
          credentials: "include",
        });
        if (!response.ok) {
          setAuthToken(null);
          setAuthUser(null);
          return;
        }
        const payload = await response.json();
        setAuthUser(payload.user as AuthUser);
        setAuthToken("cookie-session");
      } catch {
        setAuthToken(null);
        setAuthUser(null);
      }
    };

    fetchMe();
  }, [apiUrl]);

  const handleRun = async () => {
    if (!authToken) {
      setError("Connecte-toi pour executer le pipeline.");
      return;
    }
    if (!selectedCyclist) {
      setError("Selectionne un cycliste avant d'executer le pipeline.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const dirPath = `../DB/rides/${selectedCyclist}`;

      const response = await fetch(`${apiUrl}/pipeline/run`, {
        method: "POST",
        credentials: "include",
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
  const isAdmin = authUser?.role === "admin";
  const showCyclistSelection = Boolean(authToken) && isAdmin;
  const trainingSectionIndex = showCyclistSelection ? 2 : 1;
  const configSectionIndex = showCyclistSelection ? 3 : 2;

  const modelDiffVisualizations = useMemo(() => {
    if (!result || !currentRide) {
      return [] as Array<{
        modelKey: string;
        pointSeries: Array<{ x: number; diff: number }>;
        summaryRows: Array<{
          rideIndex: number;
          datetime: string;
          nPoints: number;
          meanDiff: number;
        }>;
      }>;
    }

    return result.models_computed
      .map((modelKey) => {
        const pointSeries = currentRide.data
          .map((point) => {
            const tMin = toNumberOrNull(point.t_min);
            const actual = toNumberOrNull(point.hr);
            const predicted = toNumberOrNull(point[modelKey]);
            if (tMin === null || actual === null || predicted === null) {
              return null;
            }
            return { x: tMin, diff: predicted - actual };
          })
          .filter((item): item is { x: number; diff: number } => item !== null);

        const summaryRows = result.rides
          .map((ride, idx) => {
            const diffs = ride.data
              .map((point) => {
                const actual = toNumberOrNull(point.hr);
                const predicted = toNumberOrNull(point[modelKey]);
                if (actual === null || predicted === null) {
                  return null;
                }
                return predicted - actual;
              })
              .filter((value): value is number => value !== null);

            if (diffs.length === 0) {
              return null;
            }

            const meanDiff =
              diffs.reduce((sum, value) => sum + value, 0) / diffs.length;

            return {
              rideIndex: idx + 1,
              datetime: ride.datetime,
              nPoints: ride.n_points,
              meanDiff,
            };
          })
          .filter(
            (
              item,
            ): item is {
              rideIndex: number;
              datetime: string;
              nPoints: number;
              meanDiff: number;
            } => item !== null,
          );

        return {
          modelKey,
          pointSeries,
          summaryRows,
        };
      })
      .filter(
        (modelViz) =>
          modelViz.pointSeries.length > 0 || modelViz.summaryRows.length > 0,
      );
  }, [currentRide, result]);

  useEffect(() => {
    if (modelDiffVisualizations.length === 0) {
      setSelectedDiffModel("");
      return;
    }

    if (
      !selectedDiffModel ||
      !modelDiffVisualizations.some(
        (modelViz) => modelViz.modelKey === selectedDiffModel,
      )
    ) {
      setSelectedDiffModel(modelDiffVisualizations[0].modelKey);
    }
  }, [modelDiffVisualizations, selectedDiffModel]);

  const selectedModelDiffVisualization = useMemo(
    () =>
      modelDiffVisualizations.find(
        (modelViz) => modelViz.modelKey === selectedDiffModel,
      ) ?? modelDiffVisualizations[0],
    [modelDiffVisualizations, selectedDiffModel],
  );

  const handleTrainRideChange = (value: string) => {
    const parsed = Number.parseInt(value, 10);
    if (Number.isNaN(parsed)) {
      return;
    }
    const clamped = Math.min(Math.max(parsed, 1), maxTrainRideIndex);
    setSelectedTrainRide(clamped);
  };

  useEffect(() => {
    if (selectedTrainRide < 1) {
      setSelectedTrainRide(1);
      return;
    }
    if (selectedTrainRide > maxTrainRideIndex) {
      setSelectedTrainRide(maxTrainRideIndex);
    }
  }, [maxTrainRideIndex, selectedTrainRide]);

  return (
    <div className={commonPipelineStyles.pageContainer}>
      <div>
        <h1 className={commonPipelineStyles.pageTitle}>
          Pipeline de Prédictions HR
        </h1>
        <p className={commonPipelineStyles.pageSubtitle}>
          Configurez le modèle d&apos;entrainement puis lancez l&apos;analyse
          prédictive
        </p>
      </div>

      {showCyclistSelection && (
        <div className={commonPipelineStyles.card}>
          <h2 className={commonPipelineStyles.sectionTitle}>
            1. Sélectionner le cycliste
          </h2>
          <CyclistSelector
            selectedCyclist={selectedCyclist}
            onSelectCyclist={setSelectedCyclist}
            isAdmin
            onMaxRideIndexChange={setMaxTrainRideIndex}
          />
        </div>
      )}

      <div className={commonPipelineStyles.card}>
        <h2 className={commonPipelineStyles.sectionTitle}>
          {trainingSectionIndex}. Ride d&apos;entraînement
        </h2>
        {!showCyclistSelection && (
          <div className={commonPipelineStyles.marginBottom4}>
            <CyclistSelector
              selectedCyclist={selectedCyclist}
              onSelectCyclist={setSelectedCyclist}
              isAdmin={false}
              onMaxRideIndexChange={setMaxTrainRideIndex}
            />
          </div>
        )}
        <div className={commonPipelineStyles.marginBottom4}>
          <label
            htmlFor="training-ride-index"
            className={commonPipelineStyles.formLabel}
          >
            Ride d&apos;entraînement (index, 1-based)
          </label>
          <input
            id="training-ride-index"
            type="number"
            min="1"
            max={maxTrainRideIndex}
            value={selectedTrainRide}
            onChange={(e) => handleTrainRideChange(e.target.value)}
            className={`${commonPipelineStyles.emphasizedInput} ${predictionPageStyles.trainRideInput}`}
          />
          <p className={`${commonPipelineStyles.mutedText} mt-1`}>
            Cette ride sera utilisée comme modèle pour les prédictions (1 a{" "}
            {maxTrainRideIndex})
          </p>
        </div>
        <TrainingRidePreview
          cyclist={selectedCyclist}
          rideIndex={selectedTrainRide}
        />
      </div>

      <div className={`${commonPipelineStyles.card} space-y-4`}>
        <h2 className={commonPipelineStyles.sectionTitle}>
          {configSectionIndex}. Configuration et exécution
        </h2>

        <div>
          <p className={predictionPageStyles.modelLabel}>Modèles à calculer</p>
          <div className={predictionPageStyles.modelGrid}>
            {availableModels.map((model) => (
              <label
                key={model.id}
                className={predictionPageStyles.modelOption}
              >
                <input
                  type="checkbox"
                  checked={selectedModels.includes(model.id)}
                  onChange={() => toggleModel(model.id)}
                  className={predictionPageStyles.modelCheckbox}
                />
                <span className={predictionPageStyles.modelOptionText}>
                  {model.label}
                </span>
              </label>
            ))}
          </div>
        </div>

        <button
          type="button"
          onClick={handleRun}
          disabled={loading || selectedModels.length === 0}
          className={predictionPageStyles.runButton}
        >
          {loading ? "Exécution en cours..." : "Exécuter le pipeline"}
        </button>

        {error && (
          <div className={predictionPageStyles.errorPanel}>
            <p className={predictionPageStyles.errorPanelTitle}>Erreur:</p>
            <p className={predictionPageStyles.errorPanelBody}>{error}</p>
          </div>
        )}
      </div>

      {result && (
        <div className={commonPipelineStyles.sectionStack}>
          <div className={commonPipelineStyles.card}>
            <h2 className={commonPipelineStyles.sectionTitle}>
              Résultats de l&apos;analyse
            </h2>
            <div className={predictionPageStyles.summaryGrid}>
              <div className={predictionPageStyles.summaryCard}>
                <p className={predictionPageStyles.summaryLabel}>
                  Nombre de rides
                </p>
                <p className={predictionPageStyles.summaryValue}>
                  {result.n_rides}
                </p>
              </div>
              <div className={predictionPageStyles.summaryCard}>
                <p className={predictionPageStyles.summaryLabel}>
                  Modèles calculés
                </p>
                <p className={predictionPageStyles.summaryValueMono}>
                  {result.models_computed.join(", ")}
                </p>
              </div>
              <div className={predictionPageStyles.summaryCard}>
                <p className={predictionPageStyles.summaryLabel}>
                  Points par ride
                </p>
                <p className={predictionPageStyles.summaryValue}>
                  {currentRide?.n_points || "-"}
                </p>
              </div>
            </div>
          </div>

          <RideSelector
            rides={result.rides}
            selectedIndex={selectedRideIndex}
            onSelectRide={setSelectedRideIndex}
          />

          {currentRide && (
            <div className={commonPipelineStyles.sectionStack}>
              <PredictionChart
                rideData={currentRide}
                models={result.models_computed}
              />

              {selectedModelDiffVisualization && (
                <div className="space-y-3">
                  {modelDiffVisualizations.length > 1 && (
                    <div>
                      <label
                        htmlFor="diff-model-select"
                        className={commonPipelineStyles.formLabel}
                      >
                        Modèle affiché pour les différences BPM
                      </label>
                      <select
                        id="diff-model-select"
                        value={selectedDiffModel}
                        onChange={(e) => setSelectedDiffModel(e.target.value)}
                        className={`${commonPipelineStyles.textInput} md:w-72`}
                      >
                        {modelDiffVisualizations.map((modelViz) => {
                          const modelLabel =
                            availableModels.find(
                              (model) => model.id === modelViz.modelKey,
                            )?.label ?? modelViz.modelKey;

                          return (
                            <option
                              key={modelViz.modelKey}
                              value={modelViz.modelKey}
                            >
                              {modelLabel}
                            </option>
                          );
                        })}
                      </select>
                    </div>
                  )}

                  <BpmDiffVisualizer
                    key={selectedModelDiffVisualization.modelKey}
                    sectionTitle={`${configSectionIndex + 1}. Différences BPM (prédiction vs réel)`}
                    sectionSubtitle={`Modèle analysé: ${selectedModelDiffVisualization.modelKey}. Différence calculée par point: prédiction - fréquence cardiaque réelle.`}
                    pointChartTitle={`Ride ${selectedRideIndex + 1} - Différence point par point (${selectedModelDiffVisualization.modelKey})`}
                    pointSeries={selectedModelDiffVisualization.pointSeries}
                    pointXAxisLabel="Temps (min)"
                    summaryChartTitle={`Graphe résumé des différences moyennes par ride (${selectedModelDiffVisualization.modelKey})`}
                    summaryRows={selectedModelDiffVisualization.summaryRows}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
