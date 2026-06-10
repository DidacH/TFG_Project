import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { 
  Loader2, ArrowLeft, UserCircle, Search, Download, 
  ShieldAlert, ShieldCheck, AlertTriangle, Sparkles, FileCheck, CheckCircle
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
  is_ai?: boolean;
  is_threat: boolean;
}

// --- Security Action Buttons ---
function SecurityActionToggle({ status, isThreat, onClick, isLoading, isDisabled }: any) {
    const isPending = status === 'pending';
    return (
        <button
            onClick={onClick}
            disabled={isLoading || isDisabled}
            title={isPending ? "Mark as False Positive" : isThreat ? "Downgrade" : "Escalate"}
            className={cn(
                "p-2 rounded-full transition-all duration-200 border shadow-sm",
                isPending ? "bg-gray-50 border-gray-200 text-gray-400 hover:bg-green-50 hover:text-green-600 hover:border-green-200" :
                isThreat ? "bg-white border-gray-200 text-gray-400 hover:bg-green-50 hover:text-green-600 hover:border-green-200" :
                "bg-white border-gray-200 text-gray-400 hover:bg-red-50 hover:text-red-600 hover:border-red-200",
                (isLoading || isDisabled) && "opacity-50 cursor-not-allowed transform-none"
            )}
        >
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin text-gray-500" /> : 
             isPending ? <ShieldCheck className="w-5 h-5" /> : <ShieldAlert className="w-5 h-5" />}
        </button>
    );
}

function ReviewButton({ onClick, isLoading, isDisabled }: any) {
    return (
        <button
            onClick={onClick}
            disabled={isLoading || isDisabled}
            title="Mark as Reviewed"
            className={cn(
                "p-2 rounded-full transition-all duration-200 border shadow-sm bg-gray-50 border-gray-200 text-gray-400 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200",
                (isLoading || isDisabled) && "opacity-50 cursor-not-allowed transform-none"
            )}
        >
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin text-blue-500" /> : <FileCheck className="w-5 h-5" />}
        </button>
    );
}

