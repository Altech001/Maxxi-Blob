import { ShieldCheck, Mic, X, MessageSquareText } from "lucide-react";
import { SearchStatus } from "@/components/SearchStatus";
import { AnimatedCat } from "@/components/AnimatedCat";

const Index = () => {
  return (
    <main className="relative flex min-h-screen flex-col items-center bg-background px-6 pt-8 pb-10 text-foreground">
      {/* Privacy badge */}
      <div className="flex items-center gap-2 text-sm font-medium text-[hsl(var(--success))]">
        <ShieldCheck className="h-4 w-4" aria-hidden="true" />
        <span>All chats are private</span>
      </div>

      {/* Animated cat */}
      <div className="mt-6 flex justify-center">
        <AnimatedCat />
      </div>

      {/* AI response text */}
      <section className="mx-auto mt-16 w-full max-w-2xl">
        <h1 className="sr-only">AI voice assistant</h1>
        <p className="text-lg leading-relaxed text-foreground">
          Sure, let me search for the latest information about the top-rated movies right now. I'll
        </p>
      </section>

      {/* Spacer pushes controls to bottom */}
      <div className="flex-1" />

      <div className="mb-5">
        <SearchStatus />
      </div>

      {/* Control pill */}
      <div className="flex items-center gap-2 rounded-full bg-[hsl(var(--pill))] px-3 py-2 shadow-lg">
        <button
          type="button"
          aria-label="Show transcript"
          className="flex h-11 w-11 items-center justify-center rounded-full text-[hsl(var(--pill-foreground))] transition-colors hover:bg-white/10"
        >
          <MessageSquareText className="h-5 w-5" />
        </button>
        <button
          type="button"
          aria-label="Mute microphone"
          className="flex h-11 w-11 items-center justify-center rounded-full text-[hsl(var(--pill-foreground))] transition-colors hover:bg-white/10"
        >
          <Mic className="h-5 w-5" />
        </button>
        <button
          type="button"
          aria-label="End conversation"
          className="flex h-11 w-11 items-center justify-center rounded-full text-[hsl(var(--pill-foreground))] transition-colors hover:bg-white/10"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Footer */}
      <p className="mt-3 text-xs text-muted-foreground">
        All chats are <span className="underline">private</span>. AI can make mistakes.
      </p>
    </main>
  );
};

export default Index;
