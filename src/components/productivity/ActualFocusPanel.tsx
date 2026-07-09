import { ActivityDetailPanel, type ActivityDetailPanelProps, type EventAnchorRect } from "./ActivityDetailPanel";

export type { EventAnchorRect };

type Props = ActivityDetailPanelProps;

export function ActualFocusPanel(props: Props) {
  return <ActivityDetailPanel {...props} />;
}
