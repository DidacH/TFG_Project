import React from 'react';
import { Loader2, CheckCircle, Ban, ShieldAlert, AlertTriangle } from 'lucide-react';

// Interfície de com arriben les dades del backend (app.py)
export interface LogEntry {
    id?: string | number;
    user_id: string;
    role: string;
    area: string;
    access_time: string;
    entry_allowed: boolean;
    reason: string;
    risk_score?: number;
    is_anomaly?: boolean;
    is_threat?: boolean;
    error_code?: string;
}

interface LogTableProps {
    logs: LogEntry[];
    loading: boolean;
    emptyMessage?: string;
}

export default function LogTable({ logs, loading, emptyMessage = "No logs found." }: LogTableProps) {
    
    // Funció "Click to copy" per als IDs
    const copyToClipboard = (text: string) => {
        if (text) navigator.clipboard.writeText(text);
    };

    if (loading) {
        return (
            <div className="flex justify-center items-center h-40 w-full bg-white rounded-xl border border-gray-200">
                <Loader2 className="w-10 h-10 animate-spin text-[#c8102e]" />
            </div>
        );
    }

    return (
        <div className="overflow-y-auto overflow-x-auto bg-white rounded-xl border border-gray-200 shadow-sm flex-grow relative h-full">
            <table className="w-full text-left border-collapse min-w-[1000px] table-fixed">
                <thead className="bg-[#c8102e] text-white sticky top-0 z-10 shadow-[0_1px_0_#e5e7eb]">
                    <tr>
                        <th className="p-4 font-semibold w-[15%]">Time</th>
                        <th className="p-4 font-semibold w-[15%]">User ID</th>
                        <th className="p-4 font-semibold w-[10%] text-center">Role</th>
                        <th className="p-4 font-semibold w-[15%]">Area</th>
                        <th className="p-4 font-semibold w-[15%] text-center">Status</th>
                        <th className="p-4 font-semibold w-[30%]">Reason / Detail</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                    {logs.length > 0 ? logs.map((log, index) => {
                        // Lògica de colors per fila basada en la IA / Amenaces
                        const isThreat = log.is_threat;
                        const isAnomaly = log.is_anomaly;
                        const rowBg = isThreat ? "bg-red-50 hover:bg-red-100" : 
                                    isAnomaly ? "bg-orange-50 hover:bg-orange-100" : 
                                    "hover:bg-gray-50";

                        return (
                            <tr key={log.id || index} className={`${rowBg} transition-colors`}>
                                <td className="p-4 text-sm text-gray-600 truncate" title={log.access_time}>
                                    {/* Netegem els microsegons de la data si venen del Python */}
                                    {log.access_time?.split('.')[0] || 'N/A'}
                                </td>
                                
                                <td 
                                    className="p-4 font-mono text-sm text-gray-500 truncate cursor-pointer hover:text-blue-600 transition-colors"
                                    title="Fes clic per copiar ID sencer"
                                    onClick={() => copyToClipboard(log.user_id)}
                                >
                                    {log.user_id && log.user_id !== 'unknown' ? `${log.user_id.substring(0, 8)}...` : 'Unknown'}
                                </td>
                                
                                <td className="p-4 text-center">
                                    <span className="bg-white border border-gray-200 text-gray-700 px-2 py-1 rounded text-xs font-medium shadow-sm">
                                        {log.role || 'N/A'}
                                    </span>
                                </td>
                                
                                <td className="p-4 font-medium text-gray-700 truncate" title={log.area}>
                                    {log.area}
                                </td>
                                
                                <td className="p-4 text-center">
                                    {log.entry_allowed ? (
                                        <span className="inline-flex items-center justify-center text-green-700 bg-green-100 px-2 py-1 rounded-full text-xs font-bold">
                                            <CheckCircle className="w-3 h-3 mr-1" /> ALLOWED
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center justify-center text-red-700 bg-red-100 px-2 py-1 rounded-full text-xs font-bold">
                                            <Ban className="w-3 h-3 mr-1" /> DENIED
                                        </span>
                                    )}
                                </td>
                                
                                <td className="p-4 text-sm text-gray-700">
                                    <div className="flex items-center gap-2 truncate" title={log.reason}>
                                        {isThreat && <ShieldAlert className="w-4 h-4 text-red-600 shrink-0" />}
                                        {isAnomaly && !isThreat && <AlertTriangle className="w-4 h-4 text-orange-500 shrink-0" />}
                                        <span className="truncate font-medium">{log.reason}</span>
                                    </div>
                                </td>
                            </tr>
                        );
                    }) : (
                        <tr>
                            <td colSpan={6} className="p-10 text-center text-gray-500 font-medium">
                                {emptyMessage}
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
}