import { ArrowRight, CircleSlash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { labelSystem, labelToken } from "@/lib/utils";

type Recommendation = {
  profile_id: string;
  eligible_systems: string[];
  ranking: string[];
  recommendation: string;
  reason_code: string;
};

export function MigrationProfiles({ profiles }: { profiles: Recommendation[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {profiles.map((profile) => {
        const empty = profile.recommendation === "NO_VIABLE_TRAINED_MIGRATION";
        return (
          <Card key={profile.profile_id} className="flex min-h-56 flex-col p-5">
            <Badge className="w-fit">Constraint profile</Badge>
            <h3 className="mt-4 text-lg font-semibold text-white">{labelToken(profile.profile_id)}</h3>
            <div className="mt-auto pt-8">
              {empty ? (
                <div className="flex items-start gap-3 text-amber-200">
                  <CircleSlash2 className="mt-0.5 h-5 w-5 shrink-0" />
                  <p className="font-medium">No viable trained migration</p>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-cyan-200">
                  <ArrowRight className="h-4 w-4" />
                  <p className="font-medium">{labelSystem(profile.recommendation)}</p>
                </div>
              )}
              <p className="mt-3 text-xs leading-5 text-slate-500">
                Eligible target systems: {profile.eligible_systems.length}. Qwen remains a reference.
              </p>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
