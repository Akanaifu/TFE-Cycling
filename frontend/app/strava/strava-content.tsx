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
  auto_deauthorized?: boolean;
  auto_deauth_days?: number;
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

export default function StravaPipelineContent() {
  const { replace } = useRouter();
  const searchParams = useSearchParams();
  const apiUrl = useMemo(() => process.env.NEXT_PUBLIC_API_URL || "", []);
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
  const [loadingDeauthorize, setLoadingDeauthorize] = useState(false);
  const [deauthorizeError, setDeauthorizeError] = useState<string | null>(null);
  const [deauthorizeInfo, setDeauthorizeInfo] = useState<string | null>(null);
  const [selectedActivityLimit, setSelectedActivityLimit] = useState(10);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [oauthState, setOauthState] = useState("");

  const extractOAuthParams = (
    value: string,
  ): { code: string; state: string } => {
    const clean = (value || "").trim().replace(/^['\"]|['\"]$/g, "");
    if (!clean) {
      return { code: "", state: "" };
    }

    const paramsFromQuery = (
      query: string,
    ): { code: string; state: string } => {
      const params = new URLSearchParams(query);
      return {
        code: (params.get("code") || "").trim(),
        state: (params.get("state") || "").trim(),
      };
    };

    if (clean.startsWith("http://") || clean.startsWith("https://")) {
      try {
        const url = new URL(clean);
        const fromSearch = paramsFromQuery(url.search.slice(1));
        if (fromSearch.code || fromSearch.state) {
          return fromSearch;
        }
        return paramsFromQuery(url.hash.slice(1));
      } catch {
        return { code: "", state: "" };
      }
    }

    if (clean.startsWith("?")) {
      return paramsFromQuery(clean.slice(1));
    }

    if (clean.includes("code=") && clean.includes("=")) {
      return paramsFromQuery(clean.replace(/^#/, ""));
    }

    return { code: clean, state: "" };
  };

  useEffect(() => {
    setAuthToken("cookie-session");
    setAuthChecked(true);
  }, []);

  useEffect(() => {
    const fetchMe = async () => {
      if (!authToken) {
        return;
      }
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
        setAuthToken(null);
        setAuthUser(null);
        replace("/login?next=/strava");
      }
    };

    fetchMe();
  }, [apiUrl, authToken, replace]);

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
          credentials: "include",
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
  }, [apiUrl, authToken]);

  const handleLogout = async () => {
    try {
      await fetch(`${apiUrl}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      setAuthToken(null);
      setAuthUser(null);
      setStatus(null);
      setActivities([]);
      setExchangeResult(null);
      replace("/login?next=/strava");
    }
  };

  const handleGenerateAuthUrl = async () => {
    setLoadingAuth(true);
    setOauthAuthError(null);
    setAuthUrl(null);
    try {
      const response = await fetch(`${apiUrl}/strava/auth-url`, {
        credentials: "include",
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }
      setAuthUrl(payload.auth_url as string);
      setOauthState((payload.oauth_state as string) || "");
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

    const extracted = extractOAuthParams(oauthCode);
    const code = extracted.code;
    const state =
      extracted.state || oauthState || (searchParams.get("state") || "").trim();
    if (!code) {
      setExchangeError("Le code OAuth est requis.");
      setExchangeResult(null);
      return;
    }
    if (!state) {
      setExchangeError("Le state OAuth est requis.");
      setExchangeResult(null);
      return;
    }

    setLoadingExchange(true);
    setExchangeError(null);
    setExchangeResult(null);
    try {
      const response = await fetch(`${apiUrl}/strava/exchange-code`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ code, state }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }

      setExchangeResult(payload.result as ExchangeResult);
      setOauthCode("");

      const refreshedStatus = await fetch(`${apiUrl}/strava/status`, {
        credentials: "include",
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
      const stateFromUrl = (searchParams.get("state") || "").trim();
      if (!codeFromUrl || !stateFromUrl) {
        return;
      }

      autoExchangeDoneRef.current = true;
      setLoadingExchange(true);
      setExchangeError(null);
      setExchangeResult(null);

      try {
        const response = await fetch(`${apiUrl}/strava/exchange-code`, {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ code: codeFromUrl, state: stateFromUrl }),
        });

        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || `HTTP ${response.status}`);
        }

        setExchangeResult(payload.result as ExchangeResult);

        const refreshedStatus = await fetch(`${apiUrl}/strava/status`, {
          credentials: "include",
        });
        const refreshedPayload = await refreshedStatus.json();
        if (refreshedStatus.ok) {
          setStatus(refreshedPayload.status as StravaStatus);
        }

        replace("/strava");
      } catch (err) {
        setExchangeError(
          err instanceof Error ? err.message : "Erreur inconnue",
        );
      } finally {
        setLoadingExchange(false);
      }
    };

    autoExchangeCode();
  }, [apiUrl, authToken, replace, searchParams]);

  const handlePasteOAuthCode = async () => {
    try {
      const pasted = await navigator.clipboard.readText();
      const normalized = extractOAuthParams(pasted);
      if (!normalized.code) {
        setExchangeError("Aucun code OAuth detecte dans le presse-papiers.");
        return;
      }
      setOauthCode(normalized.code);
      if (normalized.state) {
        setOauthState(normalized.state);
      }
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
          credentials: "include",
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

  const handleDeauthorize = async () => {
    if (!authToken) {
      setDeauthorizeError("Connecte-toi avant de revoquer l'acces Strava.");
      return;
    }

    const confirmed = window.confirm(
      "Confirmer la revocation de l'acces Strava pour ce compte ?",
    );
    if (!confirmed) {
      return;
    }

    setLoadingDeauthorize(true);
    setDeauthorizeError(null);
    setDeauthorizeInfo(null);

    try {
      const response = await fetch(`${apiUrl}/strava/deauthorize`, {
        method: "POST",
        credentials: "include",
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }

      const hadAccount = Boolean(payload?.result?.had_account);
      const remoteRevoked = Boolean(payload?.result?.remote_revoked);
      setDeauthorizeInfo(
        hadAccount
          ? remoteRevoked
            ? "Acces Strava revoque et tokens locaux supprimes."
            : "Tokens locaux supprimes. Revocation distante non confirmee."
          : "Aucun compte Strava actif a revoquer.",
      );

      setExchangeResult(null);
      setActivities([]);
      setActivitiesSavedInfo(null);

      const refreshedStatus = await fetch(`${apiUrl}/strava/status`, {
        credentials: "include",
      });
      const refreshedPayload = await refreshedStatus.json();
      if (refreshedStatus.ok) {
        setStatus(refreshedPayload.status as StravaStatus);
      }
    } catch (err) {
      setDeauthorizeError(
        err instanceof Error ? err.message : "Erreur inconnue",
      );
    } finally {
      setLoadingDeauthorize(false);
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
                {status.auto_deauthorized && (
                  <p className="text-amber-700">
                    L&apos;acces Strava a ete revoque automatiquement apres
                    inactivite ({status.auto_deauth_days ?? 0} jours).
                  </p>
                )}
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
                <p className="break-all text-[#ffd60a]">{authUrl}</p>
                <a
                  href={authUrl}
                  className={stravaPageStyles.openLink}
                  target="_blank"
                >
                  Ouvrir Strava
                </a>
                <p className="text-sm text-[#dbeafe]/80">
                  Apres autorisation, Strava te redirige vers mon portfolio pour
                  récupérer le code d&apos;échange
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
                  <p className="mt-2 text-green-700">{activitiesSavedInfo}</p>
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

                <div className={stravaPageStyles.oauthPanel}>
                  <p className="mb-3">
                    Revoque immediatement l&apos;acces Strava pour ce compte
                    depuis l&apos;application.
                  </p>
                  <button
                    type="button"
                    onClick={handleDeauthorize}
                    disabled={loadingDeauthorize || !status?.connected}
                    className={stravaPageStyles.actionButton}
                  >
                    {loadingDeauthorize
                      ? "Revocation en cours..."
                      : "Revoquer l'acces Strava"}
                  </button>
                  {!status?.connected && (
                    <p className="mt-2 text-sm text-[#dbeafe]/80">
                      Aucun compte Strava actif n&apos;est actuellement
                      connecte.
                    </p>
                  )}
                  {deauthorizeError && (
                    <p className={stravaPageStyles.inlineError}>
                      Erreur: {deauthorizeError}
                    </p>
                  )}
                  {deauthorizeInfo && (
                    <p className="mt-2 text-green-700">{deauthorizeInfo}</p>
                  )}
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
