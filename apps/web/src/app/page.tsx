import { LandingExperience } from "@/components/landing-experience";
import { loadReferenceSuccession } from "@/lib/data";

export default function HomePage() {
  return <LandingExperience reference={loadReferenceSuccession()} />;
}
