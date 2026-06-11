import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { 
    ArrowLeft, UserCircle, Shield, BrainCircuit, BellRing, 
    Plus, Trash2, Clock, MapPin, Power, Activity, AlertTriangle
} from "lucide-react";
import { cn } from "../components/ui/utils";

// Mock Data for the UI
const MOCK_ACCESS_RULES = [
    { id: '1', role: 'Student', area: 'Classroom_1', days: 'Mon-Fri', time: '08:00 - 14:00', active: true },
    { id: '2', role: 'Staff', area: 'Server_Room', days: 'Mon-Sun', time: '00:00 - 23:59', active: true },
    { id: '3', role: 'Professor', area: 'Lab_A', days: 'Mon-Fri', time: '08:00 - 20:00', active: false },
];

export default function FramePolicies() {
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState<'access' | 'ai' | 'alerts'>('access');
    
    // AI Settings State (Mock)
    const [aiThreshold, setAiThreshold] = useState(65);
    
    useEffect(() => {
        document.title = "AIloQR - Security Policies";
    }, []);

    return (
        <div className="fixed inset-0 flex flex-col w-full bg-background overflow-hidden">
            
            {/* --- HEADER --- */}
            <div className="shrink-0 bg-background pt-6 md:pt-8 w-full z-40">
                <div className="w-full mx-auto px-4 sm:px-6 lg:px-10">
                    <div className="relative flex justify-center items-center h-12 md:h-14 mb-3">
                        <button onClick={() => navigate(-1)} className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors">
                            <ArrowLeft className="w-6 h-6 text-black" />
                        </button>
                        <h1 className="text-xl md:text-2xl font-semibold text-black text-center flex items-center gap-2">
                            <Shield className="w-6 h-6 text-[#c8102e]" /> Security Policies
                        </h1>
                        <button onClick={() => navigate('/profile')} className="absolute right-0 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-[#eeeeee] hover:bg-[#e0e0e0] rounded-full transition-colors">
                             <UserCircle className="w-6 h-6 text-black" />
                        </button>
                    </div>
                    
                    {/* TABS NAVIGATION */}
                    <div className="flex items-center gap-6 md:gap-10 border-b border-[#e6e6e6] mt-4 px-2">
                        <button 
                            onClick={() => setActiveTab('access')}
                            className={cn("pb-3 text-sm md:text-base font-medium transition-colors border-b-2 flex items-center gap-2", activeTab === 'access' ? "border-[#c8102e] text-[#c8102e]" : "border-transparent text-gray-500 hover:text-gray-800")}
                        >
                            <Clock className="w-4 h-4" /> Access Rules
                        </button>
                        <button 
                            onClick={() => setActiveTab('ai')}
                            className={cn("pb-3 text-sm md:text-base font-medium transition-colors border-b-2 flex items-center gap-2", activeTab === 'ai' ? "border-[#c8102e] text-[#c8102e]" : "border-transparent text-gray-500 hover:text-gray-800")}
                        >
                            <BrainCircuit className="w-4 h-4" /> AI & Core
                        </button>
                        <button 
                            onClick={() => setActiveTab('alerts')}
                            className={cn("pb-3 text-sm md:text-base font-medium transition-colors border-b-2 flex items-center gap-2", activeTab === 'alerts' ? "border-[#c8102e] text-[#c8102e]" : "border-transparent text-gray-500 hover:text-gray-800")}
                        >
                            <BellRing className="w-4 h-4" /> Alert Triggers
                        </button>
                    </div>
                </div>
            </div>

            {/* --- CONTENT ZONE --- */}
            <div className="flex-1 min-h-0 w-full flex flex-col gap-6 px-4 sm:px-6 lg:px-10 pb-10 pt-6 overflow-y-auto">
                
                {/* TAB 1: ACCESS RULES */}
                {activeTab === 'access' && (
                    <div className="animate-in fade-in duration-300 flex flex-col h-full">
                        <div className="flex justify-between items-center mb-4">
                            <div>
                                <h2 className="text-xl font-semibold text-gray-900">Role-Based Access</h2>
                                <p className="text-sm text-gray-500 mt-1">Define which roles can access specific areas and when.</p>
                            </div>
                            <button className="flex items-center gap-2 bg-[#c8102e] hover:bg-[#b00f29] text-white px-4 py-2 rounded-lg font-medium transition-colors shadow-sm">
                                <Plus className="w-4 h-4" /> New Rule
                            </button>
                        </div>
                        
                        <div className="flex-1 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                            <table className="w-full text-left border-collapse min-w-[800px]">
                                <thead className="bg-gray-50 border-b border-gray-200 text-gray-600">
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
                                    {MOCK_ACCESS_RULES.map((rule) => (
                                        <tr key={rule.id} className="hover:bg-gray-50/50 transition-colors">
                                            <td className="p-4 text-sm font-medium text-gray-900">{rule.role}</td>
                                            <td className="p-4 text-sm text-gray-600 flex items-center gap-2"><MapPin className="w-4 h-4 text-gray-400"/> {rule.area}</td>
                                            <td className="p-4 text-sm text-gray-600">{rule.days}</td>
                                            <td className="p-4 text-sm text-gray-600 font-mono">{rule.time}</td>
                                            <td className="p-4 text-center">
                                                <div className={cn("inline-flex w-10 h-5 rounded-full cursor-pointer transition-colors relative", rule.active ? "bg-green-500" : "bg-gray-300")}>
                                                    <div className={cn("absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-sm", rule.active ? "translate-x-5" : "translate-x-0")} />
                                                </div>
                                            </td>
                                            <td className="p-4 text-center">
                                                <button className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors">
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* TAB 2: AI & CORE SYSTEM */}
                {activeTab === 'ai' && (
                    <div className="animate-in fade-in duration-300 max-w-4xl">
                        <div className="mb-6">
                            <h2 className="text-xl font-semibold text-gray-900">System Configuration</h2>
                            <p className="text-sm text-gray-500 mt-1">Adjust core security parameters and AI sensitivity.</p>
                        </div>

                        <div className="grid grid-cols-1 gap-6">
                            {/* Card 1: AI Threshold */}
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
                                        <span>Raw DB Value: {(aiThreshold * 0.001).toFixed(4)}</span>
                                    </div>
                                </div>
                            </div>

                            {/* Card 2: General Security */}
                            <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
                                <div className="flex items-start gap-4">
                                    <div className="p-3 bg-red-50 text-red-600 rounded-lg"><Power className="w-6 h-6" /></div>
                                    <div>
                                        <h3 className="text-lg font-semibold text-gray-900">Global Lockdown State</h3>
                                        <p className="text-sm text-gray-500">Overrides all rules and blocks all standard access.</p>
                                    </div>
                                </div>
                                <div className="inline-flex w-12 h-6 rounded-full bg-gray-300 cursor-not-allowed relative opacity-70">
                                    <div className="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full" />
                                </div>
                            </div>
                        </div>

                        <div className="mt-6 flex justify-end">
                            <button className="bg-[#c8102e] hover:bg-[#b00f29] text-white px-6 py-2 rounded-lg font-medium transition-colors shadow-sm">
                                Save Configuration
                            </button>
                        </div>
                    </div>
                )}

                {/* TAB 3: ALERTS */}
                {activeTab === 'alerts' && (
                    <div className="animate-in fade-in duration-300">
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

            </div>
        </div>
    );
}