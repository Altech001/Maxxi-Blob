import { Loader2 } from "lucide-react";

export function SearchStatus() {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground">
      <Loader2 className="h-3.5 w-3.5 animate-spin" />
      Searching
    </div>
  );
}
