import PipelineRunner from "./components/PipelineRunner";
import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 bg-gray-100 min-h-screen py-8">
      <div className="container mx-auto">
        <h1 className="text-4xl font-bold text-gray-900 mb-8">
          TFE Cycling - Analyse des Prédictions de FC
        </h1>
        <div className="mb-6">
          <Link
            href="/strava"
            className="inline-block rounded-md border-2 border-slate-500 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-50"
          >
            Ouvrir le pipeline Strava
          </Link>
        </div>
        <PipelineRunner />
      </div>
    </div>
  );
}
