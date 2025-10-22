import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, RefreshCw, Clock, UserCircle } from "lucide-react";
import { cn } from "../components/ui/utils";

const API_URL = import.meta.env.VITE_API_URL || '';
const QR_REFRESH_INTERVAL = 30; //The interval in seconds to refresh the QR code

interface DashboardData {
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
}

function ActionButton({ onClick, children, variant = 'primary', isLoading = false, className = '' }: ActionButtonProps) {
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
            {isLoading ? <Loader2 className="animate-spin h-6 w-6" /> : children}
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
  const [showHistory, setShowHistory] = useState(false);

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
  const refreshQr = useCallback(async (isInitialLoad: boolean = false) => {
    if (!getToken()) {
        handleLogout();
        return;
    }
    try {
        //Use the correct API endpoint based on whether it is initial load or just QR refresh
        const endpoint = isInitialLoad ? '/api/dashboard-data' : '/api/refresh-qr'; 
        
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
        if (isInitialLoad) {
            setData(json);
            //Use the initial remaining time from the server for the first countdown
            setRemainingTime(json.remaining); 
        } else {
            //For refresh, only update qr_base64 and reset countdown
            setData(prev => prev ? ({ ...prev, qr_base64: json.qr_base64 }) : null);
            setRemainingTime(QR_REFRESH_INTERVAL);
        }
        setError(null);
    } catch (err: any) {
        console.error(`Error ${isInitialLoad ? 'loading' : 'refreshing'} data:`, err);
        setError(err.message);
    } finally {
        if (isInitialLoad) setLoading(false);
    }
  }, [handleLogout]);


  //Countdown timer effect
  useEffect(() => {
    if (loading || error || !data) return; //Don't start timer if loading, error, or data missing

    const timer = setInterval(() => {
        setRemainingTime(prevTime => {
            if (prevTime <= 1) {
                //Time's up, refresh QR
                refreshQr(false);
                return QR_REFRESH_INTERVAL;
            }
            return prevTime - 1;
        });
    }, 1000);

    return () => clearInterval(timer); //Cleanup on unmount or dependency change
  }, [loading, error, data, refreshQr]);


  //Initial data check and fetch on mount
  useEffect(() => {
    const token = getToken();
    if (!token) {
        handleLogout();
        return;
    }
    refreshQr(true);
    //The dependency array ensures this runs once after initial mount
  }, [refreshQr, handleLogout]);


  //Loading and Error States
  if (loading) {
    return (
        <div className="w-full min-h-screen flex items-center justify-center bg-gray-100 p-4">
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
            <div className="fixed top-0 left-0 right-0 z-40 bg-background pt-6 md:pt-8 shadow-sm">
                {/*Container for alignment & max-width */}
                <div className="w-full max-w-xs md:max-w-md mx-auto px-4">
                    {/* Inner container for Title and Button alignment */}
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        {/*Profile Button - Positioned left within the padded container */}
                        <button
                            onClick={navigateToProfile}
                            aria-label="User Profile"
                            className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] rounded-full transition-colors" //
                        >
                            <UserCircle className="w-6 h-6 md:w-7 md:h-7 text-black" /> {/* */}
                        </button>
                        {/*Header Title */}
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center">
                            Your Dashboard
                        </h1> {/* */}
                    </div>
                     {/* Separator */}
                     <div className="border-b border-[#e6e6e6]"></div>
                </div>
            </div>

            {/*Main Content Area */}
            {/* Added px-4 here to match header padding */}
            <div className="flex-grow w-full flex flex-col items-center gap-6 md:gap-8 px-4 pb-8 pt-28 md:pt-32"> {/* */}

                {/*Welcome Message */}
                <h2 className="text-2xl md:text-3xl font-semibold text-black text-center mt-4 md:mt-6">
                    Welcome, <span className="text-[#c8102e]">{name}</span>!
                </h2> {/* */}

                {/*QR Code Section */}
                <div className="w-full flex flex-col items-center gap-4">
                    <h3 className="text-xl md:text-2xl font-semibold text-gray-800 flex items-center gap-2">
                        Your QR Code
                    </h3> {/* */}

                    {/*Display QR code image or a loader if not available*/}
                    {qr_base64 ? (
                        <img
                            src={`data:image/png;base64,${qr_base64}`} //
                            alt="User QR Code"
                            className="w-[220px] h-[220px] md:w-[250px] md:h-[250px] border-4 border-gray-200 rounded-lg p-1 shadow-md bg-white" //
                        />
                    ) : (
                        <div className="w-[220px] h-[220px] md:w-[250px] md:h-[250px] flex items-center justify-center bg-gray-100 rounded-lg">
                            <Loader2 className="h-8 w-8 animate-spin text-[#c8102e]" /> {/* */}
                        </div>
                    )}

                    {/*QR Refresh Timer and Manual Refresh Button*/}
                    <div className="flex flex-col items-center gap-2 pt-2 w-full">
                        <div className="text-base md:text-lg font-medium text-black flex items-center justify-center gap-1.5">
                            <Clock size={18} className="text-gray-500" /> {/* */}
                            <span className="text-gray-600">Refreshes in</span>
                            <span className="font-bold text-[#c8102e]">{remainingTime}</span> {/* */}
                            <span className="text-gray-600">seconds</span>
                        </div>
                        {/*Manual refresh button*/}
                        <button
                            onClick={() => refreshQr(false)} //
                            className="text-sm md:text-base font-medium text-gray-600 hover:text-[#c8102e] transition-colors flex items-center gap-1 mt-1"
                            aria-label="Refresh QR Code Manually"
                        >
                            <RefreshCw size={16} className={remainingTime < 5 ? "animate-spin" : ""} /> {/* */}
                            Manual Refresh
                        </button>
                    </div>
                </div>

                {/* Last Access Info */}
                <div className="w-full text-center mt-4 md:mt-2">
                    <h4 className="text-lg font-semibold text-gray-800 mb-1">Last Access</h4>
                    <p className="text-base text-[#828282]">
                        {/* Display last access time or a default message */}
                        {last_access || "No access recorded yet."} {/* */}
                    </p>
                </div>

                {/* Logout Button */}
                <div className="w-full max-w-xs md:max-w-sm mt-6 md:mt-6"> {/* Container to control width */} {/* */}
                  <ActionButton onClick={handleLogout} variant="primary" className="w-full">
                    Log Out
                  </ActionButton> {/* */}
                </div>
            </div> {/* End Main Content Area */}
        </div> //End Main container
    );
}