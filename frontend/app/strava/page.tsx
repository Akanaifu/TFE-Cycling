"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type StravaStatus = {
  configured: boolean;
  has_client_id: boolean;
  has_client_secret: boolean;
  has_redirect_uri: boolean;
  redirect_uri: string;
  scopes: string;
  tokens_file: string;
};

type ExchangeResult = {
  saved: boolean;
  tokens_file: string;
  token_type: string;
  expires_at: number | null;
  athlete_id: number | null;
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
  const apiUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    [],
  );

  const [status, setStatus] = useState<StravaStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(false);
  const [oauthCode, setOauthCode] = useState("");
  const [exchangeError, setExchangeError] = useState<string | null>(null);
  const [exchangeResult, setExchangeResult] = useState<ExchangeResult | null>(
    null,
  );
  const [loadingExchange, setLoadingExchange] = useState(false);
  const [activities, setActivities] = useState<StravaActivity[]>([]);
  const [activitiesError, setActivitiesError] = useState<string | null>(null);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [selectedActivityLimit, setSelectedActivityLimit] = useState(10);

  useEffect(() => {
    const loadStatus = async () => {
      setLoadingStatus(true);
      setStatusError(null);
      try {
        const response = await fetch(`${apiUrl}/strava/status`);
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
  }, [apiUrl]);

  const handleGenerateAuthUrl = async () => {
    setLoadingAuth(true);
    setAuthError(null);
    setAuthUrl(null);
    try {
      const response = await fetch(`${apiUrl}/strava/auth-url`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }
      setAuthUrl(payload.auth_url as string);
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoadingAuth(false);
    }
  };

  const handleExchangeCode = async () => {
    const code = oauthCode.trim();
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
        },
        body: JSON.stringify({ code }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }

      setExchangeResult(payload.result as ExchangeResult);
      setOauthCode("");

      const refreshedStatus = await fetch(`${apiUrl}/strava/status`);
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

  const handleFetchActivities = async () => {
    setLoadingActivities(true);
    setActivitiesError(null);
    setActivities([]);
    try {
      const response = await fetch(
        `${apiUrl}/strava/activities?limit=${selectedActivityLimit}`,
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }
      setActivities((payload.activities || []) as StravaActivity[]);
    } catch (err) {
      setActivitiesError(
        err instanceof Error ? err.message : "Erreur inconnue",
      );
    } finally {
      setLoadingActivities(false);
    }
  };

  const hasTokens = exchangeResult?.saved || status?.configured;

  return (
    <div className="min-h-screen bg-slate-100 py-10">
      <div className="container mx-auto max-w-6xl px-4">
        <div className="mb-8 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              Pipeline de connexion Strava
            </h1>
            <p className="mt-2 text-slate-700">
              Configure les credentials, connecte le compte, synchronise les
              activites, puis lance le pipeline de prediction.
            </p>
          </div>
          <Link
            href="/"
            className="rounded-md border-2 border-slate-500 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-50"
          >
            Retour au dashboard
          </Link>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          <section className="rounded-lg border border-slate-300 bg-white p-5 shadow-sm">
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-600">
              Etape 1
            </p>
            <h2 className="text-lg font-bold text-slate-900">
              Connexion OAuth
            </h2>
            <p className="mt-2 text-sm text-slate-700">
              Verifier la configuration puis obtenir l&apos;URL
              d&apos;autorisation Strava.
            </p>
            <div className="mt-4 rounded-md border border-slate-300 bg-slate-50 p-3 text-xs text-slate-800">
              {loadingStatus && <p>Verification des variables en cours...</p>}
              {statusError && (
                <p className="text-red-700">Erreur: {statusError}</p>
              )}
              {status && (
                <div className="space-y-1">
                  <p>Configuration: {status.configured ? "OK" : "Incomplet"}</p>
                  <p>Client ID: {status.has_client_id ? "OK" : "Manquant"}</p>
                  <p>
                    Client Secret:{" "}
                    {status.has_client_secret ? "OK" : "Manquant"}
                  </p>
                </div>
              )}
            </div>

            <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
              <p className="mb-3">
                Genere l&apos;URL OAuth depuis les credentials backend.
              </p>
              <button
                type="button"
                onClick={handleGenerateAuthUrl}
                disabled={loadingAuth}
                className="rounded-md bg-amber-600 px-3 py-2 font-semibold text-white hover:bg-amber-700 disabled:opacity-60"
              >
                {loadingAuth ? "Generation..." : "Generer URL OAuth"}
              </button>
              {authError && (
                <p className="mt-2 text-red-700">Erreur: {authError}</p>
              )}
              {authUrl && (
                <div className="mt-2 space-y-2">
                  <p className="break-all text-amber-950">{authUrl}</p>
                  <a
                    href={authUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-block rounded-md bg-slate-900 px-3 py-2 font-semibold text-white hover:bg-slate-800"
                  >
                    Ouvrir Strava
                  </a>
                </div>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-slate-300 bg-white p-5 shadow-sm">
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-600">
              Etape 2
            </p>
            <h2 className="text-lg font-bold text-slate-900">
              Echange de code
            </h2>
            <p className="mt-2 text-sm text-slate-700">
              Colle le parametre <span className="font-mono">code</span> de
              l&apos;URL de retour Strava puis echange-le contre les tokens.
            </p>
            <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
              <input
                type="text"
                value={oauthCode}
                onChange={(e) => setOauthCode(e.target.value)}
                placeholder="Ex: 9e2b4c..."
                className="w-full rounded-md border border-amber-400 bg-white px-3 py-2 text-amber-950 outline-none focus:ring-2 focus:ring-amber-500"
              />
              <button
                type="button"
                onClick={handleExchangeCode}
                disabled={loadingExchange}
                className="mt-3 rounded-md bg-slate-900 px-3 py-2 font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
              >
                {loadingExchange ? "Echange en cours..." : "Echanger le code"}
              </button>

              {exchangeError && (
                <p className="mt-2 text-red-700">Erreur: {exchangeError}</p>
              )}

              {exchangeResult && (
                <div className="mt-3 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-emerald-900">
                  <p className="font-semibold">Tokens enregistres.</p>
                  <p className="break-all">
                    Fichier: {exchangeResult.tokens_file}
                  </p>
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

          <section className="rounded-lg border border-slate-300 bg-white p-5 shadow-sm">
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-600">
              Etape 3
            </p>
            <h2 className="text-lg font-bold text-slate-900">
              Extraction + Sync
            </h2>
            <p className="mt-2 text-sm text-slate-700">
              Recupere les dernieres sorties velos de ton compte Strava, puis
              synchronise-les vers des fichiers PKL.
            </p>
            <div className="mt-4 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-xs text-emerald-900">
              {!hasTokens ? (
                <p className="text-amber-900">
                  Complete les etapes 1 et 2 pour activer l&apos;extraction.
                </p>
              ) : (
                <>
                  <div className="mb-3 flex items-end gap-2">
                    <div className="flex-1">
                      <label className="block text-xs font-semibold text-slate-700">
                        Nombre de sorties a recuperer:
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="100"
                        value={selectedActivityLimit}
                        onChange={(e) =>
                          setSelectedActivityLimit(
                            Math.max(1, parseInt(e.target.value) || 10),
                          )
                        }
                        className="mt-1 w-full rounded-md border border-emerald-400 bg-white px-3 py-2 text-slate-900 outline-none focus:ring-2 focus:ring-emerald-500"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={handleFetchActivities}
                      disabled={loadingActivities}
                      className="rounded-md bg-emerald-600 px-4 py-2 font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                    >
                      {loadingActivities ? "Extraction..." : "Extraire sorties"}
                    </button>
                  </div>

                  {activitiesError && (
                    <p className="mt-2 text-red-700">
                      Erreur: {activitiesError}
                    </p>
                  )}

                  {activities.length > 0 && (
                    <div className="mt-3 space-y-2 rounded-md border border-emerald-200 bg-emerald-100 p-3">
                      <p className="font-semibold text-emerald-900">
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
                              className="rounded border border-emerald-200 bg-white p-2 text-xs text-slate-700"
                            >
                              <p className="font-semibold">{activity.name}</p>
                              <div className="mt-1 space-y-1 text-slate-600">
                                <p>
                                  {distanceKm.toFixed(1)} km • {movingMinutes}{" "}
                                  min
                                </p>
                                {activity.average_heartrate !== null && (
                                  <p>
                                    HR: {activity.average_heartrate.toFixed(0)}{" "}
                                    bpm
                                  </p>
                                )}
                                {activity.average_watts !== null && (
                                  <p>
                                    W: {activity.average_watts.toFixed(0)} W
                                  </p>
                                )}
                                {activity.start_date && (
                                  <p>
                                    {new Date(
                                      activity.start_date,
                                    ).toLocaleString("fr-FR")}
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

        <section className="mt-6 rounded-lg border border-slate-300 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900">
            Prochaine integration
          </h2>
          <p className="mt-2 text-sm text-slate-700">
            Une fois les sorties extraites, elles seront automatiquement
            synchronisees en PKL et prete pour le pipeline de prediction.
          </p>
        </section>
      </div>
    </div>
  );
}
