import React, { Suspense } from "react";
import ClientVerify from "./ClientVerify";

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
