"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  commonPipelineStyles,
  stravaPageStyles,
} from "../components/pipelineStyles";

type StravaStatus = {
  configured: boolean;
  has_client_id: boolean;
  has_client_secret: boolean;
  has_redirect_uri: boolean;
  redirect_uri: string;
  scopes: string;
  connected?: boolean;
  athlete_id?: number | null;
  expires_at?: string | null;
};

type ExchangeResult = {
  saved: boolean;
  storage?: string;
  token_type: string;
  expires_at: number | null;
  athlete_id: number | null;
};

type AuthUser = {
  id: string;
  email: string;
  display_name?: string | null;
  role: string;
};

type StravaActivity = {
  id: number;
  name: string;
  sport_type: string;
  distance: number | null;
  moving_time: number | null;
  elapsed_time: number | null;
  start_date: string | null;
  average_speed: number | null;
  average_heartrate: number | null;
  average_watts: number | null;
};

export default function StravaPipelinePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const apiUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_URL || "https://tfe-cycling.onrender.com",
    [],
  );
  const autoExchangeDoneRef = useRef(false);

  const [status, setStatus] = useState<StravaStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [oauthAuthError, setOauthAuthError] = useState<string | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(false);
  const [oauthCode, setOauthCode] = useState("");
  const [exchangeError, setExchangeError] = useState<string | null>(null);
  const [exchangeResult, setExchangeResult] = useState<ExchangeResult | null>(
    null,
  );
  const [loadingExchange, setLoadingExchange] = useState(false);
  const [activities, setActivities] = useState<StravaActivity[]>([]);
  const [activitiesError, setActivitiesError] = useState<string | null>(null);
  const [activitiesSavedInfo, setActivitiesSavedInfo] = useState<string | null>(
    null,
  );
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [selectedActivityLimit, setSelectedActivityLimit] = useState(10);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  const authHeaders = useMemo(() => {
    if (!authToken) {
      return {} as Record<string, string>;
    }
    return { Authorization: `Bearer ${authToken}` };
  }, [authToken]);

  const extractOAuthCode = (value: string): string => {
    const clean = (value || "").trim().replace(/^['\"]|['\"]$/g, "");
    if (!clean) {
      return "";
    }

    const codeFromQuery = (query: string): string => {
      const params = new URLSearchParams(query);
      return (params.get("code") || "").trim();
    };

    if (clean.startsWith("http://") || clean.startsWith("https://")) {
      try {
        const url = new URL(clean);
        return (
          codeFromQuery(url.search.slice(1)) || codeFromQuery(url.hash.slice(1))
        );
      } catch {
        return "";
      }
    }

    if (clean.startsWith("?")) {
      return codeFromQuery(clean.slice(1));
    }

    if (clean.includes("code=") && clean.includes("=")) {
      return codeFromQuery(clean.replace(/^#/, ""));
    }

    return clean;
  };

  useEffect(() => {
    const stored = localStorage.getItem("tfe_access_token");
    if (!stored) {
      router.replace("/login?next=/strava");
      return;
    }
    setAuthToken(stored);
    setAuthChecked(true);
  }, [router]);

  useEffect(() => {
    const fetchMe = async () => {
      if (!authToken) {
        return;
      }
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
        localStorage.removeItem("tfe_access_token");
        setAuthToken(null);
        setAuthUser(null);
        router.replace("/login?next=/strava");
      }
    };

    fetchMe();
  }, [apiUrl, authHeaders, authToken, router]);

  useEffect(() => {
    const loadStatus = async () => {
      if (!authToken) {
        setStatus(null);
        return;
      }
      setLoadingStatus(true);
      setStatusError(null);
      try {
        const response = await fetch(`${apiUrl}/strava/status`, {
          headers: authHeaders,
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || `HTTP ${response.status}`);
        }
        setStatus(payload.status as StravaStatus);
      } catch (err) {
        setStatusError(err instanceof Error ? err.message : "Erreur inconnue");
      } finally {
        setLoadingStatus(false);
      }
    };

    loadStatus();
  }, [apiUrl, authHeaders, authToken]);

  const handleLogout = () => {
    localStorage.removeItem("tfe_access_token");
    setAuthToken(null);
    setAuthUser(null);
    setStatus(null);
    setActivities([]);
    setExchangeResult(null);
    router.replace("/login?next=/strava");
  };

  const handleGenerateAuthUrl = async () => {
    setLoadingAuth(true);
    setOauthAuthError(null);
    setAuthUrl(null);
    try {
      const response = await fetch(`${apiUrl}/strava/auth-url`, {
        headers: authHeaders,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }
      setAuthUrl(payload.auth_url as string);
    } catch (err) {
      setOauthAuthError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoadingAuth(false);
    }
  };

  const handleExchangeCode = async () => {
    if (!authToken) {
      setExchangeError("Connecte-toi avant d'échanger le code OAuth.");
      return;
    }

    const code = extractOAuthCode(oauthCode);
    if (!code) {
      setExchangeError("Le code OAuth est requis.");
      setExchangeResult(null);
      return;
    }

    setLoadingExchange(true);
    setExchangeError(null);
    setExchangeResult(null);
    try {
      const response = await fetch(`${apiUrl}/strava/exchange-code`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify({ code }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }

      setExchangeResult(payload.result as ExchangeResult);
      setOauthCode("");

      const refreshedStatus = await fetch(`${apiUrl}/strava/status`, {
        headers: authHeaders,
      });
      const refreshedPayload = await refreshedStatus.json();
      if (refreshedStatus.ok) {
        setStatus(refreshedPayload.status as StravaStatus);
      }
    } catch (err) {
      setExchangeError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoadingExchange(false);
    }
  };

  useEffect(() => {
    const autoExchangeCode = async () => {
      if (!authToken || autoExchangeDoneRef.current) {
        return;
      }

      const codeFromUrl = (searchParams.get("code") || "").trim();
      if (!codeFromUrl) {
        return;
      }

      autoExchangeDoneRef.current = true;
      setLoadingExchange(true);
      setExchangeError(null);
      setExchangeResult(null);

      try {
        const response = await fetch(`${apiUrl}/strava/exchange-code`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...authHeaders,
          },
          body: JSON.stringify({ code: codeFromUrl }),
        });

        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || `HTTP ${response.status}`);
        }

        setExchangeResult(payload.result as ExchangeResult);

        const refreshedStatus = await fetch(`${apiUrl}/strava/status`, {
          headers: authHeaders,
        });
        const refreshedPayload = await refreshedStatus.json();
        if (refreshedStatus.ok) {
          setStatus(refreshedPayload.status as StravaStatus);
        }

        router.replace("/strava");
      } catch (err) {
        setExchangeError(
          err instanceof Error ? err.message : "Erreur inconnue",
        );
      } finally {
        setLoadingExchange(false);
      }
    };

    autoExchangeCode();
  }, [apiUrl, authHeaders, authToken, router, searchParams]);

  const handlePasteOAuthCode = async () => {
    try {
      const pasted = await navigator.clipboard.readText();
      const normalized = extractOAuthCode(pasted);
      if (!normalized) {
        setExchangeError("Aucun code OAuth detecte dans le presse-papiers.");
        return;
      }
      setOauthCode(normalized);
      setExchangeError(null);
    } catch {
      setExchangeError("Impossible de lire le presse-papiers.");
    }
  };

  const handleFetchActivities = async () => {
    if (!authToken) {
      setActivitiesError("Connecte-toi avant de charger les sorties.");
      return;
    }

    setLoadingActivities(true);
    setActivitiesError(null);
    setActivitiesSavedInfo(null);
    setActivities([]);
    try {
      const response = await fetch(
        `${apiUrl}/strava/activities?limit=${selectedActivityLimit}`,
        {
          headers: authHeaders,
        },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }
      setActivities((payload.activities || []) as StravaActivity[]);
      const writtenCount = Number(payload.written_count || 0);
      const createdCount = Number(payload.created_count || 0);
      const updatedCount = Number(payload.updated_count || 0);
      const failedCount = Number(payload.failed_count || 0);
      setActivitiesSavedInfo(
        `PKL ecrits: ${writtenCount} (${createdCount} nouveaux, ${updatedCount} mis a jour, ${failedCount} echec(s)).`,
      );
    } catch (err) {
      setActivitiesError(
        err instanceof Error ? err.message : "Erreur inconnue",
      );
    } finally {
      setLoadingActivities(false);
    }
  };

  const hasTokens = exchangeResult?.saved || status?.connected;

  if (!authChecked || !authToken) {
    return (
      <div className={commonPipelineStyles.pageContainer}>
        <section className={commonPipelineStyles.card}>
          <h2 className={commonPipelineStyles.sectionTitleNoMargin}>
            Verification de session...
          </h2>
          <p className={`mt-2 ${commonPipelineStyles.bodyText}`}>
            Redirection vers la page de connexion.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className={commonPipelineStyles.pageContainer}>
      <div>
        <h1 className={commonPipelineStyles.pageTitle}>
          Pipeline de connexion Strava
        </h1>
        <p className={commonPipelineStyles.pageSubtitle}>
          Configure les credentials, connecte le compte strava, synchronise les
          activites, puis lance le pipeline de prediction.
        </p>
        <div className={commonPipelineStyles.redirectButtonContainer}>
          <Link
            href="/pipeline"
            className={commonPipelineStyles.redirectButtonSecondary}
          >
            Retour au dashboard
          </Link>
        </div>
      </div>

      <div className={`${commonPipelineStyles.card} space-y-4`}>
        <h2 className={commonPipelineStyles.sectionTitleNoMargin}>
          Authentification
        </h2>
        <p className={`mt-2 ${commonPipelineStyles.bodyText}`}>
          Connecte-toi pour acceder a tes tokens et tes sorties Strava en base
          de donnees.
        </p>
        <div
          className={`${stravaPageStyles.authBanner} ${commonPipelineStyles.authSuccessBanner}`}
        >
          <p>
            Connecte en tant que {authUser?.display_name || authUser?.email}
          </p>
          <button
            type="button"
            onClick={handleLogout}
            className={commonPipelineStyles.buttonDarkCompact}
          >
            Se deconnecter
          </button>
        </div>
      </div>

      <div className={commonPipelineStyles.sectionStack}>
        <section className={`${commonPipelineStyles.card} space-y-4`}>
          <h2 className={commonPipelineStyles.sectionTitle}>
            1. Connexion OAuth
          </h2>
          <p className={`mt-2 ${commonPipelineStyles.bodyText}`}>
            Verifier la configuration puis obtenir l&apos;URL
            d&apos;autorisation Strava.
          </p>
          <div className={stravaPageStyles.statusPanel}>
            {loadingStatus && <p>Verification des variables en cours...</p>}
            {statusError && (
              <p className="text-red-700">Erreur: {statusError}</p>
            )}
            {status && (
              <div className="space-y-1">
                <p>Configuration: {status.configured ? "OK" : "Incomplet"}</p>
                <p>Client ID: {status.has_client_id ? "OK" : "Manquant"}</p>
                <p>
                  Client Secret: {status.has_client_secret ? "OK" : "Manquant"}
                </p>
              </div>
            )}
          </div>

          <div className={stravaPageStyles.oauthPanel}>
            <p className="mb-3">
              Genere l&apos;URL OAuth depuis les credentials backend.
            </p>
            <button
              type="button"
              onClick={handleGenerateAuthUrl}
              disabled={loadingAuth}
              className={stravaPageStyles.actionButton}
            >
              {loadingAuth ? "Generation..." : "Generer URL OAuth"}
            </button>
            {oauthAuthError && (
              <p className={stravaPageStyles.inlineError}>
                Erreur: {oauthAuthError}
              </p>
            )}
            {authUrl && (
              <div className="mt-2 space-y-2">
                <p className="break-all text-blue-950">{authUrl}</p>
                <a href={authUrl} className={stravaPageStyles.openLink}>
                  Ouvrir Strava
                </a>
                <p className="text-sm text-slate-700">
                  Apres autorisation, Strava te redirige automatiquement sur
                  cette page pour echanger le code.
                </p>
              </div>
            )}
          </div>
        </section>

        <section className={`${commonPipelineStyles.card} space-y-4`}>
          <h2 className={commonPipelineStyles.sectionTitle}>
            2. Echange de code
          </h2>
          <p className={`mt-2 ${commonPipelineStyles.bodyText}`}>
            Le code OAuth est recupere automatiquement depuis l&apos;URL de
            retour. Le champ ci-dessous reste disponible en secours si besoin.
          </p>
          <div className={stravaPageStyles.oauthPanel}>
            <input
              type="text"
              value={oauthCode}
              onChange={(e) => setOauthCode(e.target.value)}
              placeholder="Code OAuth ou URL complete de retour"
              className={stravaPageStyles.oauthInput}
            />
            <div className={stravaPageStyles.exchangeActions}>
              <button
                type="button"
                onClick={handleExchangeCode}
                disabled={loadingExchange}
                className={stravaPageStyles.exchangeButton}
              >
                {loadingExchange ? "Echange en cours..." : "Echanger le code"}
              </button>
              <button
                type="button"
                onClick={handlePasteOAuthCode}
                disabled={loadingExchange}
                className={stravaPageStyles.pasteButton}
              >
                Coller le code
              </button>
            </div>

            {exchangeError && (
              <p className={stravaPageStyles.inlineError}>
                Erreur: {exchangeError}
              </p>
            )}

            {exchangeResult && (
              <div className={stravaPageStyles.exchangeSuccess}>
                <p className="font-semibold">Tokens enregistres.</p>
                {exchangeResult.storage && (
                  <p>Stockage: {exchangeResult.storage}</p>
                )}
                <p>Type: {exchangeResult.token_type}</p>
                {exchangeResult.athlete_id !== null && (
                  <p>Athlete ID: {exchangeResult.athlete_id}</p>
                )}
                {exchangeResult.expires_at !== null && (
                  <p>Expires At: {exchangeResult.expires_at}</p>
                )}
              </div>
            )}
          </div>
        </section>

        <section className={`${commonPipelineStyles.card} space-y-4`}>
          <h2 className={commonPipelineStyles.sectionTitle}>
            3. Extraction + Sync
          </h2>
          <p className={`mt-2 ${commonPipelineStyles.bodyText}`}>
            Recupere les dernieres sorties velos de ton compte Strava, puis
            synchronise-les vers des fichiers PKL.
          </p>
          <div className={stravaPageStyles.extractionPanel}>
            {!hasTokens ? (
              <p className={stravaPageStyles.activationWarning}>
                Complete les etapes 1 et 2 pour activer l&apos;extraction.
              </p>
            ) : (
              <>
                <div className={stravaPageStyles.extractionControls}>
                  <div className={stravaPageStyles.extractionInputWrap}>
                    <label
                      htmlFor="activity-limit"
                      className={stravaPageStyles.extractionInputLabel}
                    >
                      Nombre de sorties a recuperer:
                    </label>
                    <input
                      id="activity-limit"
                      type="number"
                      min="1"
                      max="100"
                      value={selectedActivityLimit}
                      onChange={(e) =>
                        setSelectedActivityLimit(
                          Math.max(1, parseInt(e.target.value) || 10),
                        )
                      }
                      className={stravaPageStyles.extractionInput}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleFetchActivities}
                    disabled={loadingActivities}
                    className={stravaPageStyles.extractionButton}
                  >
                    {loadingActivities ? "Extraction..." : "Extraire sorties"}
                  </button>
                </div>

                {activitiesError && (
                  <p className={stravaPageStyles.inlineError}>
                    Erreur: {activitiesError}
                  </p>
                )}

                {activitiesSavedInfo && (
                  <p className="mt-2 text-sm text-emerald-900">
                    {activitiesSavedInfo}
                  </p>
                )}

                {activities.length > 0 && (
                  <div className={stravaPageStyles.activityListPanel}>
                    <p className={stravaPageStyles.activityListTitle}>
                      {activities.length} sortie(s) trouvee(s):
                    </p>
                    <div className="space-y-2">
                      {activities.map((activity, idx) => {
                        const distanceKm = (activity.distance || 0) / 1000;
                        const movingMinutes = Math.round(
                          (activity.moving_time || 0) / 60,
                        );
                        return (
                          <div
                            key={activity.id || idx}
                            className={stravaPageStyles.activityCard}
                          >
                            <p className="font-semibold">{activity.name}</p>
                            <div className={stravaPageStyles.activityMeta}>
                              <p>
                                {distanceKm.toFixed(1)} km • {movingMinutes} min
                              </p>
                              {activity.average_heartrate !== null && (
                                <p>
                                  HR: {activity.average_heartrate.toFixed(0)}{" "}
                                  bpm
                                </p>
                              )}
                              {activity.average_watts !== null && (
                                <p>W: {activity.average_watts.toFixed(0)} W</p>
                              )}
                              {activity.start_date && (
                                <p>
                                  {new Date(activity.start_date).toLocaleString(
                                    "fr-FR",
                                  )}
                                </p>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
