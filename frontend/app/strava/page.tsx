import { Suspense } from "react";
import StravaPipelineContent from "./strava-content";
import { commonPipelineStyles } from "../components/pipelineStyles";

function StravaPipelinePageLoading() {
  return (
    <div className={commonPipelineStyles.pageContainer}>
      <section className={commonPipelineStyles.card}>
        <h2 className={commonPipelineStyles.sectionTitleNoMargin}>
          Chargement...
        </h2>
      </section>
    </div>
  );
}

export default function StravaPipelinePage() {
  return (
    <Suspense fallback={<StravaPipelinePageLoading />}>
      <StravaPipelineContent />
    </Suspense>
  );
}
