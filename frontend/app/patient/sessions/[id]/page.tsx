"use client";
import { use } from "react";
import dynamic from "next/dynamic";
import { Shell } from "@/components/Shell";
const CameraSession = dynamic(() => import("@/components/CameraSession"), {
  ssr: false,
  loading: () => <p className="empty">Preparing camera setup…</p>,
});
export default function SessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <Shell patient>
      <CameraSession id={id} />
    </Shell>
  );
}