// --- Main Component ---
export default function FrameAuditLogs() {
    const navigate = useNavigate();
    const [incidents, setIncidents] = useState<SecurityIncident[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
    
    // Toast notification state
    const [toastMessage, setToastMessage] = useState<string | null>(null);

    // Filters state
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('ALL');

    const getToken = () => localStorage.getItem('token');

    // Global loading state to disable interactions when an action is processing
    const isGlobalLoading = actionLoadingId !== null;

    // Fetch logs from backend
    const fetchAuditLogs = useCallback(async () => {
        setLoading(true);
        const token = getToken();
        try {
            const response = await fetch(`${API_URL}/api/admin/audit-logs`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(`Error ${response.status}: ${errText}`);
            }
            const data = await response.json();
            setIncidents(data);
        } catch (err: any) {
            console.error("Full Audit Logs Error:", err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        document.title = "AIloQR - Audit Logs";
        fetchAuditLogs();
    }, [fetchAuditLogs]);

    // Filtering logic
    const filteredIncidents = incidents.filter(incident => {
        const matchesSearch = incident.source_id.toLowerCase().includes(searchTerm.toLowerCase()) || 
                              incident.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
                              incident.description.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesStatus = statusFilter === 'ALL' ? true :
                              statusFilter === 'PENDING' ? incident.status === 'pending' : 
                              incident.status === 'resolved';
        return matchesSearch && matchesStatus;
    });

    // Click to Copy with Toast logic
    const copyToClipboard = (text: string) => {
        if (!text || isGlobalLoading) return;
        navigator.clipboard.writeText(text);
        
        setToastMessage(`User ID copied: ${text.substring(0, 8)}...`);
        
        setTimeout(() => {
            setToastMessage(null);
        }, 2500);
    };

    // Client-side CSV Export Logic
    const handleDownloadFilteredCSV = () => {
        if (isGlobalLoading) return;
        try {
            const headers = ['ID', 'Severity', 'Type', 'User ID', 'Timestamp', 'Description', 'Status', 'Is AI', 'Is Threat'];
            const csvRows = [];
            csvRows.push(headers.join(';'));
            
            for (const incident of filteredIncidents) {
                const row = [
                    incident.id,
                    incident.severity,
                    incident.type,
                    incident.source_id,
                    incident.timestamp,
                    incident.description,
                    incident.status,
                    incident.is_ai ? 'Yes' : 'No',
                    incident.is_threat ? 'Yes' : 'No'
                ];
                
                const escapedRow = row.map(val => {
                    const strVal = String(val || '');
                    return `"${strVal.replace(/"/g, '""')}"`;
                });
                
                csvRows.push(escapedRow.join(';'));
            }

            const csvString = csvRows.join('\n');
            const blob = new Blob(['\uFEFF' + csvString], { type: 'text/csv;charset=utf-8;' });
            const url = window.URL.createObjectURL(blob);
            
            const dateStr = new Date().toISOString().split('T')[0];
            const fileName = `audit_logs_${dateStr}.csv`;

            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error("Error generating CSV:", error);
            alert("Failed to generate CSV.");
        }
    };

    // --- Database Actions ---
    const handleToggleThreat = async (incident: SecurityIncident) => {
        if (isGlobalLoading) return;
        setActionLoadingId(incident.id);
        const token = getToken();
        let action = incident.status === 'resolved' ? (incident.is_threat ? 'resolve' : 'escalate') : 'resolve';
        try {
            await fetch(`${API_URL}/api/admin/log/${incident.id}/toggle-threat`, { 
                method: 'POST', 
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ action }) 
            });
            await fetchAuditLogs();
        } catch (error) {
            alert("Failed to update status.");
        } finally { setActionLoadingId(null); }
    };

    const handleMarkReviewed = async (incident: SecurityIncident) => {
        if (isGlobalLoading) return;
        setActionLoadingId(incident.id);
        const token = getToken();
        try {
            await fetch(`${API_URL}/api/admin/log/${incident.id}/review`, { 
                method: 'POST', headers: { 'Authorization': `Bearer ${token}` } 
            });
            await fetchAuditLogs();
        } catch (error) {
            alert("Failed to mark as reviewed.");
        } finally { setActionLoadingId(null); }
    };

    const getSeverityColor = (severity: string) => {
        switch (severity) {
          case 'high': return 'text-red-600 bg-red-50 border-red-200';
          case 'medium': return 'text-orange-600 bg-orange-50 border-orange-200';
          case 'low': return 'text-blue-600 bg-blue-50 border-blue-200';
          default: return 'text-gray-600 bg-gray-50 border-gray-200';
        }
    };

    return (
        // MAIN CONTAINER: fixed inset-0 completely locks the screen from scrolling
        <div className="fixed inset-0 flex flex-col w-full bg-background overflow-hidden">
            
            {/* Header (No scroll) */}
            <div className="shrink-0 bg-background pt-6 md:pt-8 w-full z-40">
                <div className="w-full mx-auto px-4 sm:px-6 lg:px-10">
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        <button 
                            onClick={() => navigate('/security')} 
                            disabled={isGlobalLoading}
                            className={cn(
                                "absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors",
                                isGlobalLoading && "opacity-50 cursor-not-allowed"
                            )}
                        >
                            <ArrowLeft className="w-6 h-6 text-black" />
                        </button>
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center">Audit Logs</h1>
                        <button 
                            onClick={() => navigate('/profile')} 
                            disabled={isGlobalLoading}
                            className={cn(
                                "absolute right-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors",
                                isGlobalLoading && "opacity-50 cursor-not-allowed"
                            )}
                        >
                             <UserCircle className="w-6 h-6 text-black" />
                        </button>
                    </div>
                     <div className="border-b border-[#e6e6e6]"></div>
                </div>
            </div>

            {/* Central Flex Zone */}
            <div className="flex-1 min-h-0 w-full flex flex-col gap-4 px-4 sm:px-6 lg:px-10 pb-6 pt-4">
                
                {/* Toolbar */}
                <div className="shrink-0 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
                    <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
                        {/* Search Input */}
                        <div className="relative w-full sm:w-72">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                            <input 
                                type="text" 
                                placeholder="Search ID, reason, code..." 
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                disabled={isGlobalLoading}
                                className={cn(
                                    "w-full pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:border-[#c8102e] transition-colors",
                                    isGlobalLoading && "opacity-60 cursor-not-allowed"
                                )}
                            />
                        </div>
                        <select 
                            value={statusFilter} 
                            onChange={(e) => setStatusFilter(e.target.value)}
                            disabled={isGlobalLoading}
                            className={cn(
                                "w-full sm:w-auto px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:border-[#c8102e] cursor-pointer transition-colors",
                                isGlobalLoading && "opacity-60 cursor-not-allowed"
                            )}
                        >
                            <option value="ALL">All Incidents</option>
                            <option value="PENDING">Pending Action</option>
                            <option value="RESOLVED">Resolved / Safe</option>
                        </select>
                    </div>
                    
                    <button 
                        onClick={handleDownloadFilteredCSV}
                        disabled={isGlobalLoading}
                        className={cn(
                            "flex items-center justify-center gap-2 px-4 py-2 bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] text-black font-medium rounded-lg transition-colors w-full md:w-auto",
                            isGlobalLoading && "opacity-50 cursor-not-allowed"
                        )}
                    >
                        <Download className="w-5 h-5" />
                        Export Displayed Logs
                    </button>
                </div>

                {/* LIST CONTAINER: overflow-y-auto restricted to this div */}
                <div className="flex-1 min-h-0 overflow-y-auto bg-white rounded-xl border border-gray-200 shadow-sm relative">
                    {loading ? (
                        <div className="flex justify-center items-center h-full min-h-[200px]"><Loader2 className="w-10 h-10 animate-spin text-[#c8102e]" /></div>
                    ) : error ? (
                        <div className="text-red-500 text-center p-10 font-medium">{error}</div>
                    ) : filteredIncidents.length > 0 ? (
                        <div className="divide-y divide-gray-100">
                            {filteredIncidents.map((incident) => (
                                <div 
                                    key={incident.id} 
                                    className={cn(
                                        "p-4 flex flex-col md:flex-row md:items-center justify-between transition-colors", 
                                        incident.status === 'pending'
                                            ? incident.is_ai ? "bg-indigo-50" : "bg-red-50"
                                            : "bg-white hover:bg-gray-50 opacity-80"
                                    )}
                                >
                                    <div className="flex flex-col gap-1 mb-3 md:mb-0">
                                        <div className="flex items-center gap-3">
                                            <span className={cn("px-2 py-1 rounded-md text-xs font-bold uppercase border", getSeverityColor(incident.severity))}>
                                                {incident.severity}
                                            </span>
                                            <span className={cn("font-medium", incident.status === 'pending' ? "text-red-900" : "text-gray-700")}>
                                                {incident.type}
                                            </span>
                                            {incident.status === 'pending' ? (
                                                incident.is_ai ? (
                                                    <span className="flex items-center text-xs font-bold text-indigo-600 bg-indigo-100 px-2 py-0.5 rounded-full border border-indigo-200"><Sparkles className="w-3 h-3 mr-1" /> AI Suspicion</span>
                                                ) : (
                                                    <span className="flex items-center text-xs font-bold text-red-600 bg-red-100 px-2 py-0.5 rounded-full"><AlertTriangle className="w-3 h-3 mr-1" /> Action Required</span>
                                                )
                                            ) : (
                                                incident.is_threat ? (
                                                    <span className="flex items-center text-xs font-bold text-gray-600 bg-gray-100 px-2 py-0.5 rounded-full border border-gray-200"><FileCheck className="w-3 h-3 mr-1" /> Reviewed Threat</span>
                                                ) : (
                                                    <span className="flex items-center text-xs font-bold text-green-700 bg-green-100 px-2 py-0.5 rounded-full border border-green-200"><ShieldCheck className="w-3 h-3 mr-1" /> False Positive</span>
                                                )
                                            )}
                                        </div>
                                        <div className="text-sm text-gray-500 flex flex-wrap gap-x-4 gap-y-1 mt-1 pl-1">
                                            <span>User: <span 
                                                className={cn(
                                                    "font-mono text-gray-700 transition-colors",
                                                    !isGlobalLoading ? "cursor-pointer hover:text-blue-600" : "opacity-70"
                                                )}
                                                title={!isGlobalLoading ? "Click to copy ID" : undefined} 
                                                onClick={() => copyToClipboard(incident.source_id)}
                                            >
                                                {incident.source_id}
                                            </span></span>
                                            <span className="hidden sm:inline">•</span>
                                            <span>{incident.timestamp}</span>
                                            {incident.description !== incident.type && !incident.type.includes(incident.description) && (
                                                <><span className="hidden sm:inline">•</span><span className="italic text-gray-400">{incident.description}</span></>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        {incident.status === 'pending' && <ReviewButton onClick={() => handleMarkReviewed(incident)} isLoading={actionLoadingId === incident.id} isDisabled={isGlobalLoading} />}
                                        {incident.status === 'pending' && <div className="h-6 w-px bg-gray-300"></div>}
                                        <SecurityActionToggle status={incident.status} isThreat={incident.is_threat} onClick={() => handleToggleThreat(incident)} isLoading={actionLoadingId === incident.id} isDisabled={isGlobalLoading} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="p-10 text-center text-gray-500 font-medium h-full flex items-center justify-center">No incidents found matching "{searchTerm}".</div>
                    )}
                </div>
            </div>

            {/* FLOATING TOAST NOTIFICATION */}
            {toastMessage && (
                <div className="fixed bottom-8 right-8 z-50 bg-gray-900 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3 animate-in fade-in slide-in-from-bottom-4 duration-300">
                    <CheckCircle className="w-5 h-5 text-green-400" />
                    <span className="font-medium text-sm">{toastMessage}</span>
                </div>
            )}
        </div>
    );
}