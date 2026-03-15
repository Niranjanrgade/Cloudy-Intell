/**
 * SidebarNavigator — Left sidebar navigation for CloudyIntel.
 *
 * Provides navigation between the three main views:
 * - **AWS Architecture**: Shows the AWS agent workflow graph.
 * - **Azure Architecture**: Shows the Azure agent workflow graph.
 * - **Compare Solutions**: Shows a side-by-side architecture comparison.
 *
 * Also includes a Settings button (currently a placeholder for future
 * configuration options like model selection, iteration bounds, etc.).
 */
import { Cloud, Columns, Settings, Server } from 'lucide-react';
import { ViewMode } from './CopilotSidebar';

export function SidebarNavigator({ viewMode, setViewMode }: { viewMode: ViewMode, setViewMode: (mode: ViewMode) => void }) {
  return (
    <div className="w-64 h-full bg-slate-900 text-slate-300 flex flex-col shrink-0 z-50 shadow-xl">
      <div className="p-6 mb-4">
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
          <Cloud className="w-6 h-6 text-indigo-400" />
          CloudyIntel
        </h1>
        <p className="text-xs text-slate-500 mt-2 leading-relaxed">
          Agentic AI framework for Cloud Solution Architects
        </p>
      </div>
      
      <nav className="flex-1 px-4 space-y-2">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2">
          Architectures
        </div>
        <NavItem 
          icon={<Cloud className="w-5 h-5" />} 
          label="AWS Architecture" 
          active={viewMode === 'AWS'} 
          onClick={() => setViewMode('AWS')} 
          activeColor="bg-orange-500"
        />
        <NavItem 
          icon={<Server className="w-5 h-5" />} 
          label="Azure Architecture" 
          active={viewMode === 'Azure'} 
          onClick={() => setViewMode('Azure')} 
          activeColor="bg-blue-600"
        />
        
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-8 mb-3 px-2">
          Analysis
        </div>
        <NavItem 
          icon={<Columns className="w-5 h-5" />} 
          label="Compare Solutions" 
          active={viewMode === 'Compare'} 
          onClick={() => setViewMode('Compare')} 
          activeColor="bg-indigo-600"
        />
      </nav>
      
      <div className="p-4 border-t border-slate-800">
        <NavItem 
          icon={<Settings className="w-5 h-5" />} 
          label="Settings" 
          active={false} 
          onClick={() => {}} 
          activeColor="bg-slate-700"
        />
      </div>
    </div>
  );
}

function NavItem({ 
  icon, 
  label, 
  active, 
  onClick,
  activeColor
}: { 
  icon: React.ReactNode, 
  label: string, 
  active: boolean, 
  onClick: () => void,
  activeColor: string
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
        active 
          ? `${activeColor} text-white shadow-md` 
          : 'hover:bg-slate-800 hover:text-white text-slate-400'
      }`}
    >
      {icon}
      <span className="font-medium text-sm">{label}</span>
    </button>
  );
}
