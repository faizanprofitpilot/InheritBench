import { LandingExperience } from "@/components/landing-experience";
import { loadStory, loadSystems } from "@/lib/data";

export default function HomePage() {
  return <LandingExperience story={loadStory()} systems={loadSystems()} />;
}
