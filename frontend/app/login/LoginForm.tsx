"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import {
  authPageStyles,
  commonPipelineStyles,
} from "../components/pipelineStyles";

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const apiUrl = useMemo(() => process.env.NEXT_PUBLIC_API_URL || "", []);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const next = searchParams.get("next") || "/pipeline";

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

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
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={commonPipelineStyles.pageContainer}>
      <div className={authPageStyles.wrapper}>
        <h1 className={authPageStyles.title}>Connexion</h1>
        <p className={authPageStyles.subtitle}>
          Connecte-toi pour acceder au pipeline de prediction.
        </p>

        {error && (
          <div className={authPageStyles.errorBox}>Erreur: {error}</div>
        )}

        <form onSubmit={handleLogin} className={authPageStyles.form}>
          <div>
            <p className={commonPipelineStyles.formLabel}>Email</p>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ton.email@exemple.com"
              className={commonPipelineStyles.textInput}
              required
              disabled={loading}
            />
          </div>

          <div>
            <p className={commonPipelineStyles.formLabel}>Mot de passe</p>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Ton mot de passe"
              className={commonPipelineStyles.textInput}
              required
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`${commonPipelineStyles.buttonDark} ${authPageStyles.submitButton}`}
          >
            {loading ? "Connexion..." : "Se connecter"}
          </button>
        </form>

        <p className={authPageStyles.switchText}>
          Pas encore de compte ?{" "}
          <Link href="/register" className={authPageStyles.switchLink}>
            Cree un compte
          </Link>
        </p>
      </div>
    </div>
  );
}
