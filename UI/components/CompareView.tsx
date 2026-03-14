import { Server } from 'lucide-react';
import type { ArchitectureState, ArchitectureDomainResult } from '@/lib/types';
import { DOMAIN_ICONS, AWS_DEFAULTS, AZURE_DEFAULTS, DOMAINS } from '@/lib/compare.config';
import React from 'react';

interface CompareViewProps {
  awsResult?: ArchitectureState | null;
  azureResult?: ArchitectureState | null;
}

export function CompareView({ awsResult, azureResult }: CompareViewProps) {
  const awsComponents = awsResult?.architecture_components;
  const azureComponents = azureResult?.architecture_components;

  return (
    <div className="w-full h-full flex gap-6 p-6 bg-slate-50 overflow-y-auto">
      {/* AWS Column */}
      <div className="flex-1 bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
          <h2 className="text-xl font-bold text-orange-600 flex items-center gap-2">
            AWS Architecture
          </h2>
          <span className="px-3 py-1 bg-orange-50 text-orange-600 text-xs font-semibold rounded-full border border-orange-100">
            {awsComponents ? 'Generated Solution' : 'Default Template'}
          </span>
        </div>

        <div className="space-y-4 flex-1 overflow-y-auto pr-2">
          {DOMAINS.map((domain) => (
            <SolutionCard
              key={domain}
              icon={DOMAIN_ICONS[domain] || <Server className="w-5 h-5" />}
              title={domain.charAt(0).toUpperCase() + domain.slice(1)}
              desc={getDomainDescription(awsComponents?.[domain], AWS_DEFAULTS[domain])}
            />
          ))}
        </div>
      </div>

      {/* Azure Column */}
      <div className="flex-1 bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
          <h2 className="text-xl font-bold text-blue-600 flex items-center gap-2">
            Azure Architecture
          </h2>
          <span className="px-3 py-1 bg-blue-50 text-blue-600 text-xs font-semibold rounded-full border border-blue-100">
            {azureComponents ? 'Generated Solution' : 'Default Template'}
          </span>
        </div>

        <div className="space-y-4 flex-1 overflow-y-auto pr-2">
          {DOMAINS.map((domain) => (
            <SolutionCard
              key={domain}
              icon={DOMAIN_ICONS[domain] || <Server className="w-5 h-5" />}
              title={domain.charAt(0).toUpperCase() + domain.slice(1)}
              desc={getDomainDescription(azureComponents?.[domain], AZURE_DEFAULTS[domain])}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function getDomainDescription(
  component: ArchitectureDomainResult | undefined,
  fallback: string,
): string {
  if (!component) return fallback;
  if (typeof component.recommendations === 'string' && component.recommendations.trim()) {
    // Take the first ~300 characters as a summary
    const rec = component.recommendations.trim();
    return rec.length > 300 ? rec.slice(0, 300) + '...' : rec;
  }
  return fallback;
}

function SolutionCard({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="p-4 border border-slate-100 rounded-lg bg-slate-50/50 flex items-start gap-4 hover:bg-slate-50 transition-colors">
      <div className="p-2 bg-white rounded-md shadow-sm text-slate-600 border border-slate-100 shrink-0">
        {icon}
      </div>
      <div>
        <h3 className="font-semibold text-slate-800 text-sm mb-1">{title}</h3>
        <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">{desc}</p>
      </div>
    </div>
  );
}
