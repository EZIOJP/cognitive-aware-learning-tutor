import React from "react";
import { reportClientLog } from "../../api/systemClient";
import { copyClientErrorLog } from "../../lib/clientErrorLog";

type Props = {
  children: React.ReactNode;
};

type State = {
  error: Error | null;
  copyStatus: string | null;
};

export class AppErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null, copyStatus: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
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
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm hover:opacity-90"
            >
              Reload page
            </button>
            <button
              type="button"
              onClick={() => {
                void copyClientErrorLog().then((r) => {
                  this.setState({
                    copyStatus: r.ok
                      ? `Copied ${r.count} error(s)`
                      : r.error || "Copy failed",
                  });
                });
              }}
              className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-muted"
            >
              Copy error log
            </button>
          </div>
          {this.state.copyStatus ? (
            <p className="text-xs text-muted-foreground">{this.state.copyStatus}</p>
          ) : null}
        </div>
      );
    }
    return this.props.children;
  }
}
