import React, { Suspense } from "react";
import dynamic from "next/dynamic";

const ClientVerify = dynamic(() => import("./ClientVerify"), { ssr: false });

export default function VerifyEmailPage() {
  return (
    <main>
      <h1>Vérification email</h1>
      <Suspense fallback={<div>Chargement...</div>}>
        <ClientVerify />
      </Suspense>
    </main>
  );
}
