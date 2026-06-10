import { useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { CircleUserRound, LogOut, Shield, LogIn, Sparkles } from "lucide-react";
import { ThemeToggle } from "../components/theme/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { cn } from "../app/components/ui/utils";
import { PomodoroDock } from "./topbar/PomodoroDock";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../app/components/ui/dropdown-menu";

const PAGE_TITLES: Record<string, string> = {
  "/": "Study Hub",
  "/math-tutor": "Math Dashboard",
  "/math-tutor/reports": "Math Reports",
  "/gre-vocab": "GRE Vocabulary",
  "/settings": "Settings",
  "/gre-vocab/add-words": "Add Words",
};

/** Plan: top bar = profile, theme, pomodoro only. EEG / mirror live on dashboard & plugin pages. */
export function AppTopBar() {
  const nav = useNavigate();
  const { pathname } = useLocation();
  const { user, isAuthenticated, isAdmin, logout } = useAuth();
  const { typographyPack, motionLevel } = useTheme();
  const title = PAGE_TITLES[pathname] ?? "Study Companion";
  const titleClass =
    typographyPack !== "study"
      ? cn("hero-headline text-base", motionLevel === "hero" && "hero-text-shadow")
      : "text-lg font-semibold tracking-tight";

  const [clickCount, setClickCount] = useState(0);
  const [secretRevealed, setSecretRevealed] = useState(false);
  const [lastClickTime, setLastClickTime] = useState(0);

  const handleTitleClick = () => {
    const now = Date.now();
    if (now - lastClickTime > 500) {
      setClickCount(1);
    } else {
      setClickCount((prev) => prev + 1);
    }
    setLastClickTime(now);

    if (clickCount + 1 === 5) {
      setSecretRevealed(true);
      setClickCount(0);
      setTimeout(() => setSecretRevealed(false), 3000);
    }
  };

  return (
    <header className="gloss-topbar sticky top-0 z-40 shrink-0 border-b border-border/40">
      <div className="flex items-center justify-between gap-6 px-6 py-3.5">
        <div
          className="min-w-0 cursor-pointer select-none transition-transform hover:scale-[1.02] active:scale-[0.98]"
          onClick={handleTitleClick}
          title="Click me 5 times quickly..."
        >
          <div className="flex items-center gap-2">
            <h1 className={cn("truncate", titleClass)}>{title}</h1>
            {secretRevealed && <Sparkles className="w-4 h-4 text-yellow-500 animate-pulse" />}
          </div>
          <p className="text-[11px] text-muted-foreground/70 hidden sm:block">
            {secretRevealed ? "🎉 Secret discovered!" : "Cognitive-aware learning hub"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <PomodoroDock />
          <div className="w-px h-6 bg-border/50" />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="gloss-dock-btn rounded-full p-2 hover:scale-105 transition-transform"
                aria-label="Account menu"
                title={isAuthenticated ? user?.username : "Login"}
              >
                <CircleUserRound className="w-5 h-5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuLabel>
                {isAuthenticated ? `Signed in: ${user?.username}` : "Account"}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {!isAuthenticated ? (
                <DropdownMenuItem onClick={() => nav("/login")}>
                  <LogIn className="w-4 h-4 mr-2" />
                  Login / Register
                </DropdownMenuItem>
              ) : (
                <>
                  <DropdownMenuItem onClick={() => nav("/profile")}>
                    <CircleUserRound className="w-4 h-4 mr-2" />
                    Profile
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => nav("/settings/plugins")}>Plugins & features</DropdownMenuItem>
                  {isAdmin && (
                    <DropdownMenuItem onClick={() => nav("/admin")}>
                      <Shield className="w-4 h-4 mr-2" />
                      Admin Panel
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={() => {
                      logout();
                      nav("/");
                    }}
                  >
                    <LogOut className="w-4 h-4 mr-2" />
                    Logout
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
          <ThemeToggle size="sm" />
        </div>
      </div>
    </header>
  );
}
