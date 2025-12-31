import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { 
  Loader2, 
  UserCircle, 
  ArrowLeft, 
  ShieldAlert, 
  ShieldCheck, 
  Lock, 
  AlertTriangle, 
  Activity,
  Search
} from "lucide-react";
import { cn } from "../components/ui/utils";

const API_URL = import.meta.env.VITE_API_URL || '';

// --- Interfaces ---

interface SecurityIncident {
  id: string;
  severity: 'high' | 'medium' | 'low';
  type: string;
  source_ip: string;
  timestamp: string;
  status: 'resolved' | 'pending';
}

interface SecurityStats {
  active_threats: number;
  blocked_ips_24h: number;
  system_health: string;
}

interface SecurityData {
  admin_name: string;
  stats: SecurityStats;
  recent_incidents: SecurityIncident[];
}

// --- Helper Components (Reused from FrameAdmin) ---

interface ActionButtonProps {
    onClick: (e?: React.MouseEvent<HTMLButtonElement>) => void;
    children: React.ReactNode;
    variant?: 'primary' | 'secondary'
    isLoading?: boolean;
    className?: string;
    icon?: React.ElementType;
}

function ActionButton({ onClick, children, variant = 'primary', isLoading = false, className = '', icon: Icon }: ActionButtonProps) {
    const baseClasses = "box-border cursor-pointer flex h-[50px] items-center justify-center rounded-[8px] w-full transition-colors font-medium text-lg md:text-xl";
    const variantClasses = {
        primary: "bg-[#c8102e] hover:bg-[#b00f29] active:bg-[#a00d25] text-white shadow-lg hover:shadow-xl",
        secondary: "bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] text-black shadow-md hover:shadow-lg",
    };
    return (
        <button 
            onClick={onClick} 
            className={cn(baseClasses, variantClasses[variant], isLoading ? 'opacity-75 cursor-not-allowed' : '', className)}
            disabled={isLoading}
        >
            {isLoading ? <Loader2 className="animate-spin h-6 w-6" /> : (
                <div className="flex items-center justify-center gap-2">
                    {Icon && <Icon className="h-5 w-5" />}
                    <span>{children}</span>
                </div>
            )}
        </button>
    );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
    return <h2 className="text-2xl md:text-3xl font-semibold text-black text-left">{children}</h2>;
}

// --- Main Component ---

