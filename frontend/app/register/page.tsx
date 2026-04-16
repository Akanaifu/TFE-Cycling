"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  authPageStyles,
  commonPipelineStyles,
} from "../components/pipelineStyles";

export default function Register() {
  const apiUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_URL || "https://tfe-cycling.onrender.com",
    [],
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Validation
    if (!email.trim()) {
      setError("Email est requis");
      return;
    }

    if (password.length < 8) {
      setError("Le mot de passe doit faire au moins 8 caractères");
      return;
    }

    if (password !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${apiUrl}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          password,
          display_name: displayName.trim(),
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || "Erreur lors de l'enregistrement");
        return;
      }

      const data = await response.json();
      if (data.access_token) {
        // Store token and redirect
        localStorage.setItem("tfe_access_token", data.access_token);
        setSuccess(true);
        // Redirect after 1 second
        setTimeout(() => {
          window.location.href = "/strava";
        }, 1000);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erreur lors de l'enregistrement",
      );
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className={commonPipelineStyles.pageContainer}>
        <div className="rounded-md border border-emerald-300 bg-emerald-50 p-6 text-center">
          <h2 className="text-lg font-bold text-emerald-900">
            Compte créé avec succès !
          </h2>
          <p className="mt-2 text-emerald-700">
            Redirection vers le pipeline Strava...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={commonPipelineStyles.pageContainer}>
      <div className={authPageStyles.wrapper}>
        <h1 className={authPageStyles.title}>Créer un compte</h1>
        <p className={authPageStyles.subtitle}>
          Cree ton compte puis connecte ton Strava.
        </p>

        {error && <div className={authPageStyles.errorBox}>{error}</div>}

        <form onSubmit={handleRegister} className={authPageStyles.form}>
          <div>
            <p className={commonPipelineStyles.formLabel}>Email</p>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ton.email@exemple.com"
              className={commonPipelineStyles.textInput}
              disabled={loading}
            />
          </div>

          <div>
            <p className={commonPipelineStyles.formLabel}>Mot de passe</p>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimum 8 caractères"
              className={commonPipelineStyles.textInput}
              disabled={loading}
            />
          </div>

          <div>
            <p className={commonPipelineStyles.formLabel}>
              Confirmer le mot de passe
            </p>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Répète le mot de passe"
              className={commonPipelineStyles.textInput}
              disabled={loading}
            />
          </div>

          <div>
            <p className={commonPipelineStyles.formLabel}>
              Nom d&apos;affichage (optionnel)
            </p>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Ton nom (optionnel)"
              className={commonPipelineStyles.textInput}
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`${commonPipelineStyles.buttonDark} ${authPageStyles.submitButton}`}
          >
            {loading ? "Création en cours..." : "Créer le compte"}
          </button>
        </form>

        <p className={authPageStyles.switchText}>
          Tu as déjà un compte ?{" "}
          <Link href="/login" className={authPageStyles.switchLink}>
            Se connecter
          </Link>
        </p>
      </div>
    </div>
  );
}
