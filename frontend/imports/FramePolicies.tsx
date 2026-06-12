import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { 
    ArrowLeft, UserCircle, BrainCircuit, BellRing, 
    Plus, Trash2, Clock, MapPin, Power, Loader2, AlertTriangle, X
} from "lucide-react";
import { cn } from "../components/ui/utils";

const API_URL = import.meta.env.VITE_API_URL || '';

// --- TypeScript Interfaces ---
interface AccessRule {
    id: number;
    role: string;
    area: string;
    days: string;
    start_time: string;
    end_time: string;
    active: boolean;
}

interface NewRuleData {
    role: string;
    area: string;
    days: string;
    start_time: string;
    end_time: string;
    active: boolean;
}

export default function FramePolicies() {
    const navigate = useNavigate();
    
    // UI Navigation State
    const [activeTab, setActiveTab] = useState<'access' | 'ai' | 'alerts'>('access');
    
    // States for Real Data (Access Rules)
    const [originalRules, setOriginalRules] = useState<AccessRule[]>([]);
    const [rules, setRules] = useState<AccessRule[]>([]);
    const [hasUnsavedRules, setHasUnsavedRules] = useState(false);
    
    // States for Core System Configuration (AI & Lockdown)
    const [aiThreshold, setAiThreshold] = useState(25); // UI representation mapped to 0-100
    const [originalSystemLockdown, setOriginalSystemLockdown] = useState(false);
    const [systemLockdown, setSystemLockdown] = useState(false);
    
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    
    // Modal Management State
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [newRule, setNewRule] = useState<NewRuleData>({
        role: 'Student', area: '', days: '0,1,2,3,4', start_time: '08:00', end_time: '20:00', active: true
    });

    // Dynamically extract unique areas from the existing rule set for the dropdown menu
    const existingAreas = Array.from(new Set(originalRules.map(r => r.area)));
    if (!existingAreas.includes('ALL')) existingAreas.unshift('ALL');

    const getToken = () => localStorage.getItem('token');

    // --- DATA FETCHING ARCHITECTURE ---
    // Utilizes AbortController to safely manage component unmounting during asynchronous operations
    const fetchData = useCallback(async (signal?: AbortSignal) => {
        setLoading(true);
        const token = getToken();
        try {
            // Concurrent Request 1: Fetch Access Control Rules
            const rulesRes = await fetch(`${API_URL}/api/admin/rules/access`, {
                headers: { 'Authorization': `Bearer ${token}` },
                signal
            });
            if (rulesRes.ok) {
                const fetchedRules = await rulesRes.json();
                
                if (!signal?.aborted) {
                    setRules(fetchedRules);
                    // Deep copy to serve as a baseline for detecting unsaved local changes
                    setOriginalRules(JSON.parse(JSON.stringify(fetchedRules))); 
                    setHasUnsavedRules(false);
                }
            }

            // Concurrent Request 2: Fetch Global Security Configurations
            const configRes = await fetch(`${API_URL}/api/admin/config`, {
                headers: { 'Authorization': `Bearer ${token}` },
                signal
            });
            if (configRes.ok) {
                const config = await configRes.json();
                
                if (!signal?.aborted) {
                    const isLocked = config.system_lockdown === 'true';
                    setOriginalSystemLockdown(isLocked);
                    setSystemLockdown(isLocked);
                    
                    // Normalize the backend threshold (-0.1 to 0.9) to a 0-100 scale for UI clarity
                    if (config.anomaly_threshold) {
                        const rawVal = parseFloat(config.anomaly_threshold);
                        let uiVal = (rawVal + 0.1) * 1000; 
                        if (uiVal < 0) uiVal = 0;
                        if (uiVal > 100) uiVal = 100;
                        setAiThreshold(Math.round(uiVal));
                    }
                }
            }
        } catch (error: any) {
            if (error.name === 'AbortError') return;
            if (!signal?.aborted) {
                console.error("Error fetching policies:", error);
            }
        } finally {
            if (!signal?.aborted) {
                setLoading(false);
            }
        }
    }, []);

    // Component mounting lifecycle hook
    useEffect(() => {
        document.title = "AIloQR - Security Policies";
        const controller = new AbortController();
        fetchData(controller.signal);
        
        return () => controller.abort();
    }, [fetchData]);

    // --- RULE MANAGEMENT (Local Mutators & Batch Processing) ---
    
    // Toggles the active status of a rule locally before committing to the database
    const handleToggleRuleLocal = (id: number) => {
        setRules(prev => prev.map(r => r.id === id ? { ...r, active: !r.active } : r));
        setHasUnsavedRules(true);
    };

    // Removes a rule locally from the state array
    const handleDeleteRuleLocal = (id: number) => {
        setRules(prev => prev.filter(r => r.id !== id));
        setHasUnsavedRules(true);
    };

    // Reverts all local changes by restoring the deep-copied original state
    const handleCancelRules = () => {
        setRules(JSON.parse(JSON.stringify(originalRules)));
        setHasUnsavedRules(false);
    };

    // Executes a batch transaction to synchronize local UI changes with the backend database
    const handleSaveRules = async () => {
        setSaving(true);
        try {
            // 1. Isolate rules that have altered their active status
            const changedRules = rules.filter(r => {
                const orig = originalRules.find(o => o.id === r.id);
                return orig && orig.active !== r.active;
            });

            // 2. Identify rules that exist in the original database but were removed locally
            const deletedRules = originalRules.filter(o => !rules.find(r => r.id === o.id));

            const requests: Promise<any>[] = [];

            // Queue PUT network requests for modifications
            changedRules.forEach(r => {
                requests.push(fetch(`${API_URL}/api/admin/rules/access`, {
                    method: 'PUT',
                    headers: { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: r.id, active: r.active })
                }));
            });

            // Queue DELETE network requests for removals
            deletedRules.forEach(r => {
                requests.push(fetch(`${API_URL}/api/admin/rules/access?id=${r.id}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${getToken()}` }
                }));
            });

            // Execute all API calls concurrently to minimize network latency overhead
            await Promise.all(requests);
            
            // Refresh the UI context with verified server data to ensure consistency
            await fetchData();
        } catch (e) {
            console.error("Batch save transaction failed:", e);
        } finally {
            setSaving(false);
        }
    };

    // Submits a new security policy to the access control matrix
    const handleAddRule = async () => {
        try {
            await fetch(`${API_URL}/api/admin/rules/access`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(newRule)
            });
            setIsAddModalOpen(false);
            fetchData();
        } catch (e) { 
            console.error("Failed to create rule:", e); 
        }
    };

    const openAddRuleModal = () => {
        setNewRule(prev => ({ ...prev, area: existingAreas[0] || '' }));
        setIsAddModalOpen(true);
    };

    // --- SYSTEM CONFIGURATION ACTIONS ---

    const handleToggleLockdownLocal = () => {
        setSystemLockdown(prev => !prev);
    };

    // Pushes configuration alterations to the core system settings
    const handleSaveConfig = async () => {
        setSaving(true);
        // Translate the UI percentage back to the algorithmic raw threshold
        const rawThreshold = (aiThreshold / 1000) - 0.1;
        try {
            // 1. Update the AI Detection Threshold parameters
            await fetch(`${API_URL}/api/admin/config`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ anomaly_threshold: rawThreshold.toFixed(4) })
            });

            // 2. Process system lockdown state changes securely
            // This triggers specific backend protocols (like WebSocket broadcasts or notification dispatchers)
            if (systemLockdown !== originalSystemLockdown) {
                await fetch(`${API_URL}/api/admin/system-lockdown`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${getToken()}` }
                });
            }

            // Force a state refresh to validate successful operations
            await fetchData();
        } catch (e) { 
            console.error("Configuration update failed:", e); 
        } finally {
            setSaving(false);
        }
    };

    // Helper formatter for rendering database bitmasks into human-readable day schedules
    const formatDays = (daysStr: string) => {
        if (daysStr === '0,1,2,3,4,5,6') return 'Every day';
        if (daysStr === '0,1,2,3,4') return 'Mon - Fri';
        const dayMap: {[key: string]: string} = {'0':'Mon', '1':'Tue', '2':'Wed', '3':'Thu', '4':'Fri', '5':'Sat', '6':'Sun'};
        return daysStr.split(',').map(d => dayMap[d]).join(', ');
    };

    return (
        <div className="fixed inset-0 flex flex-col w-full bg-background overflow-hidden">
            
            {/* POLICY CREATION MODAL */}
            {isAddModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-white rounded-xl shadow-xl w-[90%] max-w-md overflow-hidden">
                        <div className="flex justify-between items-center p-4 border-b border-gray-100">
                            <h2 className="text-lg font-semibold text-gray-900">Create New Access Rule</h2>
                            <button onClick={() => setIsAddModalOpen(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5"/></button>
                        </div>
                        <div className="p-4 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
                                <select className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:border-[#c8102e] bg-white" value={newRule.role} onChange={e => setNewRule({...newRule, role: e.target.value})}>
                                    <option value="Student">Student</option>
                                    <option value="Professor">Professor</option>
                                    <option value="Staff">Staff</option>
                                    <option value="Admin">Admin</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Target Area</label>
                                <select className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:border-[#c8102e] bg-white" value={newRule.area} onChange={e => setNewRule({...newRule, area: e.target.value})}>
                                    {existingAreas.map(area => (
                                        <option key={area} value={area}>{area}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Start Time</label>
                                    <input type="time" className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:border-[#c8102e]" value={newRule.start_time} onChange={e => setNewRule({...newRule, start_time: e.target.value})} />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">End Time</label>
                                    <input type="time" className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:border-[#c8102e]" value={newRule.end_time} onChange={e => setNewRule({...newRule, end_time: e.target.value})} />
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Days (Comma separated: 0=Mon, 6=Sun)</label>
                                <input type="text" className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:border-[#c8102e]" value={newRule.days} onChange={e => setNewRule({...newRule, days: e.target.value})} />
                            </div>
                        </div>
                        <div className="p-4 bg-gray-50 border-t border-gray-100 flex justify-end gap-3">
                            <button onClick={() => setIsAddModalOpen(false)} className="px-4 py-2 font-medium text-gray-600 hover:bg-gray-200 rounded-lg transition-colors">Cancel</button>
                            <button onClick={handleAddRule} className="px-5 py-2 font-medium text-white bg-[#c8102e] hover:bg-[#b00f29] rounded-lg transition-colors">Create Rule</button>
                        </div>
                    </div>
                </div>
            )}

            {/* --- STATIC HEADER & NAVIGATION --- */}
            <div className="shrink-0 bg-background pt-6 md:pt-8 w-full z-40 animate-in fade-in slide-in-from-top-4 duration-500">
                <div className="w-full mx-auto px-4 sm:px-6 lg:px-10">
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        <button onClick={() => navigate(-1)} className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors">
                            <ArrowLeft className="w-6 h-6 text-black" />
                        </button>
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center flex items-center gap-2">
                            Security Policies
                        </h1>
                        <button onClick={() => navigate('/profile')} className="absolute right-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors">
                             <UserCircle className="w-6 h-6 text-black" />
                        </button>
                    </div>
                    
                    {/* MODULAR TAB NAVIGATION */}
                    <div className="flex items-center gap-6 md:gap-10 border-b border-[#e6e6e6] mt-4 px-2">
                        <button onClick={() => setActiveTab('access')} className={cn("pb-3 text-sm md:text-base font-medium transition-colors border-b-2 flex items-center gap-2", activeTab === 'access' ? "border-[#c8102e] text-[#c8102e]" : "border-transparent text-gray-500 hover:text-gray-800")}>
                            <Clock className="w-4 h-4" /> Access Rules
                        </button>
                        <button onClick={() => setActiveTab('ai')} className={cn("pb-3 text-sm md:text-base font-medium transition-colors border-b-2 flex items-center gap-2", activeTab === 'ai' ? "border-[#c8102e] text-[#c8102e]" : "border-transparent text-gray-500 hover:text-gray-800")}>
                            <BrainCircuit className="w-4 h-4" /> AI & Core
                        </button>
                        <button onClick={() => setActiveTab('alerts')} className={cn("pb-3 text-sm md:text-base font-medium transition-colors border-b-2 flex items-center gap-2", activeTab === 'alerts' ? "border-[#c8102e] text-[#c8102e]" : "border-transparent text-gray-500 hover:text-gray-800")}>
                            <BellRing className="w-4 h-4" /> Alert Triggers
                        </button>
                    </div>
                </div>
            </div>

            {/* --- DYNAMIC CONTENT RENDERING ZONE --- */}
            <div className="flex-1 min-h-0 w-full flex flex-col gap-6 px-4 sm:px-6 lg:px-10 pb-10 pt-6">
                
                {loading ? (
                    <div className="flex justify-center items-center h-full"><Loader2 className="w-10 h-10 animate-spin text-[#c8102e]" /></div>
                ) : (
                    <>
                        {/* VIEW 1: ACCESS MATRIX CONFIGURATION */}
                        {activeTab === 'access' && (
                            <div className="animate-in fade-in duration-300 flex flex-col h-full flex-1 min-h-0">
                                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4 shrink-0">
                                    <div>
                                        <h2 className="text-xl font-semibold text-gray-900">Role-Based Access</h2>
                                        <p className="text-sm text-gray-500 mt-1">Define which roles can access specific areas and when.</p>
                                    </div>
                                    <div className="flex items-center gap-3 w-full sm:w-auto">
                                        {hasUnsavedRules && (
                                            <>
                                                <button onClick={handleCancelRules} className="px-4 py-2 font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                                                    Cancel
                                                </button>
                                                <button onClick={handleSaveRules} disabled={saving} className="flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg font-medium transition-colors shadow-sm disabled:opacity-50 min-w-[140px]">
                                                    Save Changes
                                                </button>
                                            </>
                                        )}
                                        <button onClick={openAddRuleModal} className="flex items-center justify-center gap-2 bg-[#c8102e] hover:bg-[#b00f29] text-white px-4 py-2 rounded-lg font-medium transition-colors shadow-sm sm:w-auto w-full">
                                            <Plus className="w-4 h-4" /> New Rule
                                        </button>
                                    </div>
                                </div>
                                
                                <div className="flex-1 min-h-0 bg-white rounded-xl border border-gray-200 shadow-sm relative flex flex-col">
                                    <div className="overflow-y-auto overflow-x-auto flex-1">
                                        <table className="w-full text-left border-collapse min-w-[800px] table-fixed">
                                            <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 sticky top-0 z-10 shadow-[0_1px_0_#e5e7eb]">
                                                <tr>
                                                    <th className="p-4 font-medium w-[15%]">Role</th>
                                                    <th className="p-4 font-medium w-[25%]">Target Area</th>
                                                    <th className="p-4 font-medium w-[20%]">Allowed Days</th>
                                                    <th className="p-4 font-medium w-[20%]">Time Window</th>
                                                    <th className="p-4 font-medium w-[10%] text-center">Status</th>
                                                    <th className="p-4 font-medium w-[10%] text-center">Delete</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-100">
                                                {rules.map((rule) => (
                                                    <tr key={rule.id} className="hover:bg-gray-50/50 transition-colors">
                                                        <td className="p-4 text-sm font-medium text-gray-900">{rule.role}</td>
                                                        <td className="p-4 text-sm text-gray-600 flex items-center gap-2"><MapPin className="w-4 h-4 text-gray-400"/> {rule.area}</td>
                                                        <td className="p-4 text-sm text-gray-600">{formatDays(rule.days)}</td>
                                                        <td className="p-4 text-sm text-gray-600 font-mono">{rule.start_time.substring(0,5)} - {rule.end_time.substring(0,5)}</td>
                                                        <td className="p-4 text-center">
                                                            <div 
                                                                onClick={() => handleToggleRuleLocal(rule.id)}
                                                                className={cn("inline-flex w-10 h-5 rounded-full cursor-pointer transition-colors relative", rule.active ? "bg-green-500" : "bg-gray-300")}
                                                            >
                                                                <div className={cn("absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-sm", rule.active ? "translate-x-5" : "translate-x-0")} />
                                                            </div>
                                                        </td>
                                                        <td className="p-4 text-center">
                                                            <button 
                                                                onClick={() => handleDeleteRuleLocal(rule.id)} 
                                                                className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                                                            >
                                                                <Trash2 className="w-4 h-4" />
                                                            </button>
                                                        </td>
                                                    </tr>
                                                ))}
                                                {rules.length === 0 && (
                                                    <tr><td colSpan={6} className="p-8 text-center text-gray-500">No access rules defined.</td></tr>
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* VIEW 2: AI MACHINE LEARNING SENSITIVITY & CORE CONTROLS */}
                        {activeTab === 'ai' && (
                            <div className="animate-in fade-in duration-300 max-w-4xl overflow-y-auto pr-2 pb-8">
                                <div className="mb-6">
                                    <h2 className="text-xl font-semibold text-gray-900">System Configuration</h2>
                                    <p className="text-sm text-gray-500 mt-1">Adjust core security parameters and AI sensitivity.</p>
                                </div>

                                <div className="grid grid-cols-1 gap-6">
                                    {/* Card 1: Machine Learning Evaluation Threshold */}
                                    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
                                        <div className="flex items-start gap-4 mb-6">
                                            <div className="p-3 bg-indigo-50 text-indigo-600 rounded-lg"><BrainCircuit className="w-6 h-6" /></div>
                                            <div>
                                                <h3 className="text-lg font-semibold text-gray-900">AI Anomaly Threshold</h3>
                                                <p className="text-sm text-gray-500">Determines how strict the AI is when flagging unusual behavior.</p>
                                            </div>
                                        </div>
                                        
                                        <div className="px-2">
                                            <div className="flex justify-between text-sm font-medium mb-4">
                                                <span className={cn(aiThreshold < 40 ? "text-green-600 font-bold" : "text-gray-400")}>Lax (Permissive)</span>
                                                <span className={cn(aiThreshold >= 40 && aiThreshold <= 70 ? "text-blue-600 font-bold" : "text-gray-400")}>Balanced</span>
                                                <span className={cn(aiThreshold > 70 ? "text-red-600 font-bold" : "text-gray-400")}>Strict (High Security)</span>
                                            </div>
                                            <input 
                                                type="range" 
                                                min="0" max="100" 
                                                value={aiThreshold}
                                                onChange={(e) => setAiThreshold(Number(e.target.value))}
                                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#c8102e]"
                                            />
                                            <div className="mt-4 flex justify-between items-center text-xs text-gray-400">
                                                <span>UI Value: {aiThreshold}%</span>
                                                <span>Raw DB Value: {((aiThreshold / 1000) - 0.1).toFixed(4)}</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Card 2: Emergency Response Protocol */}
                                    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
                                        <div className="flex items-start gap-4">
                                            <div className={cn("p-3 rounded-lg transition-colors", systemLockdown ? "bg-red-100 text-red-600" : "bg-gray-100 text-gray-600")}><Power className="w-6 h-6" /></div>
                                            <div>
                                                <h3 className="text-lg font-semibold text-gray-900">Global Lockdown State</h3>
                                                <p className="text-sm text-gray-500">Overrides all rules and blocks all standard access instantly.</p>
                                            </div>
                                        </div>
                                        <div 
                                            onClick={handleToggleLockdownLocal}
                                            className={cn("inline-flex w-12 h-6 rounded-full cursor-pointer transition-colors relative shadow-inner", systemLockdown ? "bg-red-600" : "bg-gray-300")}
                                        >
                                            <div className={cn("absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-sm", systemLockdown ? "translate-x-6" : "translate-x-0")} />
                                        </div>
                                    </div>
                                </div>

                                <div className="mt-6 flex justify-end">
                                    <button 
                                        onClick={handleSaveConfig}
                                        disabled={saving}
                                        className="bg-[#c8102e] hover:bg-[#b00f29] disabled:opacity-50 text-white px-6 py-2 rounded-lg font-medium transition-colors shadow-sm flex items-center gap-2"
                                    >
                                        Save Configuration
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* VIEW 3: SYSTEM NOTIFICATION HANDLERS */}
                        {activeTab === 'alerts' && (
                            <div className="animate-in fade-in duration-300 overflow-y-auto pr-2 pb-8">
                                <div className="mb-6">
                                    <h2 className="text-xl font-semibold text-gray-900">Alert Triggers</h2>
                                    <p className="text-sm text-gray-500 mt-1">Configure how the system classifies different types of violations.</p>
                                </div>
                                
                                <div className="bg-white rounded-xl border border-gray-200 shadow-sm divide-y divide-gray-100">
                                    {[
                                        { title: "Out of Hours Access", desc: "User tries to access outside their allowed time window." },
                                        { title: "Area Violation", desc: "User role does not have permission for the target area." },
                                        { title: "AI High Confidence Anomaly", desc: "AI detects a severe pattern deviation." },
                                    ].map((alert, i) => (
                                        <div key={i} className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-gray-50 transition-colors">
                                            <div className="flex gap-4 items-start">
                                                <AlertTriangle className="w-5 h-5 text-orange-400 mt-0.5" />
                                                <div>
                                                    <p className="font-medium text-gray-900">{alert.title}</p>
                                                    <p className="text-sm text-gray-500">{alert.desc}</p>
                                                </div>
                                            </div>
                                            <select className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-500 min-w-[140px]">
                                                <option>Critical Alert</option>
                                                <option>Warning</option>
                                                <option>Log Only</option>
                                            </select>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}