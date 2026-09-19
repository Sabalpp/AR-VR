"use client";
import dynamic from "next/dynamic";
const QuestSession = dynamic(() => import("@/components/QuestSession"), { ssr: false });
export default function QuestPage() { return <QuestSession />; }
