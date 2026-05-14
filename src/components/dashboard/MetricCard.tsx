import type { LucideIcon } from 'lucide-react';

const gradients = {
  purple: 'from-violet-50 via-purple-50/60 to-white border-violet-100/60',
  blue: 'from-blue-50 via-sky-50/60 to-white border-blue-100/60',
  amber: 'from-amber-50/80 via-orange-50/40 to-white border-amber-100/60',
} as const;

const iconColors = {
  purple: 'text-violet-500',
  blue: 'text-blue-500',
  amber: 'text-amber-500',
} as const;

type MetricColor = keyof typeof gradients;

type MetricCardProps = {
  icon: LucideIcon;
  label: string;
  value: string | number;
  color?: MetricColor;
};

export default function MetricCard({ icon: Icon, label, value, color = 'purple' }: MetricCardProps) {
  return (
    <div className={`rounded-xl border bg-gradient-to-br ${gradients[color]} p-5 flex items-center gap-4`}>
      <div className={`${iconColors[color]}`}>
        <Icon className="h-6 w-6" strokeWidth={1.8} />
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground tracking-wide uppercase">{label}</p>
        <p className="text-2xl font-bold text-foreground mt-0.5">{value}</p>
      </div>
    </div>
  );
}
