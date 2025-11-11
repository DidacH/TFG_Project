import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, UserCircle, Users, FileText, LogOut, AlertTriangle, CheckCircle2 } from "lucide-react";
import { cn } from "../components/ui/utils";

const API_URL = import.meta.env.VITE_API_URL || '';

interface LogEntry {
  role: string;
  access_time: string;
  entry_allowed: boolean;
  area: string;
  reason: string;
}
interface UserEntry {
  name: string;
  email: string;
  role: string;
  registered_at: string;
}
//Data obtained from the admin dashboard API
interface AdminData {
  admin_name: string;
  last_3_logs: LogEntry[];
  last_3_users: UserEntry[];
}


//Action Button Component
interface ActionButtonProps {
    onClick: (e?: React.MouseEvent<HTMLButtonElement>) => void;
    children: React.ReactNode;
    variant?: 'primary' | 'secondary';
    isLoading?: boolean;
    className?: string;
    icon?: React.ElementType; //To add icons
}
function ActionButton({ onClick, children, variant = 'primary', isLoading = false, className = '', icon: Icon }: ActionButtonProps) {
    const baseClasses = "box-border cursor-pointer flex h-[50px] items-center justify-center rounded-[8px] w-full transition-colors font-medium text-lg md:text-xl";
    const variantClasses = {
        primary: "bg-[#c8102e] hover:bg-[#b00f29] active:bg-[#a00d25] text-white shadow-lg hover:shadow-xl",
        secondary: "bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] text-black shadow-md hover:shadow-lg"
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

//Component for Section Titles
function SectionTitle({ children }: { children: React.ReactNode }) {
    //Aligned text left for desktop layout
    return <h2 className="text-2xl md:text-3xl font-semibold text-black text-left">{children}</h2>;
}

//Admin Frame Component
export default function FrameAdmin() {
  const navigate = useNavigate();
  const [data, setData] = useState<AdminData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  //Get token from localStorage
  const getToken = () => localStorage.getItem('token');

  //Logout handler
  const handleLogout = useCallback(() => {
    localStorage.removeItem("token");
    navigate("/login");
  }, [navigate]);

  //Fetch admin data
  const fetchAdminData = useCallback(async () => {
    const token = getToken();
    if (!token) {
        handleLogout();
        return;
    }
    setLoading(true);
    try {
        const response = await fetch(`${API_URL}/api/admin/dashboard-data`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });

        if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
                throw new Error('Unauthorized access. Please log in as an admin.');
            }
            throw new Error('Failed to fetch admin data.');
        }
        
        const json: AdminData = await response.json();
        setData(json);
    } catch (err: any) {
        setError(err.message);
    } finally {
        setLoading(false);
    }
  }, [handleLogout]);

  //Hook to fetch data on mount
  useEffect(() => {
    fetchAdminData();
  }, [fetchAdminData]);

  //Loading Render
  if (loading) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-100 p-4">
            <Loader2 className="h-10 w-10 animate-spin text-[#c8102e]" />
            <p className="ml-4 text-gray-700 font-sans font-medium">Loading Admin Panel...</p>
        </div>
    );
  }

  //Error Render
  if (error || !data) {
    return (
        <div className="w-full min-h-screen flex flex-col items-center justify-center bg-gray-100 p-4">
            <div className="w-full max-w-sm md:max-w-md p-8 bg-white rounded-xl shadow-md text-center border border-red-300">
                <AlertTriangle className="h-12 w-12 text-red-700 mx-auto mb-4" />
                <h1 className="text-2xl font-bold text-red-700">Access Error</h1>
                <p className="mt-4 text-sm text-gray-600">{error || "Could not load admin data. You may not have permission."}</p>
                <ActionButton onClick={handleLogout} variant="primary" className="mt-8 max-w-[200px] mx-auto">
                    Log In Again
                </ActionButton>
            </div>
        </div>
    );
  }

  //Admin panel Render
  return (
        <div className="flex flex-col min-h-screen bg-background">
            {/* Header Section */}
            <div className="fixed top-0 left-0 right-0 z-40 bg-background pt-6 md:pt-8">
                {/*Container for alignment & max-width */}
                <div className="w-full mx-auto px-4 sm:px-6 lg:px-10">
                    {/* Inner container for Title and Button alignment */}
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        {/*Profile Button - Positioned left within the padded container */}
                        <button
                            onClick={() => navigate('/profile')}
                            aria-label="User Profile"
                            className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] rounded-full transition-colors"
                        >
                            <UserCircle className="w-6 h-6 md:w-7 md:h-7 text-black" />
                        </button>
                        {/*Header Title */}
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center">
                            Admin Panel
                        </h1>
                    </div>
                     {/* Separator */}
                     <div className="border-b border-[#e6e6e6]"></div>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-grow w-full flex flex-col items-center gap-10 px-4 pb-12 pt-8 md:pt-12">
                
                {/*This container centers all content and provides max width */}
                <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

                    {/* Welcome Title */}
                    <div className="w-full mb-10">
                        <SectionTitle>Welcome, <span className="text-[#c8102e]">{data.admin_name}</span>!</SectionTitle>
                    </div>

                    {/*Row 1 - Recent Activity */}
                    <div className="w-full grid grid-cols-1 lg:grid-cols-2 lg:gap-8">
                        {/* Recent Activity Column */}
                        <div className="flex flex-col gap-3">
                            <h3 className="text-xl md:text-2xl font-semibold text-gray-800">Recent Access Logs</h3>
                            {data.last_3_logs.length > 0 ? (
                                <div className="flex flex-col gap-3">
                                    {data.last_3_logs.map((log, index) => (
                                        <div key={`log-${index}`} className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm flex justify-between items-center">
                                            <div className="flex-1 overflow-hidden">
                                                <p className="font-medium text-gray-800 truncate">Area: {log.area}</p>
                                                <p className="text-gray-600">Role: {log.role}</p>
                                                <p className="text-gray-600">Reason: {log.reason}</p>
                                                <p className="text-gray-500 text-xs">{log.access_time}</p>
                                            </div>
                                            {log.entry_allowed ? (
                                                <CheckCircle2 className="h-6 w-6 text-green-600 flex-shrink-0 ml-2" />
                                            ) : (
                                                <AlertTriangle className="h-6 w-6 text-red-600 flex-shrink-0 ml-2" />
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-left text-gray-500">No recent logs.</p>
                            )}
                        </div>

                        {/* Recent Users Column */}
                        <div className="flex flex-col gap-3 mt-10 lg:mt-0">
                            <h3 className="text-xl md:text-2xl font-semibold text-gray-800">Recent Registered Users</h3>
                            {data.last_3_users.length > 0 ? (
                                <div className="flex flex-col gap-3">
                                    {data.last_3_users.map((user, index) => (
                                        <div key={`user-${index}`} className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm">
                                            <p className="font-medium text-gray-800">{user.name} ({user.role})</p>
                                            <p className="text-gray-600 truncate">{user.email}</p>
                                            <p className="text-gray-500 text-xs">Registered: {user.registered_at}</p>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-left text-gray-500">No recent users.</p>
                            )}
                        </div>
                    </div>

                    {/* # CHANGE: Row 2 - Actions */}
                    <div className="w-full mt-12">
                        <h3 className="text-xl md:text-2xl font-semibold text-gray-800 mb-4">Management</h3>
                        {/* # CHANGE: Grid for action buttons */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <ActionButton 
                                onClick={() => navigate('/admin/users')} 
                                variant="secondary" 
                                icon={Users}
                            >
                                Manage Users
                            </ActionButton>
                            <ActionButton 
                                onClick={() => navigate('/admin/logs')} 
                                variant="secondary" 
                                icon={FileText}
                            >
                                View Logs
                            </ActionButton>
                        </div>
                    </div>
                    
                    {/* Removed Downloads Section */}

                    {/* Logout Button */}
                    {/* Centered the logout button container */}
                    <div className="w-full max-w-xs md:max-w-sm mt-12 mx-auto">
                      <ActionButton onClick={handleLogout} variant="primary" icon={LogOut}>
                        Log Out
                      </ActionButton>
                    </div>

                </div>
            </div> {/* End Main Content Area */}
        </div> //End Main container
  );
}