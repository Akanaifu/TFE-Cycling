import Link from "next/link";
import { commonPipelineStyles } from "./components/pipelineStyles";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-white">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-900">404</h1>
        <p className="mt-4 text-2xl font-semibold text-gray-900">
          Page non trouvée
        </p>
        <p className="mt-2 text-gray-600">
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
