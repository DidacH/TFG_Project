import { useState, useEffect, useCallback, useRef } from "react";
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
  Search,
  CheckCircle,
  CheckCircle2
} from "lucide-react";
import { cn } from "../components/ui/utils";

const API_URL = import.meta.env.VITE_API_URL || '';

// --- Interfaces ---

interface SecurityIncident {
  id: string;
  severity: 'high' | 'medium' | 'low';
  type: string;
  source_id: string;
  timestamp: string;
  description: string;
  status: 'resolved' | 'pending';
}

interface SecurityStats {
  active_threats: number;
  blocked_attempts_24h: number;
  system_health: string;
  risk_score: number;
}

interface SecurityData {
  admin_name: string;
  stats: SecurityStats;
  recent_incidents: SecurityIncident[];
}

// --- Helper Components ---

interface ActionButtonProps {
    onClick: (e?: React.MouseEvent<HTMLButtonElement>) => void;
    children: React.ReactNode;
    variant?: 'primary' | 'secondary'
    isLoading?: boolean;
    disabled?: boolean; // Added prop
    className?: string;
    icon?: React.ElementType;
}

function ActionButton({ onClick, children, variant = 'primary', isLoading = false, disabled = false, className = '', icon: Icon }: ActionButtonProps) {
    const baseClasses = "box-border cursor-pointer flex h-[50px] items-center justify-center rounded-[8px] w-full transition-colors font-medium text-lg md:text-xl";
    const variantClasses = {
        primary: "bg-[#c8102e] hover:bg-[#b00f29] active:bg-[#a00d25] text-white shadow-lg hover:shadow-xl",
        secondary: "bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] text-black shadow-md hover:shadow-lg",
    };
    
    // Combine loading or prop disabled
    const isButtonDisabled = isLoading || disabled;

    return (
        <button 
            onClick={onClick} 
            className={cn(
                baseClasses, 
                variantClasses[variant], 
                isButtonDisabled ? 'opacity-75 cursor-not-allowed' : '', 
                className
            )}
            disabled={isButtonDisabled}
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

// Toggle Button: Handles "Mark Safe" (if pending) OR "Escalate to Threat" (if resolved)
interface SecurityActionToggleProps {
    status: 'resolved' | 'pending';
    onClick: () => void;
    isLoading?: boolean;     // Is this specific button loading?
    isDisabled?: boolean;    // Is the UI blocked globally?
}

function SecurityActionToggle({ status, onClick, isLoading, isDisabled }: SecurityActionToggleProps) {
    const [showTooltip, setShowTooltip] = useState(false);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    const isPending = status === 'pending';

    const handleMouseEnter = () => {
        if (isDisabled || isLoading) return; // No tooltip if disabled
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => setShowTooltip(true), 600);
    };

    const handleMouseLeave = () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        setShowTooltip(false);
    };

    useEffect(() => {
        return () => {
            if (timerRef.current) clearTimeout(timerRef.current);
        };
    }, []);

    return (
        <div className="relative flex items-center">
            <button
                onClick={onClick}
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
                disabled={isDisabled || isLoading}
                className={cn(
                    "p-2 rounded-full transition-all duration-200 border shadow-sm",
                    isPending 
                        ? "bg-gray-50 border-gray-200 text-gray-400 hover:bg-green-50 hover:text-green-600 hover:border-green-200 hover:scale-105" 
                        : "bg-green-50 border-green-200 text-green-600 hover:bg-red-50 hover:text-red-600 hover:border-red-200 hover:scale-105",
                    (isDisabled || isLoading) && "opacity-50 cursor-not-allowed transform-none hover:scale-100 hover:bg-gray-50 hover:text-gray-400 hover:border-gray-200"
                )}
            >
                {isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
                ) : isPending ? (
                    <ShieldCheck className="w-5 h-5" /> 
                ) : (
                    <ShieldAlert className="w-5 h-5" /> 
                )}
            </button>

            {showTooltip && !isDisabled && !isLoading && (
                <div className="absolute right-full mr-3 top-1/2 -translate-y-1/2 w-48 bg-gray-800 text-white text-xs rounded-md py-1.5 px-3 z-50 animate-in fade-in zoom-in-95 duration-200 shadow-xl">
                    <div className="absolute right-[-4px] top-1/2 -translate-y-1/2 w-2 h-2 bg-gray-800 rotate-45"></div>
                    <p className="font-medium relative z-10 text-center">
                        {isPending 
                            ? "Mark as False Positive (Safe)" 
                            : "Escalate to Active Threat"}
                    </p>
                </div>
            )}
        </div>
    );
}

