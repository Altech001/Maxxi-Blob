import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, LogOut, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { maxxiApi } from '@/lib/maxxiApi';

const GOOGLE_CLIENT_ID =
  import.meta.env.VITE_GOOGLE_CLIENT_ID ||
  '607016949081-pu5rdrdaobgtvgiq8q6omf05thl3avpa.apps.googleusercontent.com';

type GoogleCredentialResponse = {
  credential?: string;
};

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: {
          initialize: (config: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: Record<string, string | number | boolean>,
          ) => void;
        };
      };
    };
  }
}

export default function GoogleAuthPanel() {
  const buttonRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const [scriptReady, setScriptReady] = useState(false);
  const hasToken = !!maxxiApi.getAuthToken();

  const { data: user, isError, isLoading } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => maxxiApi.getCurrentUser(),
    enabled: hasToken,
    retry: false,
  });

  useEffect(() => {
    if (window.google?.accounts?.id) {
      setScriptReady(true);
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>('script[src="https://accounts.google.com/gsi/client"]');
    if (existing) {
      existing.addEventListener('load', () => setScriptReady(true), { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => setScriptReady(true);
    document.head.appendChild(script);
  }, []);

  // Only render the Google button when we're sure the user is NOT authenticated
  const showGoogleButton = scriptReady && !user && !isLoading;

  useEffect(() => {
    if (!showGoogleButton || !buttonRef.current) return;
    const googleId = window.google?.accounts?.id;
    if (!googleId) return;

    buttonRef.current.innerHTML = '';
    googleId.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async (response) => {
        if (!response.credential) {
          toast.error('Google did not return a credential');
          return;
        }

        try {
          await maxxiApi.googleLogin(response.credential);
          await queryClient.invalidateQueries({ queryKey: ['auth-me'] });
          toast.success('Signed in with Google');
        } catch (error) {
          toast.error(error instanceof Error ? error.message : 'Google sign in failed');
        }
      },
    });
    googleId.renderButton(buttonRef.current, {
      theme: 'outline',
      size: 'medium',
      text: 'signin_with',
      shape: 'rectangular',
      width: 220,
    });

    // Cleanup: wipe the container when unmounting or when user becomes available
    return () => {
      if (buttonRef.current) {
        buttonRef.current.innerHTML = '';
      }
    };
  }, [queryClient, showGoogleButton]);

  const signOut = () => {
    maxxiApi.clearAuthToken();
    queryClient.removeQueries({ queryKey: ['auth-me'] });
    toast.success('Signed out');
  };

  // ── Authenticated ──────────────────────────────────────────────────────
  if (user) {
    return (
      <div className="flex items-center gap-3  rounded bg-card px-3 py-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
          <ShieldCheck className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{user.full_name}</p>
          <p className="truncate text-xs text-muted-foreground">{user.email}</p>
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={signOut}>
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  // ── Loading (verifying existing token) ─────────────────────────────────
  if (hasToken && isLoading) {
    return (
      <div className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Verifying session…</span>
      </div>
    );
  }

  // ── Unauthenticated ────────────────────────────────────────────────────
  return (
    <div className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2">
      <div ref={buttonRef} className="min-h-8 min-w-52" />
      {isError && <span className="text-xs text-destructive">Session expired</span>}
    </div>
  );
}

