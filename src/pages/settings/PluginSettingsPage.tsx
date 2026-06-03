import { usePlugins } from "../../plugins/registry";
import { Card } from "../../app/components/ui/card";
import { Settings2, Power, PowerOff } from "lucide-react";

export function PluginSettingsPage() {
  const { allPlugins, enabledIds, togglePlugin, isLoaded } = usePlugins();

  if (!isLoaded) return <div className="p-8">Loading plugins...</div>;

  return (
    <div className="h-full overflow-y-auto max-w-4xl mx-auto space-y-8 p-4">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Settings2 className="w-8 h-8 text-primary" />
          Plugin Manager
        </h1>
        <p className="text-muted-foreground mt-2">
          Customize your LifeOS by turning features on or off. Core features cannot be disabled.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {allPlugins.map((plugin) => {
          const isEnabled = plugin.isCore || enabledIds.includes(plugin.id);
          const Icon = plugin.icon;

          return (
            <Card
              key={plugin.id}
              className={`p-5 flex flex-col gloss-panel transition-all duration-300 ${
                isEnabled ? "ring-1 ring-primary/50" : "opacity-70 grayscale-[0.5]"
              }`}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      isEnabled ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg leading-tight">{plugin.name}</h3>
                    {plugin.isCore && (
                      <span className="text-[10px] uppercase font-bold tracking-wider text-primary/70">Core Plugin</span>
                    )}
                  </div>
                </div>
                
                {!plugin.isCore && (
                  <button
                    onClick={() => togglePlugin(plugin.id, !isEnabled)}
                    className={`p-2 rounded-full transition-colors ${
                      isEnabled 
                        ? "bg-emerald-500/20 text-emerald-500 hover:bg-emerald-500/30" 
                        : "bg-muted hover:bg-muted-foreground/20 text-muted-foreground"
                    }`}
                    title={isEnabled ? "Disable plugin" : "Enable plugin"}
                  >
                    {isEnabled ? <Power className="w-4 h-4" /> : <PowerOff className="w-4 h-4" />}
                  </button>
                )}
              </div>
              
              <p className="text-sm text-muted-foreground flex-1">
                {plugin.description}
              </p>
              
              <div className="mt-4 pt-4 border-t border-border/50 flex flex-wrap gap-2">
                {plugin.routes?.length ? (
                  <span className="text-[10px] px-2 py-1 rounded-md bg-muted text-muted-foreground">
                    {plugin.routes.length} Route(s)
                  </span>
                ) : null}
                {plugin.widgets?.length ? (
                  <span className="text-[10px] px-2 py-1 rounded-md bg-muted text-muted-foreground">
                    {plugin.widgets.length} Widget(s)
                  </span>
                ) : null}
                {plugin.Provider ? (
                  <span className="text-[10px] px-2 py-1 rounded-md bg-muted text-muted-foreground">
                    Has Background Context
                  </span>
                ) : null}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