// Review Button: Mark as Reviewed (Only appears if Pending)
interface ReviewButtonProps {
    onClick: () => void;
    isLoading?: boolean;
    isDisabled?: boolean;
}

function ReviewButton({ onClick, isLoading, isDisabled }: ReviewButtonProps) {
    const [showTooltip, setShowTooltip] = useState(false);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    const handleMouseEnter = () => {
        if (isDisabled || isLoading) return;
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => setShowTooltip(true), 600);
    };
    
    const handleMouseLeave = () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        setShowTooltip(false);
    };

    useEffect(() => {
        return () => {
            if (timerRef.current) clearTimeout(timerRef.current);
        };
    }, []);

    return (
        <div className="relative flex items-center">
            <button
                onClick={onClick}
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
                disabled={isDisabled || isLoading}
                className={cn(
                    "p-2 rounded-full transition-all duration-200 border shadow-sm bg-gray-50 border-gray-200 text-gray-400 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 hover:scale-105",
                    (isDisabled || isLoading) && "opacity-50 cursor-not-allowed transform-none hover:bg-gray-50 hover:text-gray-400 hover:border-gray-200"
                )}
            >
                {isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                ) : (
                    <CheckCircle className="w-5 h-5" />
                )}
            </button>

            {showTooltip && !isDisabled && !isLoading && (
                <div className="absolute right-full mr-3 top-1/2 -translate-y-1/2 w-48 bg-gray-800 text-white text-xs rounded-md py-1.5 px-3 z-50 animate-in fade-in zoom-in-95 duration-200 shadow-xl">
                    <div className="absolute right-[-4px] top-1/2 -translate-y-1/2 w-2 h-2 bg-gray-800 rotate-45"></div>
                    <p className="font-medium relative z-10 text-center">
                        Mark as Reviewed
                    </p>
                </div>
            )}
        </div>
    );
}

// --- Main Component ---

