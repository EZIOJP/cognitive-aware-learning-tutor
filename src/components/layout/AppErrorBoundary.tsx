import React from "react";
import { reportClientLog } from "../../api/systemClient";

type Props = {
  children: React.ReactNode;
};

type State = {
  error: Error | null;
};

export class AppErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    reportClientLog({
      level: "error",
      message: error.message,
      context: "AppErrorBoundary",
      stack: info.componentStack || error.stack,
    });
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-6 bg-background text-foreground">
          <h1 className="text-lg font-semibold">App crashed</h1>
          <p className="text-sm text-muted-foreground text-center max-w-md">
            Something went wrong while rendering. This can happen after a hot reload — try a hard
            refresh (Ctrl+Shift+R) or reload the page.
          </p>
          <p className="text-xs text-red-400/90 font-mono max-w-lg truncate" title={this.state.error.message}>
            {this.state.error.message}
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm hover:opacity-90"
          >
            Reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
