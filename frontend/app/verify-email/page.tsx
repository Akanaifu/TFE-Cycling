import React, { Suspense } from "react";
import ClientVerify from "./ClientVerify";

export default function VerifyEmailPage() {
  return (
    <main>
      <Suspense fallback={<div>Chargement...</div>}>
        <ClientVerify />
      </Suspense>
    </main>
  );
}
