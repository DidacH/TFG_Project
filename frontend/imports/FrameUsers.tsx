import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, ArrowLeft, UserCircle, Search, Download, CheckCircle, AlertTriangle } from "lucide-react";
import { cn } from "../components/ui/utils";

const API_URL = import.meta.env.VITE_API_URL || '';

// --- TypeScript Interfaces ---
interface UserData {
    id: string;
    name: string;
    email: string;
    role: string;
    registered_at: string;
    is_blocked: boolean;
}

export interface BasicUser {
    id: string;
    name: string;
    is_blocked: boolean;
}

interface UserBlockModalProps {
    isOpen: boolean;
    onClose: () => void;
    user: BasicUser | null;
    onConfirm: (userId: string, newStatus: boolean) => Promise<void>;
}

// --- Integrated Modal Component ---
function UserBlockModal({ isOpen, onClose, user, onConfirm }: UserBlockModalProps) {
    const [isLoading, setIsLoading] = useState(false);

    if (!isOpen || !user) return null;

    const handleConfirm = async () => {
        setIsLoading(true);
        try {
            await onConfirm(user.id, !user.is_blocked);
            onClose();
        } catch (error) {
            console.error("Error updating user status:", error);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-xl shadow-xl w-[90%] max-w-md overflow-hidden">
                <div className={cn("p-4 text-white flex items-center gap-2", user.is_blocked ? "bg-green-600" : "bg-red-600")}>
                    <AlertTriangle className="w-5 h-5" />
                    <h2 className="text-lg font-semibold">
                        {user.is_blocked ? "Unblock User" : "Block User"}
                    </h2>
                </div>
                
                <div className="p-6 text-gray-700">
                    <p className="text-base mb-2">
                        Are you sure you want to <strong>{user.is_blocked ? "unblock" : "block"}</strong> access for this user?
                    </p>
                    <p className="text-lg font-semibold text-black bg-gray-100 p-2 rounded text-center">
                        {user.name}
                    </p>
                </div>

                <div className="flex justify-end gap-3 p-4 bg-gray-50 border-t border-gray-200">
                    <button 
                        onClick={onClose} 
                        disabled={isLoading}
                        className="px-4 py-2 rounded-lg font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 transition-colors disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button 
                        onClick={handleConfirm} 
                        disabled={isLoading}
                        className={cn(
                            "px-4 py-2 rounded-lg font-medium text-white flex items-center gap-2 transition-colors disabled:opacity-50",
                            user.is_blocked ? "bg-green-600 hover:bg-green-700" : "bg-red-600 hover:bg-red-700"
                        )}
                    >
                        {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                        Confirm
                    </button>
                </div>
            </div>
        </div>
    );
}

// --- Main FrameUsers Component ---
export default function FrameUsers() {
    const navigate = useNavigate();
    const [users, setUsers] = useState<UserData[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [toastMessage, setToastMessage] = useState<string | null>(null);

    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('ALL');

    const [isModalOpen, setIsModalOpen] = useState(false);
    const [selectedUser, setSelectedUser] = useState<BasicUser | null>(null);

    const getToken = () => localStorage.getItem('token');

    const fetchUsers = useCallback(async () => {
        setLoading(true);
        const token = getToken();
        try {
            const response = await fetch(`${API_URL}/api/admin/users`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Error ${response.status}: ${errorText}`);
            }
            const data: UserData[] = await response.json();
            setUsers(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        document.title = "AIloQR - Manage Users";
        fetchUsers();
    }, [fetchUsers]);

    const handleToggleBlock = async (targetUserId: string, newStatus: boolean) => {
        const token = getToken();
        try {
            const response = await fetch(`${API_URL}/api/admin/user/${targetUserId}/toggle-block`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                await fetchUsers(); 
            } else {
                alert("Failed to change user status.");
            }
        } catch (error) {
            console.error("Error toggling block status:", error);
        }
    };

    const openBlockModal = (user: UserData) => {
        setSelectedUser({ id: user.id, name: user.name, is_blocked: user.is_blocked });
        setIsModalOpen(true);
    };

    const filteredUsers = users.filter(user => {
        const matchesSearch = user.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                              user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
                              user.id.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesStatus = statusFilter === 'ALL' ? true :
                              statusFilter === 'BLOCKED' ? user.is_blocked : !user.is_blocked;
        return matchesSearch && matchesStatus;
    });

    const copyToClipboard = (text: string, type: string) => {
        if (!text) return;
        navigator.clipboard.writeText(text);
        
        setToastMessage(`${type} copied to clipboard!`);
        
        setTimeout(() => {
            setToastMessage(null);
        }, 2500);
    };

    const handleDownloadFilteredCSV = () => {
        try {
            const headers = ['User ID', 'Name', 'Email', 'Role', 'Status', 'Registered At'];
            const csvRows = [];
            csvRows.push(headers.join(';'));
            
            for (const user of filteredUsers) {
                const row = [
                    user.id,
                    user.name,
                    user.email,
                    user.role,
                    user.is_blocked ? 'Blocked' : 'Active',
                    user.registered_at
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
            const fileName = `users_export_${dateStr}.csv`;

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
            
            <div className="shrink-0 bg-background pt-6 md:pt-8 w-full z-40">
                <div className="w-full mx-auto px-4 sm:px-6 lg:px-10">
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        <button onClick={() => navigate('/admin')} className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors">
                            <ArrowLeft className="w-6 h-6 text-black" />
                        </button>
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center">User Management</h1>
                        <button onClick={() => navigate('/profile')} className="absolute right-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors">
                             <UserCircle className="w-6 h-6 text-black" />
                        </button>
                    </div>
                     <div className="border-b border-[#e6e6e6]"></div>
                </div>
            </div>

            <div className="flex-1 min-h-0 w-full flex flex-col gap-4 px-4 sm:px-6 lg:px-10 pb-6 pt-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                
                <div className="shrink-0 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
                    <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
                        <div className="relative w-full sm:w-72">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                            <input 
                                type="text" 
                                placeholder="Search name, email, ID..." 
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="w-full pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:border-[#c8102e] transition-colors"
                            />
                        </div>
                        <select 
                            value={statusFilter} 
                            onChange={(e) => setStatusFilter(e.target.value)}
                            className="w-full sm:w-auto px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:border-[#c8102e] cursor-pointer transition-colors"
                        >
                            <option value="ALL">All Status</option>
                            <option value="ACTIVE">Active Only</option>
                            <option value="BLOCKED">Blocked Only</option>
                        </select>
                    </div>
                    
                    <button 
                        onClick={handleDownloadFilteredCSV}
                        className="flex items-center justify-center gap-2 px-4 py-2 bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] text-black font-medium rounded-lg transition-colors w-full md:w-auto"
                    >
                        <Download className="w-5 h-5" />
                        Export Selected Users (CSV)
                    </button>
                </div>

                <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto bg-white rounded-xl border border-gray-200 shadow-sm relative">
                    {loading ? (
                        <div className="flex justify-center items-center h-full min-h-[200px]"><Loader2 className="w-10 h-10 animate-spin text-[#c8102e]" /></div>
                    ) : error ? (
                        <div className="text-red-500 text-center p-10 font-medium">{error}</div>
                    ) : (
                        <table className="w-full text-left border-collapse min-w-[950px] table-fixed animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <thead className="bg-[#c8102e] text-white sticky top-0 z-10 shadow-[0_1px_0_#e5e7eb]">
                                <tr>
                                    <th className="p-4 font-semibold w-[15%]">User ID</th>
                                    <th className="p-4 font-semibold w-[18%]">Name</th>
                                    <th className="p-4 font-semibold w-[27%]">Email</th>
                                    <th className="p-4 font-semibold w-[10%] text-left">Role</th>
                                    <th className="p-4 font-semibold w-[12%] text-center">Status</th>
                                    <th className="p-4 font-semibold w-[18%] text-center">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {filteredUsers.length > 0 ? filteredUsers.map((user) => (
                                    <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                                        <td 
                                            className="p-4 font-mono text-sm text-gray-500 truncate cursor-pointer hover:text-blue-600 transition-colors" 
                                            title="Click to copy" 
                                            onClick={() => copyToClipboard(user.id, 'User ID')}
                                        >
                                            {user.id.substring(0, 12)}...
                                        </td>
                                        <td 
                                            className="p-4 font-medium text-sm text-gray-800 truncate cursor-pointer hover:text-blue-600 transition-colors" 
                                            title="Click to copy" 
                                            onClick={() => copyToClipboard(user.name, 'Name')}
                                        > 
                                            {user.name}
                                        </td>
                                        <td 
                                            className="p-4 text-sm text-gray-600 truncate cursor-pointer hover:text-blue-600 transition-colors" 
                                            title="Click to copy" 
                                            onClick={() => copyToClipboard(user.email, 'Email')}
                                        > 
                                            {user.email}
                                        </td>
                                        <td 
                                            className="p-4 text-sm text-gray-700 truncate cursor-pointer hover:text-blue-600 transition-colors"
                                            title="Click to copy"
                                            onClick={() => copyToClipboard(user.role, 'Role')}
                                        >
                                            {user.role}
                                        </td>
                                        <td className="p-4 text-center">
                                            <span className={cn(
                                                "font-bold text-xs tracking-wider uppercase",
                                                user.is_blocked ? "text-red-600" : "text-green-600"
                                            )}>
                                                {user.is_blocked ? 'BLOCKED' : 'ACTIVE'}
                                            </span>
                                        </td>
                                        <td className="p-4 text-center">
                                            <div className="flex items-center justify-center gap-2">
                                                <button 
                                                    onClick={() => navigate(`/user/${user.id}`)}
                                                    className="px-4 py-1.5 rounded-md text-sm font-medium bg-[#eeeeee] hover:bg-[#e0e0e0] text-gray-800 transition-colors shadow-sm"
                                                >
                                                    View
                                                </button>
                                                <button 
                                                    onClick={() => openBlockModal(user)}
                                                    className={cn(
                                                        "px-4 py-1.5 rounded-md text-sm font-medium text-white shadow-sm transition-colors w-[80px]",
                                                        user.is_blocked ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'
                                                    )}
                                                >
                                                    {user.is_blocked ? 'Unblock' : 'Block'}
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                )) : (
                                    <tr>
                                        <td colSpan={6} className="p-10 text-center text-gray-500 font-medium">
                                            No users found matching "{searchTerm}".
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>

            {toastMessage && (
                <div className="fixed bottom-8 right-8 z-50 bg-gray-900 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3 animate-in fade-in slide-in-from-bottom-4 duration-300">
                    <CheckCircle className="w-5 h-5 text-green-400" />
                    <span className="font-medium text-sm">{toastMessage}</span>
                </div>
            )}

            <UserBlockModal 
                isOpen={isModalOpen} 
                onClose={() => setIsModalOpen(false)} 
                user={selectedUser} 
                onConfirm={handleToggleBlock} 
            />
        </div>
    );
}