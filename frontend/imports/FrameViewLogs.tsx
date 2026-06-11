import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, UserCircle, Search, Download } from "lucide-react";
import LogTable, { LogEntry } from "../components/LogTable";

const API_URL = import.meta.env.VITE_API_URL || '';

export default function FrameViewLogs() {
    const navigate = useNavigate();
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filters
    const [searchTerm, setSearchTerm] = useState('');
    const [accessFilter, setAccessFilter] = useState('ALL'); // ALL, ALLOWED, DENIED

    const getToken = () => localStorage.getItem('token');

    // Fetch Logs
    const fetchLogs = useCallback(async () => {
        setLoading(true);
        const token = getToken();
        try {
            const response = await fetch(`${API_URL}/api/admin/logs`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(`Error ${response.status}: ${errText}`);
            }
            const data = await response.json();
            setLogs(data);
        } catch (err: any) {
            console.error("View Logs Error:", err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        document.title = "AIloQR - Historical Logs";
        fetchLogs();
    }, [fetchLogs]);

    // CORRECCIÓ 3: Protecció contra valors Null al filtre
    const filteredLogs = logs.filter(log => {
        const searchLower = searchTerm.toLowerCase();
        
        // Assegurem que cap variable sigui 'null' abans de fer toLowerCase()
        const matchesSearch = (log.user_id || '').toLowerCase().includes(searchLower) || 
                              (log.area || '').toLowerCase().includes(searchLower) ||
                              (log.reason || '').toLowerCase().includes(searchLower);
        
        const matchesAccess = accessFilter === 'ALL' ? true :
                              accessFilter === 'ALLOWED' ? log.entry_allowed === true : 
                              log.entry_allowed === false;
                              
        return matchesSearch && matchesAccess;
    });

    // Client-side CSV Export Logic
    const handleDownloadFilteredCSV = () => {
        try {
            const headers = ['Time', 'User ID', 'Role', 'Area', 'Access Status', 'Reason', 'Is Threat', 'Is Anomaly'];
            const csvRows = [];
            csvRows.push(headers.join(';'));
            
            for (const log of filteredLogs) {
                // CORRECCIÓ 3.1: Protecció contra valors Null a l'exportació
                const row = [
                    log.access_time?.split('.')[0] || '',
                    log.user_id || 'Unknown',
                    log.role || 'N/A',
                    log.area || 'Unknown',
                    log.entry_allowed ? 'ALLOWED' : 'DENIED',
                    log.reason || 'No reason provided',
                    log.is_threat ? 'Yes' : 'No',
                    log.is_anomaly ? 'Yes' : 'No'
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
            const fileName = `historical_logs_${dateStr}.csv`;

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

    return (
        <div className="fixed inset-0 flex flex-col w-full bg-background overflow-hidden">
            
            {/* Header */}
            <div className="shrink-0 bg-background pt-6 md:pt-8 w-full z-40">
                <div className="w-full mx-auto px-4 sm:px-6 lg:px-10">
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        <button onClick={() => navigate('/admin')} className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors">
                            <ArrowLeft className="w-6 h-6 text-black" />
                        </button>
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center">Historical Logs</h1>
                        <button onClick={() => navigate('/profile')} className="absolute right-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors">
                             <UserCircle className="w-6 h-6 text-black" />
                        </button>
                    </div>
                     <div className="border-b border-[#e6e6e6]"></div>
                </div>
            </div>

            {/* Central Flex Zone */}
            <div className="flex-1 min-h-0 w-full flex flex-col gap-4 px-4 sm:px-6 lg:px-10 pb-6 pt-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                
                {/* Toolbar */}
                <div className="shrink-0 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
                    <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
                        <div className="relative w-full sm:w-72">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                            <input 
                                type="text" 
                                placeholder="Search ID, area, reason..." 
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="w-full pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:border-[#c8102e] transition-colors"
                            />
                        </div>
                        <select 
                            value={accessFilter} 
                            onChange={(e) => setAccessFilter(e.target.value)}
                            className="w-full sm:w-auto px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:border-[#c8102e] cursor-pointer transition-colors"
                        >
                            <option value="ALL">All Access Events</option>
                            <option value="ALLOWED">Allowed Only</option>
                            <option value="DENIED">Denied Only</option>
                        </select>
                    </div>
                    
                    <button 
                        onClick={handleDownloadFilteredCSV}
                        className="flex items-center justify-center gap-2 px-4 py-2 bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] text-black font-medium rounded-lg transition-colors w-full md:w-auto"
                    >
                        <Download className="w-5 h-5" />
                        Export Displayed Logs
                    </button>
                </div>

                {/* THE REUSABLE LOG TABLE COMPONENT */}
                <div className="flex-1 min-h-0 relative">
                    {error ? (
                        <div className="bg-white rounded-xl border border-gray-200 p-10 text-center text-red-500 font-medium">
                            {error}
                        </div>
                    ) : (
                        <LogTable 
                            logs={filteredLogs} 
                            loading={loading} 
                            emptyMessage={`No historical logs found matching "${searchTerm}".`}
                            isAdmin={true}
                        />
                    )}
                </div>
            </div>
        </div>
    );
}