export default function FrameSecurity() {
  const navigate = useNavigate();
  const [data, setData] = useState<SecurityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingDots, setLoadingDots] = useState("");
  // Track which incident is currently being updated to show spinner
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

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

  const fetchSecurityData = useCallback(async (isInitialLoad = false) => {
    const token = getToken();
    if (!token) {
        handleLogout();
        return;
    }
    
    // Only show full page loader on initial load
    if (isInitialLoad) setLoading(true);
    
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
    } finally {
        if (isInitialLoad) setLoading(false);
    }
  }, [handleLogout]);

  useEffect(() => {
    fetchSecurityData(true);
  }, [fetchSecurityData]);

  useEffect(() => {
    if (!loading) return;

    const interval = setInterval(() => {
        setLoadingDots((prev) => (prev.length >= 3 ? "" : prev + "."));
    }, 400);

    return () => clearInterval(interval);
  }, [loading]);

  // --- ACTIONS LOGIC ---

  // Handle Threat Toggle (Reliable)
  const handleToggleThreat = async (incident: SecurityIncident) => {
    if (actionLoadingId !== null) return; // Prevent double clicks
    const token = getToken();
    if (!token) return;

    setActionLoadingId(incident.id); // Start loading spinner on button

    try {
        const response = await fetch(`${API_URL}/api/admin/log/${incident.id}/toggle-threat`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            // RELIABLE: Re-fetch data from server to ensure stats match DB exactly
            await fetchSecurityData(false);
        } else {
            console.error("Failed to toggle threat status");
        }
    } catch (error) {
        console.error("Error toggling threat:", error);
    } finally {
        setActionLoadingId(null); // Stop loading regardless of outcome
    }
  };

  // Handle Review Toggle (Reliable)
  const handleMarkReviewed = async (incident: SecurityIncident) => {
    if (actionLoadingId !== null) return; // Prevent double clicks
    const token = getToken();
    if (!token) return;

    setActionLoadingId(incident.id);

    try {
        const response = await fetch(`${API_URL}/api/admin/log/${incident.id}/review`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            await fetchSecurityData(false);
        } else {
            console.error("Failed to mark reviewed");
        }
    } catch (error) {
        console.error("Error marking reviewed:", error);
    } finally {
        setActionLoadingId(null);
    }
  };


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
            {/* Header Section */}
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
                                    <p className="text-gray-500 text-sm font-medium">Blocked attempts (24h)</p>
                                    <p className="text-3xl font-bold text-gray-800 mt-1">{data?.stats.blocked_attempts_24h}</p>
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

                        {/* Recent Incidents Table */}
                        <div className="w-full mb-12">
                            <h3 className="text-xl md:text-2xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
                                Recent Activity & Alerts
                            </h3>
                            <div className="bg-white border border-gray-200 rounded-xl overflow-visible shadow-sm">
                                {data?.recent_incidents && data.recent_incidents.length > 0 ? (
                                    <div className="divide-y divide-gray-100">
                                        {data.recent_incidents.map((incident) => (
                                            <div key={incident.id} className={cn(
                                                "p-4 md:p-5 flex flex-col md:flex-row md:items-center justify-between transition-colors",
                                                incident.status === 'pending' ? "bg-red-50/30 hover:bg-red-50/60" : "hover:bg-gray-50"
                                            )}>
                                                <div className="flex flex-col gap-1 mb-3 md:mb-0">
                                                    <div className="flex items-center gap-3">
                                                        <span className={cn("px-2 py-1 rounded-md text-xs font-bold uppercase border", getSeverityColor(incident.severity))}>
                                                            {incident.severity}
                                                        </span>
                                                        
                                                        <span className={cn(
                                                            "font-medium", 
                                                            incident.status === 'pending' ? "text-red-900" : "text-gray-700"
                                                        )}>
                                                            {incident.type}
                                                        </span>
                                                        
                                                        {incident.status === 'pending' && (
                                                            <span className="flex items-center text-xs font-bold text-red-600 bg-red-100 px-2 py-0.5 rounded-full animate-pulse">
                                                                <AlertTriangle className="w-3 h-3 mr-1" /> Action Required
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="text-sm text-gray-500 flex flex-wrap gap-x-4 gap-y-1 mt-1">
                                                        <span>User: <span className="font-mono text-gray-700">{incident.source_id}</span></span>
                                                        <span className="hidden sm:inline">•</span>
                                                        <span>{incident.timestamp}</span>
                                                        {incident.description !== incident.type && (
                                                            <>
                                                                <span className="hidden sm:inline">•</span>
                                                                <span className="italic text-gray-400">{incident.description}</span>
                                                            </>
                                                        )}
                                                    </div>
                                                </div>
                                                
                                                {/* ACTIONS COLUMN */}
                                                <div className="flex items-center gap-3 pl-0 md:pl-4">
                                                    
                                                    {/* Button 1: Mark as Reviewed (Only if Pending) */}
                                                    {incident.status === 'pending' && (
                                                        <ReviewButton 
                                                            onClick={() => handleMarkReviewed(incident)}
                                                            isLoading={actionLoadingId === incident.id}
                                                            isDisabled={actionLoadingId !== null}
                                                        />
                                                    )}

                                                    {/* Separator if two buttons */}
                                                    {incident.status === 'pending' && <div className="h-6 w-px bg-gray-300"></div>}

                                                    {/* Button 2: Toggle Classification Safe/Threat */}
                                                    <SecurityActionToggle 
                                                        status={incident.status} 
                                                        onClick={() => handleToggleThreat(incident)}
                                                        isLoading={actionLoadingId === incident.id}
                                                        isDisabled={actionLoadingId !== null}
                                                    />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="p-8 text-center text-gray-500">No recent incidents found.</div>
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

// Simple Icon component for the card
function BanIcon({ className }: { className?: string }) {
    return (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
            <circle cx="12" cy="12" r="10" />
            <path d="m4.9 4.9 14.2 14.2" />
        </svg>
    )
}