"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import FitImportRunner from "../components/FitImportRunner";
import { commonPipelineStyles } from "../components/pipelineStyles";

interface AuthUser {
  id: string;
  email: string;
  display_name?: string | null;
  role: string;
}

export default function FitImportPage() {
  const router = useRouter();
  const apiUrl = useMemo(() => process.env.NEXT_PUBLIC_API_URL || "", []);

  const [authChecked, setAuthChecked] = useState(false);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const fetchMe = async () => {
      try {
        const response = await fetch(`${apiUrl}/auth/me`, {
          credentials: "include",
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || `HTTP ${response.status}`);
        }
        setAuthUser(payload.user as AuthUser);
        setAuthChecked(true);
      } catch {
        router.replace("/login?next=/fit-import");
      }
    };

    fetchMe();
  }, [apiUrl, router]);

  if (!authChecked || !authUser) {
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
      <div className={commonPipelineStyles.pageHeader}>
        <div>
          <h1 className={commonPipelineStyles.pageTitle}>Import manuel FIT</h1>
          <p className={commonPipelineStyles.pageSubtitle}>
            Charge un ou plusieurs fichiers .fit et convertis-les en sorties PKL
            compatibles avec le pipeline.
          </p>
        </div>
        <Link
          href="/pipeline"
          className={commonPipelineStyles.redirectButtonSecondary}
        >
          ← Retour au Pipeline
        </Link>
      </div>

      <FitImportRunner authUser={authUser} />
    </div>
  );
}
