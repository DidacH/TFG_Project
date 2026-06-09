import { useState } from 'react';
import { Loader2, AlertTriangle } from 'lucide-react';
import { cn } from './ui/utils'; // Asumeixo que tens això per com fas servir cn als altres fitxers

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

export default function UserBlockModal({ isOpen, onClose, user, onConfirm }: UserBlockModalProps) {
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 animate-in fade-in duration-200">
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