import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, UserCircle, Mail, Shield, Calendar, Ban, CheckCircle2, Fingerprint, Loader2 } from "lucide-react";
import LogTable, { LogEntry } from "../components/LogTable";

const API_URL = import.meta.env.VITE_API_URL || '';

// --- TypeScript Data Interfaces ---
interface UserProfileData {
    id: string;
    name: string;
    email: string;
    role: string;
    registered_at: string;
    is_blocked: boolean;
    logs: LogEntry[];
}

export default function FrameUserProfile() {
    const navigate = useNavigate();
    const { id: urlUserId } = useParams(); 
    
    // Component State Definitions
    const [data, setData] = useState<UserProfileData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const getToken = () => localStorage.getItem('token');
    
    // Determine context: Is the user viewing their own profile or auditing another user?
    const isMyProfile = !urlUserId;
    
    // Security Context Verification
    const isAdmin = localStorage.getItem('role') === 'Admin';

    // Fetches user identity and access history using AbortController for lifecycle safety
    const fetchProfile = useCallback(async (signal?: AbortSignal) => {
        setLoading(true);
        const token = getToken();
        try {
            // Dynamic endpoint resolution based on routing context
            const endpoint = isMyProfile ? '/api/profile' : `/api/admin/user/${urlUserId}`;
            const response = await fetch(`${API_URL}${endpoint}`, {
                headers: { 'Authorization': `Bearer ${token}` },
                signal
            });
            
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(`Error ${response.status}: ${errText}`);
            }
            const jsonData = await response.json();
            
            // Validate that the component remains mounted before committing state updates
            if (!signal?.aborted) {
                setData(jsonData);
            }
        } catch (err: any) {
            // Silently swallow intentional aborts to preserve console cleanliness
            if (err.name === 'AbortError') return;
            
            if (!signal?.aborted) {
                console.error("Profile Data Retrieval Error:", err);
                setError(err.message);
            }
        } finally {
            if (!signal?.aborted) {
                setLoading(false);
            }
        }
    }, [urlUserId, isMyProfile]);

    // Triggers network request upon component initialization
    useEffect(() => {
        document.title = isMyProfile ? "AIloQR - My Profile" : "AIloQR - User Details";
        
        const controller = new AbortController();
        fetchProfile(controller.signal);
        
        // Cleanup function inherently cancels pending requests if user navigates away rapidly
        return () => controller.abort();
    }, [fetchProfile, isMyProfile]);

    return (
        <div className="fixed inset-0 flex flex-col w-full bg-background overflow-hidden">
            
            {/* Viewport Header */}
            <div className="shrink-0 bg-background pt-6 md:pt-8 w-full z-40">
                <div className="w-full mx-auto px-4 sm:px-6 lg:px-10">
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        <button 
                            onClick={() => navigate(-1)} 
                            className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors"
                        >
                            <ArrowLeft className="w-6 h-6 text-black" />
                        </button>
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center">
                            {isMyProfile ? "My Profile" : "User Details"}
                        </h1>
                    </div>
                     <div className="border-b border-[#e6e6e6]"></div>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 min-h-0 w-full flex flex-col gap-6 px-4 sm:px-6 lg:px-10 pb-6 pt-4">
                
                {loading ? (
                    <div className="flex flex-col items-center justify-center h-full"><Loader2 className="w-10 h-10 animate-spin text-[#c8102e]" /></div>
                ) : error || !data ? (
                    <div className="bg-white rounded-xl border border-red-200 p-10 text-center text-red-500 font-medium shadow-sm">
                        {error || "Profile validation failed or user not found."}
                    </div>
                ) : (
                    <>
                        {/* Identity & Status Overview Card */}
                        <div className="shrink-0 bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6 animate-in fade-in duration-500">
                            <div className="flex items-center gap-5">
                                <div className="hidden md:flex h-16 w-16 bg-gray-100 rounded-full items-center justify-center border border-gray-200">
                                    <UserCircle className="h-8 w-8 text-gray-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-gray-900">{data.name}</h2>
                                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-2 text-sm text-gray-600">
                                        <span className="flex items-center gap-1.5"><Mail className="w-4 h-4 text-gray-400"/> {data.email}</span>
                                        <span className="flex items-center gap-1.5"><Fingerprint className="w-4 h-4 text-gray-400"/> {data.id}</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div className="flex flex-col md:items-end gap-3">
                                <div className="flex items-center gap-3">
                                    {/* Role Badge */}
                                    <span className="flex items-center gap-1.5 bg-gray-100 border border-gray-200 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-700">
                                        <Shield className="w-4 h-4 text-gray-500" /> {data.role}
                                    </span>
                                    {/* Access Clearance Status Badge */}
                                    {data.is_blocked ? (
                                        <span className="flex items-center gap-1.5 bg-red-100 border border-red-200 px-3 py-1.5 rounded-lg text-sm font-bold text-red-700">
                                            <Ban className="w-4 h-4" /> Blocked
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1.5 bg-green-100 border border-green-200 px-3 py-1.5 rounded-lg text-sm font-bold text-green-700">
                                            <CheckCircle2 className="w-4 h-4" /> Active
                                        </span>
                                    )}
                                </div>
                                <div className="flex items-center gap-1.5 text-sm text-gray-500">
                                    <Calendar className="w-4 h-4" /> Registered: {data.registered_at.split(' ')[0]}
                                </div>
                            </div>
                        </div>

                        <h3 className="shrink-0 text-xl font-semibold text-gray-800 px-1">Access History</h3>

                        {/* Integration of the modular LogTable component passing authorization context */}
                        <div className="flex-1 min-h-0 relative animate-in fade-in duration-500">
                            <LogTable 
                                logs={data.logs} 
                                loading={false} 
                                emptyMessage="No access logs found for this entity."
                                isAdmin={isAdmin} 
                            />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}