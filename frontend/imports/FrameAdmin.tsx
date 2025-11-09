import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, UserCircle, Users, FileText, Download, LogOut, AlertTriangle, CheckCircle2 } from "lucide-react";
import { cn } from "../components/ui/utils";

const API_URL = import.meta.env.VITE_API_URL || '';

// --- Tipus de Dades (Interfícies) ---
interface LogEntry {
  user_id: string; // O name/email si ho prefereixes
  role: string;
  access_time: string;
  entry_allowed: boolean;
  area: string;
}
interface UserEntry {
  name: string;
  email: string;
  role: string;
  registered_at: string;
}
//Dades que rebrem de l'API per a aquest dashboard
interface AdminData {
  admin_name: string;
  last_3_logs: LogEntry[];
  last_3_users: UserEntry[];
}

// --- Components Reutilitzables (Adaptats de FrameDashboard) ---

//Botó d'Acció (Similar al de Login/Dashboard)
interface ActionButtonProps {
    onClick: (e?: React.MouseEvent<HTMLButtonElement>) => void;
    children: React.ReactNode;
    variant?: 'primary' | 'secondary';
    isLoading?: boolean;
    className?: string;
    icon?: React.ElementType; //Per afegir icones
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

//Component per als títols de secció
function SectionTitle({ children }: { children: React.ReactNode }) {
    return <h2 className="text-2xl md:text-3xl font-semibold text-black text-center">{children}</h2>;
}

// --- Component Principal: FrameAdmin ---

export default function FrameAdmin() {
  const navigate = useNavigate();
  const [data, setData] = useState<AdminData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<'users' | 'logs' | null>(null);

  //Obtenir token
  const getToken = () => localStorage.getItem('token');

  //Logout handler
  const handleLogout = useCallback(() => {
    localStorage.removeItem("token");
    navigate("/login");
  }, [navigate]);

  //Funció per obtenir les dades del dashboard d'admin
  const fetchAdminData = useCallback(async () => {
    const token = getToken();
    if (!token) {
        handleLogout();
        return;
    }
    setLoading(true);
    try {
        //Aquest endpoint nou l'haurem de crear a app.py
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

  //Hook per carregar les dades quan el component es munta
  useEffect(() => {
    fetchAdminData();
  }, [fetchAdminData]);

  //Funció per gestionar les descàrregues de CSV
  const handleDownload = async (type: 'users' | 'logs') => {
    setDownloading(type);
    const token = getToken();
    try {
        const response = await fetch(`${API_URL}/api/admin/${type}/download`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('Download failed');

        //Obtenir el nom del fitxer
        const filename = type === 'users' ? 'users.csv' : 'logs.csv';
        
        //Crear un link temporal per descarregar el blob
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

    } catch (err: any) {
        setError(`Failed to download ${type} CSV.`);
    } finally {
        setDownloading(null);
    }
  };

  //Renderitzat de Loading
  if (loading) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-100 p-4">
            <Loader2 className="h-10 w-10 animate-spin text-[#c8102e]" />
            <p className="ml-4 text-gray-700 font-sans font-medium">Loading Admin Panel...</p>
        </div>
    );
  }

  //Renderitzat d'Error
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

  //Renderitzat del Dashboard d'Admin
  return (
        <div className="flex flex-col min-h-screen bg-background">

            {/* Header Section (Similar a Dashboard) */}
            <div className="fixed top-0 left-0 right-0 z-40 bg-gray-50 pt-6 md:pt-8 shadow-sm px-4">
                <div className="w-full mx-auto">
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        {/* El botó de perfil d'admin pot anar a la mateixa pàgina de perfil /profile */}
                        <button
                            onClick={() => navigate('/profile')}
                            aria-label="User Profile"
                            className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] rounded-full transition-colors"
                        >
                            <UserCircle className="w-6 h-6 md:w-7 md:h-7 text-black" />
                        </button>
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center">
                            Admin Panel
                        </h1>
                    </div>
                     <div className="border-b border-[#e6e6e6]"></div>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-grow w-full flex flex-col items-center gap-6 md:gap-10 px-4 pb-8 pt-28 md:pt-32">
                <SectionTitle>Welcome, <span className="text-[#c8102e]">{data.admin_name}</span>!</SectionTitle>

                {/* Secció d'Accions */}
                <div className="w-full max-w-xs md:max-w-sm flex flex-col gap-4">
                    <SectionTitle>Management</SectionTitle>
                    <ActionButton 
                        onClick={() => navigate('/admin/users')} 
                        variant="secondary" 
                        icon={Users}
                    >
                        Manage All Users
                    </ActionButton>
                    <ActionButton 
                        onClick={() => navigate('/admin/logs')} 
                        variant="secondary" 
                        icon={FileText}
                    >
                        View Full Logs
                    </ActionButton>
                </div>

                {/* Secció de Descàrregues */}
                <div className="w-full max-w-xs md:max-w-sm flex flex-col gap-4">
                     <SectionTitle>Download Reports</SectionTitle>
                     <ActionButton 
                        onClick={() => handleDownload('users')}
                        variant="secondary"
                        icon={Download}
                        isLoading={downloading === 'users'}
                     >
                        Download Users (CSV)
                     </ActionButton>
                     <ActionButton 
                        onClick={() => handleDownload('logs')}
                        variant="secondary"
                        icon={Download}
                        isLoading={downloading === 'logs'}
                     >
                        Download Logs (CSV)
                     </ActionButton>
                </div>

                {/* Secció d'Activitat Recent */}
                <div className="w-full max-w-lg flex flex-col gap-8 mt-4">
                    <div className="flex flex-col gap-3">
                        <SectionTitle>Recent Access Logs</SectionTitle>
                        {data.last_3_logs.length > 0 ? (
                            data.last_3_logs.map((log, index) => (
                                <div key={`log-${index}`} className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm">
                                    <div className="flex justify-between items-center mb-1">
                                        <span className="font-medium text-gray-800">{log.area}</span>
                                        {log.entry_allowed ? (
                                            <CheckCircle2 className="h-5 w-5 text-green-600" />
                                        ) : (
                                            <AlertTriangle className="h-5 w-5 text-red-600" />
                                        )}
                                    </div>
                                    <p className="text-gray-600">User: {log.user_id}</p>
                                    <p className="text-gray-500 text-xs">{log.access_time}</p>
                                </div>
                            ))
                        ) : (
                            <p className="text-center text-gray-500">No recent logs.</p>
                        )}
                    </div>

                    <div className="flex flex-col gap-3">
                        <SectionTitle>Recent Registered Users</SectionTitle>
                        {data.last_3_users.length > 0 ? (
                            data.last_3_users.map((user, index) => (
                                <div key={`user-${index}`} className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm">
                                    <p className="font-medium text-gray-800">{user.name} ({user.role})</p>
                                    <p className="text-gray-600">{user.email}</p>
                                    <p className="text-gray-500 text-xs">Registered: {user.registered_at}</p>
                                </div>
                            ))
                        ) : (
                            <p className="text-center text-gray-500">No recent users.</p>
                        )}
                    </div>
                </div>

                {/* Logout Button */}
                <div className="w-full max-w-xs md:max-w-sm mt-6 md:mt-8">
                  <ActionButton onClick={handleLogout} variant="primary" icon={LogOut}>
                    Log Out
                  </ActionButton>
                </div>
            </div> {/* End Main Content Area */}
        </div> //End Main container
  );
}