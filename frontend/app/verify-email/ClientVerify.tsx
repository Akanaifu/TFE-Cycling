"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  authPageStyles,
  commonPipelineStyles,
} from "../components/pipelineStyles";

export default function ClientVerify() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const apiUrl = useMemo(() => process.env.NEXT_PUBLIC_API_URL || "", []);
  const initialEmail = searchParams?.get("email") || "";

  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (initialEmail) setEmail(initialEmail);
  }, [initialEmail]);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!email.trim()) {
      setError("L'email est requis");
      return;
    }

    if (!code.trim()) {
      setError("Le code de vérification est requis");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${apiUrl}/auth/verify-email`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          code: code.trim().toUpperCase(),
        }),
      });

      const payload = await response.json();

      if (!response.ok) {
        setError(payload.detail || "Erreur lors de la vérification");
        return;
      }

      setSuccess(payload.message || "Email vérifié avec succès");
      router.push("/login?verified=1");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erreur lors de la vérification",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={commonPipelineStyles.pageContainer}>
      <div className={authPageStyles.wrapper}>
        <h1 className={authPageStyles.title}>Vérifier mon compte</h1>
        <p className={authPageStyles.subtitle}>
          Encode le code reçu par mail pour activer ton compte.
        </p>

        {error && <div className={authPageStyles.errorBox}>{error}</div>}
        {success && <div className={authPageStyles.errorBox}>{success}</div>}

        <form onSubmit={handleVerify} className={authPageStyles.form}>
          <div>
            <label className={commonPipelineStyles.formLabel} htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ton.email@exemple.com"
              className={commonPipelineStyles.textInput}
              disabled={loading}
              readOnly
            />
          </div>

          <div>
            <label className={commonPipelineStyles.formLabel} htmlFor="code">
              Code de vérification
            </label>
            <input
              id="code"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Ex: A1B2C3"
              maxLength={6}
              className={commonPipelineStyles.textInput}
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`${commonPipelineStyles.buttonDark} ${authPageStyles.submitButton}`}
          >
            {loading ? "Vérification en cours..." : "Vérifier le compte"}
          </button>
        </form>

        <p className={authPageStyles.switchText}>
          <a href="/login" className={authPageStyles.switchLink}>
            Retour à la connexion
          </a>
        </p>
      </div>
    </div>
  );
}
