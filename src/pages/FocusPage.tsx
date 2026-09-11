import { Navigate } from "react-router";

/** Focus page retired — live SoftLand / Arm live on Settings → Overview. */
export default function FocusPage() {
  return (
    <Navigate
      to={{ pathname: "/productivity", search: "?tab=settings&section=overview" }}
      replace
    />
  );
}
