"use client";
import { useTransition } from "react";
import { useRouter } from "next/navigation";

export const RetryEvidence = () => {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <button
      className="text-link"
      disabled={pending}
      onClick={() => startTransition(() => router.refresh())}
    >
      {pending ? "Checking service…" : "Retry evidence request ↗"}
    </button>
  );
};