export default function FrameSecurity() {
  const navigate = useNavigate();
  const [data, setData] = useState<SecurityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingDots, setLoadingDots] = useState("");

  // Helper to get severity color
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'text-red-600 bg-red-50 border-red-200';
      case 'medium': return 'text-orange-600 bg-orange-50 border-orange-200';
      case 'low': return 'text-blue-600 bg-blue-50 border-blue-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  // Helper to get system health text color
  const getHealthColor = (health?: string) => {
    switch (health?.toLowerCase()) {
      case 'critical': return 'text-red-600';
      case 'warning': return 'text-orange-500';
      default: return 'text-green-600'; // Good
    }
  };

  // Helper to get system health background/icon color
  const getHealthBg = (health?: string) => {
    switch (health?.toLowerCase()) {
      case 'critical': return 'bg-red-100 text-red-600';
      case 'warning': return 'bg-orange-100 text-orange-600';
      default: return 'bg-green-100 text-green-600';
    }
  };

  const getToken = () => localStorage.getItem('token');

  const handleLogout = useCallback(() => {
    localStorage.removeItem("token");
    navigate("/login");
  }, [navigate]);

  const fetchSecurityData = useCallback(async () => {
    const token = getToken();
    if (!token) {
        handleLogout();
        return;
    }
    setLoading(true);
    try {
        const response = await fetch(`${API_URL}/api/admin/security-data`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });

        if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
                throw new Error('Unauthorized access.');
            }
            throw new Error('Failed to fetch security data.');
        }
        
        const json: SecurityData = await response.json();
        setData(json);
    } catch (err: any) {
        console.error("Error real:", err);
        setError(err.message); 
        setLoading(false);
    } finally {
        setLoading(false);
    }
  }, [handleLogout]);

  useEffect(() => {
    fetchSecurityData();
  }, [fetchSecurityData]);

  useEffect(() => {
    if (!loading) return;

    const interval = setInterval(() => {
        setLoadingDots((prev) => (prev.length >= 3 ? "" : prev + "."));
    }, 400);

    return () => clearInterval(interval);
  }, [loading]);


  if (error && !data) {
    return (
        <div className="w-full min-h-screen flex flex-col items-center justify-center bg-gray-100 p-4">
            <div className="w-full max-w-sm md:max-w-md p-8 bg-white rounded-xl shadow-md text-center border border-red-300">
                <ShieldAlert className="h-12 w-12 text-red-700 mx-auto mb-4" />
                <h1 className="text-2xl font-bold text-red-700">Security Access Error</h1>
                <p className="mt-4 text-sm text-gray-600">{error || "Could not load security module."}</p>
                <ActionButton onClick={() => navigate('/admin')} variant="secondary" className="mt-8 max-w-[200px] mx-auto">
                    Back to Admin
                </ActionButton>
            </div>
        </div>
    );
  }

  return (
        <div className="flex flex-col min-h-screen bg-background">
            {/* Header Section (Consistent with FrameAdmin) */}
            <div className="fixed top-0 left-0 right-0 z-40 bg-background pt-6 md:pt-8">
                <div className="w-full mx-auto px-4 sm:px-6 lg:px-10">
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        <button
                            onClick={() => navigate('/admin')}
                            aria-label="Back to Admin"
                            className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] rounded-full transition-colors"
                        >
                            <ArrowLeft className="w-6 h-6 md:w-7 md:h-7 text-black" />
                        </button>
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center flex items-center gap-2">
                            <Lock className="w-5 h-5 md:w-6 md:h-6" /> Security Center
                        </h1>
                        <button
                            onClick={() => navigate('/profile')}
                            className="absolute right-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors"
                        >
                             <UserCircle className="w-6 h-6 md:w-7 md:h-7 text-black" />
                        </button>
                    </div>
                     <div className="border-b border-[#e6e6e6]"></div>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-grow w-full flex flex-col gap-10 px-4 sm:px-6 lg:px-10 pb-12 pt-8 md:pt-12">

                {/* CONDITIONAL: If loading show spinner, else show content */}
                {loading ? (
                    <div className="flex flex-col items-center justify-center h-[75vh] w-full">
                        <div className="relative">
                            <p className="text-gray-500 font-medium">
                                Fetching security data
                            </p>
                            
                            <span className="absolute left-full top-0 text-gray-500 font-medium">
                                {loadingDots}
                            </span>
                        </div>
                    </div>
                ) : (    
                    <div className="w-full px-4 sm:px-6 lg:px-10">

                        <div className="w-full mb-10">
                            <SectionTitle>Security Overview</SectionTitle>
                        </div>

                        {/* Status Cards Row */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
                            {/* Card 1 */}
                            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm flex items-center justify-between">
                                <div>
                                    <p className="text-gray-500 text-sm font-medium">Active Threats</p>
                                    <p className="text-3xl font-bold text-red-600 mt-1">{data?.stats.active_threats}</p>
                                </div>
                                <div className="h-12 w-12 bg-red-100 rounded-full flex items-center justify-center">
                                    <ShieldAlert className="h-6 w-6 text-red-600" />
                                </div>
                            </div>
                            {/* Card 2 */}
                            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm flex items-center justify-between">
                                <div>
                                    <p className="text-gray-500 text-sm font-medium">Blocked IPs (24h)</p>
                                    <p className="text-3xl font-bold text-gray-800 mt-1">{data?.stats.blocked_ips_24h}</p>
                                </div>
                                <div className="h-12 w-12 bg-gray-100 rounded-full flex items-center justify-center">
                                    <BanIcon className="h-6 w-6 text-gray-600" />
                                </div>
                            </div>
                            {/* Card 3 */}
                            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm flex items-center justify-between">
                                <div>
                                    <p className="text-gray-500 text-sm font-medium">System Health</p>
                                    <p className={cn("text-3xl font-bold mt-1", getHealthColor(data?.stats.system_health))}>
                                        {data?.stats.system_health}
                                    </p>
                                </div>
                                <div className={cn("h-12 w-12 rounded-full flex items-center justify-center transition-colors", getHealthBg(data?.stats.system_health))}>
                                    {/* Canviem la icona segons l'estat si vols, o deixem Activity per defecte */}
                                    {data?.stats.system_health === 'Critical' ? (
                                        <AlertTriangle className="h-6 w-6" />
                                    ) : (
                                        <Activity className="h-6 w-6" />
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Recent Incidents Table/List */}
                        <div className="w-full mb-12">
                            <h3 className="text-xl md:text-2xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
                                Recent Incidents
                            </h3>
                            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
                                {data?.recent_incidents && data.recent_incidents.length > 0 ? (
                                    <div className="divide-y divide-gray-100">
                                        {data.recent_incidents.map((incident) => (
                                            <div key={incident.id} className="p-4 md:p-5 flex flex-col md:flex-row md:items-center justify-between hover:bg-gray-50 transition-colors">
                                                <div className="flex flex-col gap-1 mb-3 md:mb-0">
                                                    <div className="flex items-center gap-3">
                                                        <span className={cn("px-2 py-1 rounded-md text-xs font-bold uppercase border", getSeverityColor(incident.severity))}>
                                                            {incident.severity}
                                                        </span>
                                                        <span className="font-medium text-gray-900">{incident.type}</span>
                                                    </div>
                                                    <div className="text-sm text-gray-500 flex gap-4 mt-1">
                                                        <span>IP: {incident.source_ip}</span>
                                                        <span>•</span>
                                                        <span>{incident.timestamp}</span>
                                                    </div>
                                                </div>
                                                
                                                <div className="flex items-center gap-3">
                                                    {incident.status === 'resolved' ? (
                                                        <div className="flex items-center text-green-600 text-sm font-medium">
                                                            <ShieldCheck className="h-4 w-4 mr-1" /> Resolved
                                                        </div>
                                                    ) : (
                                                        <button className="text-sm bg-white border border-gray-300 text-gray-700 px-3 py-1.5 rounded-md hover:bg-gray-50 font-medium">
                                                            Review
                                                        </button>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="p-8 text-center text-gray-500">No security incidents found.</div>
                                )}
                            </div>
                        </div>

                        {/* Quick Actions */}
                        <div className="w-full">
                            <h3 className="text-xl md:text-2xl font-semibold text-gray-800 mb-4">Security Actions</h3>
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                                <ActionButton onClick={() => console.log('Audit Logs')} variant="secondary" icon={Search}>
                                    Audit Logs
                                </ActionButton>
                                <ActionButton onClick={() => console.log('Rules')} variant="secondary" icon={Lock}>
                                    Firewall Rules
                                </ActionButton>
                                <ActionButton onClick={() => console.log('Lockdown')} variant="primary" icon={ShieldAlert}>
                                    System Lockdown
                                </ActionButton>
                            </div>
                        </div>

                    </div>
                )}
            </div>
        </div>
  );
}

// Simple Icon component for the card (locally defined to avoid missing imports if not in lucide list provided)
function BanIcon({ className }: { className?: string }) {
    return (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
            <circle cx="12" cy="12" r="10" />
            <path d="m4.9 4.9 14.2 14.2" />
        </svg>
    )
}