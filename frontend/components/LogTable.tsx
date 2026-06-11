import { useState } from "react";
import { Loader2, CheckCircle } from "lucide-react";
import { cn } from "./ui/utils";

export interface LogEntry {
    id?: string;
    user_id: string;
    role: string;
    area: string;
    access_time: string;
    entry_allowed: boolean;
    reason: string;
    is_threat?: boolean;
    is_anomaly?: boolean;
}

interface LogTableProps {
    logs: LogEntry[];
    loading: boolean;
    emptyMessage?: string;
    isAdmin?: boolean; // Prop to hide/show details
}

export default function LogTable({ 
    logs, 
    loading, 
    emptyMessage = "No logs found.",
    isAdmin = false 
}: LogTableProps) {
    
    // State for the copy-to-clipboard toast notification
    const [toastMessage, setToastMessage] = useState<string | null>(null);

    // Function to handle clipboard copying and toast triggering
    const copyToClipboard = (text: string, fieldName: string) => {
        if (!text) return;
        navigator.clipboard.writeText(text);
        setToastMessage(`${fieldName} copied to clipboard!`);
        setTimeout(() => {
            setToastMessage(null);
        }, 2500);
    };

    return (
        <div className="absolute inset-0 overflow-y-auto overflow-x-auto bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col">
            {loading ? (
                <div className="flex justify-center items-center h-full min-h-[200px]">
                    <Loader2 className="w-10 h-10 animate-spin text-[#c8102e]" />
                </div>
            ) : logs.length > 0 ? (
                <table className="w-full text-left border-collapse min-w-[950px] table-fixed animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <thead className="bg-[#c8102e] text-white sticky top-0 z-10 shadow-[0_1px_0_#e5e7eb]">
                        <tr>
                            {/* Adjusted column widths dynamically based on isAdmin to maximize space for Reason */}
                            <th className={cn("p-4 font-semibold", isAdmin ? "w-[15%]" : "w-[20%]")}>Time</th>
                            <th className={cn("p-4 font-semibold", isAdmin ? "w-[15%]" : "w-[25%]")}>User ID</th>
                            <th className={cn("p-4 font-semibold", isAdmin ? "w-[10%]" : "w-[15%]")}>Role</th>
                            <th className={cn("p-4 font-semibold", isAdmin ? "w-[15%]" : "w-[25%]")}>Area</th>
                            <th className={cn("p-4 font-semibold", isAdmin ? "w-[10%]" : "w-[15%]")}>Status</th>
                            {isAdmin && (
                                <th className="p-4 font-semibold w-[35%]">Reason / Detail</th>
                            )}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {logs.map((log, index) => {
                            const timeStr = log.access_time?.split('.')[0] || log.access_time;
                            return (
                                <tr 
                                    key={log.id || index} 
                                    className="bg-white hover:bg-gray-50 transition-colors"
                                >
                                    <td 
                                        className="p-4 text-sm text-gray-500 whitespace-nowrap cursor-pointer hover:text-blue-600 transition-colors"
                                        title="Click to copy"
                                        onClick={() => copyToClipboard(timeStr, "Time")}
                                    >
                                        {timeStr}
                                    </td>
                                    
                                    <td 
                                        className="p-4 font-mono text-sm text-gray-500 truncate cursor-pointer hover:text-blue-600 transition-colors" 
                                        title="Click to copy"
                                        onClick={() => copyToClipboard(log.user_id, "User ID")}
                                    >
                                        {log.user_id?.substring(0, 12)}...
                                    </td>
                                    
                                    <td 
                                        className="p-4 text-sm text-gray-700 cursor-pointer hover:text-blue-600 transition-colors truncate"
                                        title="Click to copy"
                                        onClick={() => copyToClipboard(log.role, "Role")}
                                    >
                                        {log.role}
                                    </td>
                                    
                                    <td 
                                        className="p-4 text-sm text-gray-700 truncate cursor-pointer hover:text-blue-600 transition-colors"
                                        title="Click to copy"
                                        onClick={() => copyToClipboard(log.area, "Area")}
                                    >
                                        {log.area}
                                    </td>
                                    
                                    {/* Status: Simplified typography, no underline, no copy action needed */}
                                    <td className="p-4 text-sm whitespace-nowrap">
                                        <span className={cn(
                                            "font-bold text-xs tracking-wider", 
                                            log.entry_allowed ? "text-green-600" : "text-red-600"
                                        )}>
                                            {log.entry_allowed ? 'ALLOWED' : 'DENIED'}
                                        </span>
                                    </td>
                                    
                                    {/* Reason conditionally rendered for Admins */}
                                    {isAdmin && (
                                        <td 
                                            className="p-4 text-sm text-gray-700 truncate cursor-pointer hover:text-blue-600 transition-colors" 
                                            title="Click to copy"
                                            onClick={() => copyToClipboard(log.reason, "Reason")}
                                        >
                                            {log.reason}
                                        </td>
                                    )}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            ) : (
                <div className="flex items-center justify-center h-full min-h-[200px] text-gray-500 font-medium">
                    {emptyMessage}
                </div>
            )}

            {/* Floating Toast Notification for Copy Actions */}
            {toastMessage && (
                <div className="fixed bottom-8 right-8 z-50 bg-gray-900 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3 animate-in fade-in slide-in-from-bottom-4 duration-300">
                    <CheckCircle className="w-5 h-5 text-green-400" />
                    <span className="font-medium text-sm">{toastMessage}</span>
                </div>
            )}
        </div>
    );
}