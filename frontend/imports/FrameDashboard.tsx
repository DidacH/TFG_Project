import { useState, useEffect, useCallback, useRef} from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, RefreshCw, UserCircle, LogOut } from "lucide-react";
import { cn } from "../components/ui/utils";
import { useWebSocket } from "../context/WebSocketContext";

const API_URL = import.meta.env.VITE_API_URL || '';
const QR_REFRESH_INTERVAL = 30;

interface DashboardData {
    id: string;
    name: string;
    role: string; 
    qr_base64: string;
    remaining: number;
    last_access: string | null;
}

interface ActionButtonProps {
    onClick: () => void;
    children: React.ReactNode;
    variant?: 'primary' | 'secondary';
    isLoading?: boolean;
    className?: string;
    icon?: React.ElementType;
}

// Reusable action button component
function ActionButton({ onClick, children, variant = 'primary', isLoading = false, className = '', icon: Icon }: ActionButtonProps) {
    const baseClasses = "box-border cursor-pointer flex h-[50px] items-center justify-center rounded-[8px] w-full transition-colors font-medium";
    const variantClasses = {
        primary: "bg-[#c8102e] hover:bg-[#b00f29] active:bg-[#a00d25] text-white",
        secondary: "bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] text-black"
    };

    return (
        <button 
            onClick={onClick} 
            className={cn(baseClasses, variantClasses[variant], isLoading ? 'opacity-75 cursor-not-allowed' : 'shadow-lg hover:shadow-xl', "text-lg md:text-xl", className)}
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

export default function FrameDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDots, setLoadingDots] = useState("");
  const [error, setError] = useState<string | null>(null);
  
  // QR lifecycle state
  const [remainingTime, setRemainingTime] = useState(QR_REFRESH_INTERVAL);
  const [isManualRefreshing, setIsManualRefreshing] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false); 
  
  // Refs for tracking background intervals and stale requests
  const isRefreshingRef = useRef(false); 
  const expirationTimeRef = useRef<number | null>(null); 
  const abortControllerRef = useRef<AbortController | null>(null);
  const userIdRef = useRef<string | undefined>(data?.id);
  
  const { socket } = useWebSocket();
  const storedRole = localStorage.getItem('role');

  useEffect(() => {
    document.title = "AIloQR - Dashboard";
  }, []);

  // Loading animation effect
  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => {
        setLoadingDots((prev) => (prev.length >= 3 ? "" : prev + "."));
    }, 400);
    return () => clearInterval(interval);
  }, [loading]);

  // Cleanup pending network requests on unmount
  useEffect(() => {
      return () => {
          if (abortControllerRef.current) {
              abortControllerRef.current.abort();
          }
      };
  }, []);

  useEffect(() => { userIdRef.current = data?.id; }, [data?.id]);

  const getToken = () => localStorage.getItem('token');

  const handleLogout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    navigate("/login");
  }, [navigate]);

  // Fetches fresh QR data from the server
  const refreshQr = useCallback(async (isInitialLoad: boolean = false, fetchOnly: boolean = false) => {
    if (!getToken()) { handleLogout(); return; }
    if (isRefreshingRef.current && !isInitialLoad && !fetchOnly) return; 

    if (abortControllerRef.current) {
        abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    isRefreshingRef.current = true;
    if (!fetchOnly) setIsRefreshing(true);

    try {
        const endpoint = (isInitialLoad || fetchOnly) ? '/api/dashboard-data' : '/api/refresh-qr'; 
        const response = await fetch(`${API_URL}${endpoint}`, {
            method: 'GET',
            headers: { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
            signal: controller.signal
        });
        const json = await response.json();

        if (!response.ok) {
            if (response.status === 401) { handleLogout(); return; }
            throw new Error(json.message || "Error loading data.");
        }

        if (isInitialLoad || fetchOnly) {
            setData(json);
            if (json.remaining !== undefined) {
                setRemainingTime(json.remaining);
                expirationTimeRef.current = Date.now() + (json.remaining * 1000); 
            }
        } else {
            setData(prev => prev ? ({ ...prev, qr_base64: json.qr_base64 }) : null);
            setRemainingTime(QR_REFRESH_INTERVAL);
            expirationTimeRef.current = Date.now() + (QR_REFRESH_INTERVAL * 1000);
        }
    } catch (err: any) {
        if (err.name === 'AbortError') return;
        setError(err.message);
    } finally {
        if (abortControllerRef.current === controller) {
            isRefreshingRef.current = false;
            if (!fetchOnly) setIsRefreshing(false);
            if (isInitialLoad) setLoading(false);
        }
    }
  }, [handleLogout]);

  // Countdown timer for QR validity
  useEffect(() => {
    if (loading || error || !data || isRefreshing) return; 
    const timer = setInterval(() => {
        if (!expirationTimeRef.current) return;
        const timeDiff = expirationTimeRef.current - Date.now();
        const newRemaining = Math.max(0, Math.ceil(timeDiff / 1000));
        setRemainingTime(newRemaining);
        if (newRemaining <= 2 && !isRefreshingRef.current) refreshQr(false); 
    }, 1000);
    return () => clearInterval(timer); 
  }, [loading, error, data, isRefreshing, refreshQr]);

  // WebSocket listeners for real-time dashboard updates
  useEffect(() => {
        if (!socket) return;
        const handleUpdateData = (eventData?: any) => {
            if (!eventData?.user_id || userIdRef.current === eventData.user_id) refreshQr(false, true);
        };
        socket.on("dashboard_update", handleUpdateData);
        socket.on("connect", () => handleUpdateData());
        
        return () => {
            socket.off("dashboard_update", handleUpdateData);
            socket.off("connect", handleUpdateData);
        };
  }, [socket, refreshQr]);

  useEffect(() => { refreshQr(true); }, [refreshQr]);

  if (!loading && (error || !data)) {
    return (
        <div className="w-full min-h-screen flex flex-col items-center justify-center bg-gray-100 p-4">
            <div className="w-full max-w-sm md:max-w-md p-8 bg-white rounded-xl shadow-md text-center border border-red-300">
                <h1 className="text-3xl font-bold text-red-700">Auth Error</h1>
                <ActionButton onClick={handleLogout} variant="primary" className="mt-8 max-w-[200px] mx-auto">Log In Again</ActionButton>
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
                            onClick={() => !loading && navigate('/profile')} 
                            disabled={loading}
                            className={cn(
                                "absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 rounded-full transition-all",
                                loading ? 'bg-gray-200 opacity-50 cursor-not-allowed' : 'bg-[#eeeeee] hover:bg-[#e0e0e0]'
                            )}
                        >
                            <UserCircle className="w-6 h-6 md:w-7 md:h-7 text-black" />
                        </button>
                        
                        {(data?.role === 'Admin' || storedRole === 'Admin') ? (
                            <div className="flex bg-[#eeeeee] rounded-lg p-1 mx-auto shadow-inner">
                                <button className="px-4 py-1.5 rounded-md bg-white shadow text-sm md:text-base font-semibold text-[#c8102e] cursor-default">
                                    Dashboard
                                </button>
                                <button 
                                    onClick={() => !loading && navigate('/admin')} 
                                    disabled={loading}
                                    className={cn(
                                        "px-4 py-1.5 rounded-md text-sm md:text-base font-medium transition-all",
                                        loading ? 'opacity-50 cursor-not-allowed text-gray-400' : 'text-gray-600 hover:text-black'
                                    )}
                                >
                                    Admin Panel
                                </button>
                            </div>
                        ) : (
                            <h1 className="text-xl md:text-2xl font-semibold text-black text-center">Your Dashboard</h1>
                        )}
                    </div>
                     <div className="border-b border-[#e6e6e6]"></div>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-grow w-full flex flex-col items-center gap-6 md:gap-8 px-4 pb-8 pt-8 md:pt-12">
                {loading ? (
                    <div className="flex flex-col items-center justify-center h-[75vh] w-full">
                        <div className="relative">
                            <p className="text-gray-500 font-medium">Loading Dashboard</p>
                            <span className="absolute left-full top-0 text-gray-500 font-medium">{loadingDots}</span>
                        </div>
                    </div>
                ) : (
                    <div className="w-full flex flex-col items-center gap-6 md:gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <h2 className="text-2xl md:text-3xl font-semibold text-black text-center mt-4 md:mt-6">
                            Welcome, <span className="text-[#c8102e]">{data?.name}</span>!
                        </h2>
                        
                        <div className="w-full flex flex-col items-center gap-4">
                            <h3 className="text-xl md:text-2xl font-semibold text-gray-800">Your QR Code</h3>
                            <img src={`data:image/png;base64,${data?.qr_base64}`} alt="Access QR Code" className="w-[220px] h-[220px] md:w-[250px] md:h-[250px] border-4 border-gray-200 rounded-lg p-1 shadow-sm bg-white" />
                            <div className="flex flex-col items-center gap-2 pt-2">
                                <p className="text-base md:text-lg font-medium">Refreshes in <span className="font-bold text-[#c8102e]">{remainingTime}</span> s</p>
                                <button onClick={async () => {setIsManualRefreshing(true); await refreshQr(); setIsManualRefreshing(false);}} className="text-sm text-gray-600 flex items-center gap-1 transition-opacity hover:opacity-70">
                                    <RefreshCw size={16} className={isManualRefreshing ? "animate-spin" : ""} /> Manual Refresh
                                </button>
                            </div>
                        </div>

                        <div className="w-full text-center mt-4 md:mt-2">
                            <h4 className="text-lg font-semibold text-gray-800 mb-1">Last Access</h4>
                            <p className="text-base text-[#828282]">{data?.last_access || "No access recorded yet."}</p>
                        </div>

                        <div className="w-full max-w-xs md:max-w-sm mt-6">
                          <ActionButton onClick={handleLogout} variant="primary" icon={LogOut}>Log Out</ActionButton>
                        </div>
                    </div>
                )}
            </div> 
        </div> 
    );
}