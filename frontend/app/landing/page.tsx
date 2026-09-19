import type { Metadata } from "next";
import LandingExperience from "@/components/ui/landing-experience";

export const metadata: Metadata = {
  title: "Reach — connected physical therapy",
  description:
    "Therapist dashboard and phone-camera seated-reach capture. The work you do at home stops being something you describe from memory.",
};

export default function Landing() {
  return <LandingExperience />;
}
