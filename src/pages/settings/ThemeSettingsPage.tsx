import { Link, useNavigate } from "react-router";
import { ThemeSettingsPanel } from "../../components/productivity/settings/ThemeSettingsPanel";
import { SettingsPageScroll } from "./SettingsPageScroll";
import { Button } from "../../app/components/ui/button";

/** Study route `/settings/theme` — Focus uses Settings → Appearance. */
export default function ThemeSettingsPage() {
  const navigate = useNavigate();

  return (
    <SettingsPageScroll className="p-4 md:p-6 pb-16">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link to="/settings" className="text-sm text-primary hover:underline w-fit">
            ← Settings
          </Link>
          <Button type="button" size="sm" onClick={() => navigate(-1)}>
            Back
          </Button>
        </div>
        <ThemeSettingsPanel />
      </div>
    </SettingsPageScroll>
  );
}
