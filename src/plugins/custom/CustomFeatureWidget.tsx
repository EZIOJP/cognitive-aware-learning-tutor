import { Link } from "react-router";
import type { HubCustomFeature } from "../../api/hubClient";

type Props = { feature: HubCustomFeature };

export function CustomFeatureWidget({ feature }: Props) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        {feature.metrics.length} metric{feature.metrics.length === 1 ? "" : "s"} · log values on the feature page
      </p>
      <Link
        to={`/features/${feature.feature_id}`}
        className="text-xs text-primary hover:underline"
      >
        Open {feature.name} →
      </Link>
    </div>
  );
}
