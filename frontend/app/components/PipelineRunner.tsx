"use client";

import { useEffect, useMemo, useState } from "react";
import CyclistSelector from "./CyclistSelector";
import PredictionChart from "./PredictionChart";
import RideSelector from "./RideSelector";
import TrainingRidePreview from "./TrainingRidePreview";
import { commonPipelineStyles, predictionPageStyles } from "./pipelineStyles";

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
  const [email, setEmail] = useState("shapunaifu_athlete@strava.local");
  const [password, setPassword] = useState("");
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [loadingLogin, setLoadingLogin] = useState(false);
  const [maxTrainRideIndex, setMaxTrainRideIndex] = useState(1);

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

  const handleLogin = async () => {
    setLoadingLogin(true);
    setAuthError(null);
    try {
      const response = await fetch(`${apiUrl}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }

      setAuthToken("cookie-session");
      setAuthUser(payload.user as AuthUser);
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoadingLogin(false);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch(`${apiUrl}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      setAuthToken(null);
      setAuthUser(null);
      setResult(null);
      setError(null);
    }
  };

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
      {/* Header */}
      <div>
        <h1 className={commonPipelineStyles.pageTitle}>
          Pipeline de Prédictions HR
        </h1>
        <p className={commonPipelineStyles.pageSubtitle}>
          Configurez le modèle d&apos;entrainement puis lancez l&apos;analyse
          prédictive
        </p>
      </div>

      <div className={`${commonPipelineStyles.card} space-y-4`}>
        <h2 className={commonPipelineStyles.sectionTitleNoMargin}>
          Authentification
        </h2>
        <p className={commonPipelineStyles.bodyText}>
          Connecte-toi pour charger et analyser tes rides (routes protegees par
          JWT).
        </p>

        {!authToken ? (
          <div className={predictionPageStyles.authGrid}>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className={commonPipelineStyles.textInput}
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mot de passe"
              className={commonPipelineStyles.textInput}
            />
            <button
              type="button"
              onClick={handleLogin}
              disabled={loadingLogin}
              className={commonPipelineStyles.buttonDark}
            >
              {loadingLogin ? "Connexion..." : "Se connecter"}
            </button>
          </div>
        ) : (
          <div className={commonPipelineStyles.authSuccessBanner}>
            <p>
              Connecte en tant que{" "}
              {authUser?.display_name || authUser?.email || email}
            </p>
            <button
              type="button"
              onClick={handleLogout}
              className={commonPipelineStyles.buttonDarkCompact}
            >
              Se deconnecter
            </button>
          </div>
        )}

        {authError && (
          <p className={commonPipelineStyles.errorText}>Erreur: {authError}</p>
        )}
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

      {/* Section 2: Training Ride Preview */}
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

      {/* Section 3: Model Configuration & Run */}
      <div className={`${commonPipelineStyles.card} space-y-4`}>
        <h2 className={commonPipelineStyles.sectionTitle}>
          {configSectionIndex}. Configuration et exécution
        </h2>

        {/* Model Selection */}
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

        {/* Run Button */}
        <button
          type="button"
          onClick={handleRun}
          disabled={loading || selectedModels.length === 0}
          className={predictionPageStyles.runButton}
        >
          {loading ? "Exécution en cours..." : "Exécuter le pipeline"}
        </button>

        {/* Error Message */}
        {error && (
          <div className={predictionPageStyles.errorPanel}>
            <p className={predictionPageStyles.errorPanelTitle}>Erreur:</p>
            <p className={predictionPageStyles.errorPanelBody}>{error}</p>
          </div>
        )}
      </div>

      {/* Results Panel */}
      {result && (
        <div className={commonPipelineStyles.sectionStack}>
          {/* Results Summary */}
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

          {/* Ride Selector */}
          <RideSelector
            rides={result.rides}
            selectedIndex={selectedRideIndex}
            onSelectRide={setSelectedRideIndex}
          />

          {/* Charts and Data */}
          {currentRide && (
            <div className={commonPipelineStyles.sectionStack}>
              {/* Prediction Chart */}
              <PredictionChart
                rideData={currentRide}
                models={result.models_computed}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
