import { useState } from 'react';
import { Info, X } from 'lucide-react';

type InfoBannerProps = {
  message: string;
  linkText?: string;
  onLinkClick?: () => void;
};

export default function InfoBanner({ message, linkText, onLinkClick }: InfoBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/60 px-4 py-3 flex items-center gap-3 text-sm">
      <Info className="h-4 w-4 text-blue-500 shrink-0" />
      <p className="text-foreground flex-1">
        {message}{' '}
        {linkText && (
          <button onClick={onLinkClick} className="text-primary font-medium hover:underline">
            {linkText}
          </button>
        )}
      </p>
      <button onClick={() => setDismissed(true)} className="text-muted-foreground hover:text-foreground transition-colors">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
