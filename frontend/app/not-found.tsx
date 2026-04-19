import Link from "next/link";
import { commonPipelineStyles } from "./components/pipelineStyles";

export default function NotFound() {
  return (
    <div className="flex min-h-[calc(100vh-88px)] flex-col items-center justify-center px-6 py-16 text-center">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-[#fff4f1]">404</h1>
        <p className="mt-4 text-2xl font-semibold text-[#fff4f1]">
          Page non trouvée
        </p>
        <p className="mt-2 text-[#f8d7d2]/80">
          La page que tu cherches n&apos;existe pas ou a été déplacée.
        </p>
        <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <Link href="/" className={commonPipelineStyles.redirectButtonPrimary}>
            Retourner à l&apos;accueil
          </Link>
          <Link
            href="/strava"
            className={commonPipelineStyles.redirectButtonSecondary}
          >
            Aller à Strava
          </Link>
        </div>
      </div>
    </div>
  );
}
