import { useState, useEffect, useCallback, useRef} from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, RefreshCw, UserCircle, LogOut } from "lucide-react";
import { cn } from "../components/ui/utils";
import { useWebSocket } from "../context/WebSocketContext";

const API_URL = import.meta.env.VITE_API_URL || '';
const QR_REFRESH_INTERVAL = 30; //The interval in seconds to refresh the QR code

interface DashboardData {
    id: string;
    name: string;
    qr_base64: string;
    remaining: number; //Seconds until next refresh
    last_access: string | null;
}

//Reusable Button Component
interface ActionButtonProps {
    onClick: () => void;
    children: React.ReactNode;
    variant?: 'primary' | 'secondary';
    isLoading?: boolean;
    className?: string;
    icon?: React.ElementType;
}

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

//Dashboard Frame Component
export default function FrameDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [remainingTime, setRemainingTime] = useState(QR_REFRESH_INTERVAL);
  const [isManualRefreshing, setIsManualRefreshing] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false); //async state to indicate ongoing refresh
  const isRefreshingRef = useRef(false); //Ref to track ongoing refresh state (sychronous)
  const isInitialLoadDone = useRef(false); //Ref to track if initial load is done
  const prevQrBase64Ref = useRef<string | null | undefined>(); //Ref to store previous QR code for comparison
  const { socket } = useWebSocket();
  const userIdRef = useRef<string | undefined>(data?.id);

  useEffect(() => {
    document.title = "AIloQR - Dashboard";
  }, []);

  //Function to get JWT token
  const getToken = () => localStorage.getItem('token');

  //Logout handler
  const handleLogout = useCallback(() => {
    //Remove the authentication token
    localStorage.removeItem("token");
    //Navigate to login
    navigate("/login");
  }, [navigate]);

  //Fetch or refresh QR code data
  const refreshQr = useCallback(async (isInitialLoad: boolean = false, fetchOnly: boolean = false) => {
    if (!getToken()) {
        handleLogout();
        return;
    }

    if (isRefreshingRef.current && !isInitialLoad && !fetchOnly) return; //Prevent overlapping refreshes

    isRefreshingRef.current = true;
    if (!fetchOnly) setIsRefreshing(true);

    try {
        //Use the correct API endpoint based on whether it is initial load or just QR refresh
        const endpoint = (isInitialLoad || fetchOnly) ? '/api/dashboard-data' : '/api/refresh-qr'; 
        
        const response = await fetch(`${API_URL}${endpoint}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
        });
        const json = await response.json();

        if (!response.ok) {
            if (response.status === 401) { //Handle unauthorized token (expired or invalid)
                handleLogout();
                return;
            }
            throw new Error(json.message || `Failed to ${isInitialLoad ? 'load' : 'refresh'} dashboard data.`);
        }

        //Update state with new data. Only update the entire object on initial load.
        if (isInitialLoad || fetchOnly) {
            setData(json);
            //Use the initial remaining time from the server for the first countdown
            if (isInitialLoad) setRemainingTime(json.remaining); 
        } else {
            //For refresh, only update qr_base64
            setData(prev => prev ? ({ ...prev, qr_base64: json.qr_base64 }) : null);
        }
        setError(null);
    } catch (err: any) {
        console.error(`Error ${isInitialLoad ? 'loading' : 'refreshing'} data:`, err);
        setError(err.message);
    } finally {
        isRefreshingRef.current = false;
        if (!fetchOnly) setIsRefreshing(false);
        if (isInitialLoad) setLoading(false);
    }
  }, [handleLogout]);


  useEffect(() => {
        userIdRef.current = data?.id;
    }, [data?.id]);

    
  //Countdown timer effect
  useEffect(() => {
    if (loading || error || !data || isRefreshing) return; //Don't start timer if loading state, error state, or refreshing

    const timer = setInterval(() => {
        setRemainingTime(prevTime => {

           if (prevTime <= 0) return 0; //Prevent negative time

           if (prevTime === 2 && !isRefreshingRef.current) {
                //Time is about to run up, start refreshing the QR
                refreshQr(false); //Call refreshQr
            }

            return prevTime - 1;
        });
    }, 1000);

    return () => clearInterval(timer); //Cleanup on unmount or dependency change
  }, [loading, error, data, isRefreshing, refreshQr]);

  useEffect(() => {
    const currentQr = data?.qr_base64;
    const prevQr = prevQrBase64Ref.current;

    //If we now have a QR code, but didn't have one before (means it's the initial load)
    if (currentQr && !prevQr) {
        
        //Mark initial load as done
        isInitialLoadDone.current = true; 

        //Edge case: If remaining time is <=2, refresh immediately
        if (data.remaining <= 2 && !isRefreshingRef.current) {
            refreshQr(false);
        }
    }

    //If we have both current and previous QR codes, and they differ
    if (currentQr && prevQr && currentQr !== prevQr) {
        //reset timer
        setRemainingTime(QR_REFRESH_INTERVAL);
    }
    
    //Store the current QR for next comparison
    prevQrBase64Ref.current = currentQr;

  }, [data?.qr_base64, data?.remaining, refreshQr]);

  //WebSocket effect to listen for updates
  useEffect(() => {
        if (!socket) return;

        const handleUpdateData = (eventData?: any) => {
            const currentUserId = userIdRef.current;

            // Specific update (with user ID) - Only refresh if it matches our current user ID
            if (eventData && eventData.user_id) {
                if (currentUserId && eventData.user_id === currentUserId) {
                    console.log("✅ My access, updating dashboard...");
                    refreshQr(false, true);
                } else {
                    // This update is for another user, ignore it
                    console.log("⚠️ Received dashboard update for another user, ignoring...");
                }
            } 
            // Generic update without user ID
            else {
                console.log("🔄 Generic synchronization / Reconnect...");
                refreshQr(false, true);
            }
        };

        socket.on("dashboard_update", handleUpdateData);

        const onConnect = () => {
            handleUpdateData();
        };

        socket.on("connect", onConnect);

        if (socket.connected) {
            onConnect();
        }

        return () => {
            socket.off("dashboard_update", handleUpdateData);
            socket.off("connect", onConnect);
        };
        
    }, [socket, refreshQr]);


  //Initial data check and fetch on mount
  useEffect(() => {
    const token = getToken();
    if (!token) {
        handleLogout();
        return;
    }
    refreshQr(true);
    //The dependency array ensures this runs once after initial mount
  }, [handleLogout]);


  //Loading and Error States
  if (loading) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-100 p-4">
            <Loader2 className="h-10 w-10 animate-spin text-[#c8102e]" />
            <p className="ml-4 text-gray-700 font-sans font-medium">Loading Dashboard...</p>
        </div>
    );
  }

  if (error || !data) {
    return (
        <div className="w-full min-h-screen flex flex-col items-center justify-center bg-gray-100 p-4">
            <div className="w-full max-w-sm md:max-w-md p-8 bg-white rounded-xl shadow-md text-center border border-red-300">
                <h1 className="text-3xl font-bold text-red-700">Authentication Error</h1>
                <p className="mt-4 text-sm text-gray-600">{error || "Could not load dashboard data. Please log in again."}</p>
                <ActionButton onClick={handleLogout} variant="primary" className="mt-8 max-w-[200px] mx-auto">
                    Log In Again
                </ActionButton>
            </div>
        </div>
    );
  }
  
  //Rendering the Dashboard Content
  const { name, qr_base64, last_access } = data;

  const navigateToProfile = () => {
        navigate('/profile'); //Navigate to profile page
    };

  return (
        //Main container
        <div className="flex flex-col min-h-screen bg-background">

            {/* Header Section */}
            <div className="fixed top-0 left-0 right-0 z-40 bg-background pt-6 md:pt-8">
                {/*Container for alignment & max-width */}
                <div className="w-full mx-auto px-4 sm:px-6 lg:px-10">
                    {/* Inner container for Title and Button alignment */}
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        {/*Profile Button - Positioned left within the padded container */}
                        <button
                            onClick={navigateToProfile}
                            aria-label="User Profile"
                            className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] rounded-full transition-colors"
                        >
                            <UserCircle className="w-6 h-6 md:w-7 md:h-7 text-black" />
                        </button>
                        {/*Header Title */}
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center">
                            Your Dashboard
                        </h1>
                    </div>
                     {/* Separator */}
                     <div className="border-b border-[#e6e6e6]"></div>
                </div>
            </div>

            {/*Main Content Area */}
            {/* Added px-4 here to match header padding */}
            <div className="flex-grow w-full flex flex-col items-center gap-6 md:gap-8 px-4 pb-8 pt-8 md:pt-12">

                {/*Welcome Message */}
                <h2 className="text-2xl md:text-3xl font-semibold text-black text-center mt-4 md:mt-6">
                    Welcome, <span className="text-[#c8102e]">{name}</span>!
                </h2>

                {/*QR Code Section */}
                <div className="w-full flex flex-col items-center gap-4">
                    <h3 className="text-xl md:text-2xl font-semibold text-gray-800 flex items-center gap-2">
                        Your QR Code
                    </h3>

                    {/*Display QR code image or a loader if not available*/}
                    {qr_base64 ? (
                        <img
                            src={`data:image/png;base64,${qr_base64}`}
                            alt="User QR Code"
                            className="w-[220px] h-[220px] md:w-[250px] md:h-[250px] border-4 border-gray-200 rounded-lg p-1 shadow-sm bg-white" //
                        />
                    ) : (
                        <div className="w-[220px] h-[220px] md:w-[250px] md:h-[250px] flex items-center justify-center bg-gray-100 rounded-lg">
                            <Loader2 className="h-8 w-8 animate-spin text-[#c8102e]" />
                        </div>
                    )}

                    {/*QR Refresh Timer and Manual Refresh Button*/}
                    <div className="flex flex-col items-center gap-2 pt-2 w-full">
                        <div className="text-base md:text-lg font-medium text-black flex items-center justify-center gap-1.5">
                            <span className="text-gray-600">Refreshes in</span>
                            <span className="font-bold text-[#c8102e]">{remainingTime}</span>
                            <span className="text-gray-600">seconds</span>
                        </div>
                        {/*Manual refresh button*/}
                        <button
                            onClick={async () => {
                                //Activate animation on click
                                setIsManualRefreshing(true);
                                //Call the refresh function and reset timer
                                await refreshQr(false);
                                //Resert the countdown timer
                                setRemainingTime(QR_REFRESH_INTERVAL);
                                //Deactivate the animation on completion
                                setIsManualRefreshing(false);
                            }}
                            className="text-sm md:text-base font-medium text-gray-600 hover:text-[#c8102e] transition-colors flex items-center gap-1 mt-1"
                            aria-label="Refresh QR Code Manually"
                            disabled={isManualRefreshing || remainingTime > (QR_REFRESH_INTERVAL - 3)} //Disable button while loading and prevent spam
                        >
                            <RefreshCw size={16} className={(remainingTime < 3 || isManualRefreshing)? "animate-spin" : ""} />
                            Manual Refresh
                        </button>
                    </div>
                </div>

                {/* Last Access Info */}
                <div className="w-full text-center mt-4 md:mt-2">
                    <h4 className="text-lg font-semibold text-gray-800 mb-1">Last Access</h4>
                    <p className="text-base text-[#828282]">
                        {/* Display last access time or a default message */}
                        {last_access || "No access recorded yet."}
                    </p>
                </div>

                {/* Logout Button */}
                <div className="w-full max-w-xs md:max-w-sm mt-6 md:mt-6"> {/* Container to control width */}
                  <ActionButton onClick={handleLogout} variant="primary" className="w-full" icon={LogOut}>
                    Log Out
                  </ActionButton>
                </div>
            </div> {/* End Main Content Area */}
        </div> //End Main container
    );
}
