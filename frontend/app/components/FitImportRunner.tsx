"use client";

import { useMemo, useState } from "react";
import { commonPipelineStyles, predictionPageStyles } from "./pipelineStyles";

interface AuthUser {
  id: string;
  email: string;
  display_name?: string | null;
  role: string;
}

interface FitImportResponse {
  ok: boolean;
  cyclist: string;
  saved_count: number;
  skipped_count: number;
  saved: Array<{ source_file: string; saved_file: string; rows: number }>;
  skipped: Array<{ file: string; reason: string }>;
}

interface FitImportRunnerProps {
  authUser: AuthUser;
}

export default function FitImportRunner({ authUser }: FitImportRunnerProps) {
  const apiUrl = useMemo(() => process.env.NEXT_PUBLIC_API_URL || "", []);

  const [fitFiles, setFitFiles] = useState<File[]>([]);
  const [loadingImport, setLoadingImport] = useState(false);
  const [fitImportError, setFitImportError] = useState<string | null>(null);
  const [fitImportResult, setFitImportResult] =
    useState<FitImportResponse | null>(null);

  const handleImportFit = async () => {
    if (fitFiles.length === 0) {
      setFitImportError("Sélectionne au moins un fichier .fit.");
      return;
    }

    setLoadingImport(true);
    setFitImportError(null);
    setFitImportResult(null);

    try {
      const formData = new FormData();
      for (const file of fitFiles) {
        formData.append("files", file);
      }

      const response = await fetch(`${apiUrl}/rides/import-fit`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });

      const payload = (await response.json()) as
        | FitImportResponse
        | { detail?: string };

      if (!response.ok) {
        const detail =
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : undefined;
        throw new Error(detail || `HTTP ${response.status}`);
      }

      if (!("ok" in payload)) {
        throw new Error("Réponse API invalide");
      }

      setFitImportResult(payload);
      setFitFiles([]);
    } catch (err) {
      setFitImportError(
        err instanceof Error
          ? err.message
          : "Erreur inconnue lors de l'import.",
      );
    } finally {
      setLoadingImport(false);
    }
  };

  return (
    <div className={commonPipelineStyles.sectionStack}>
      <div className={`${commonPipelineStyles.card} space-y-4`}>
        <h2 className={commonPipelineStyles.sectionTitleNoMargin}>
          Import manuel de fichiers FIT
        </h2>
        <p className={commonPipelineStyles.bodyText}>
          Importe un ou plusieurs fichiers .fit. Les sorties sont converties au
          format PKL standard du projet.
        </p>
        <p className={commonPipelineStyles.mutedText}>
          Les fichiers seront enregistrés automatiquement dans le dossier du
          compte connecté{authUser.display_name ? ` (${authUser.display_name})` : ""}.
        </p>
      </div>

      <div className={`${commonPipelineStyles.card} space-y-4`}>
        <h2 className={commonPipelineStyles.sectionTitle}>Fichiers</h2>
        <input
          type="file"
          accept=".fit"
          multiple
          onChange={(e) => {
            const files = Array.from(e.target.files || []);
            setFitFiles(files);
          }}
          className={commonPipelineStyles.textInput}
        />

        <button
          type="button"
          onClick={handleImportFit}
          disabled={loadingImport || fitFiles.length === 0}
          className={commonPipelineStyles.buttonPrimary}
        >
          {loadingImport
            ? "Import en cours..."
            : `Importer ${fitFiles.length || ""} fichier(s) FIT`}
        </button>

        {fitImportError && (
          <p className={commonPipelineStyles.errorText}>{fitImportError}</p>
        )}

        {fitImportResult && (
          <div className={predictionPageStyles.errorPanel}>
            <p className={predictionPageStyles.errorPanelTitle}>
              Import terminé pour {fitImportResult.cyclist}
            </p>
            <p className={predictionPageStyles.errorPanelBody}>
              Sauvegardés: {fitImportResult.saved_count} - Ignorés:{" "}
              {fitImportResult.skipped_count}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
