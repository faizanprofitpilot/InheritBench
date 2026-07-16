import { LabNavigation } from "@/components/lab-navigation";

export default function OpsRouteLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <LabNavigation />
      {children}
    </div>
  );
}
