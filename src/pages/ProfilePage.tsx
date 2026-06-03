import { useAuth } from "../context/AuthContext";
import { LogOut } from "lucide-react";
import { useNavigate } from "react-router";

export function ProfilePage() {
  const { user, isAuthenticated, logout } = useAuth();
  const nav = useNavigate();

  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4">
        <h2 className="text-2xl font-bold">Not Logged In</h2>
        <p className="text-muted-foreground">Please log in to view your profile.</p>
        <button
          onClick={() => nav("/login")}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
        >
          Go to Login
        </button>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Profile</h1>
        <p className="text-muted-foreground mt-2">
          Manage your account settings and preferences.
        </p>
      </div>

      <div className="bg-card border border-border/50 rounded-xl p-6 shadow-sm space-y-4">
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">Username</p>
          <p className="text-lg font-semibold">{user?.username}</p>
        </div>
        
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">Role</p>
          <p className="text-lg font-semibold capitalize">{user?.role}</p>
        </div>
      </div>

      <div className="pt-4">
        <button
          onClick={() => {
            logout();
            nav("/");
          }}
          className="flex items-center gap-2 px-4 py-2 text-destructive hover:bg-destructive/10 rounded-lg transition-colors font-medium"
        >
          <LogOut className="w-4 h-4" />
          Log out
        </button>
      </div>
    </div>
  );
}
