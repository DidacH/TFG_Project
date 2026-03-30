import { useState, useEffect, useRef, forwardRef, Ref } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Eye, EyeOff, Loader2, CheckCircle2, XCircle } from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || '';

// Reusable Components


//Generic input component
//Used for email and name fields
interface InputProps {
  value: string;
  onChange: (value: string) => void;
  onBlur: () => void;
  placeholder: string;
  type?: "text" | "email" | "name";
  hasError?: boolean;
}

const Input = forwardRef(({ value, onChange, onBlur, placeholder, type = "text", hasError = false }: InputProps, ref: Ref<HTMLInputElement>) => {
  const errorClasses = hasError ? "border-red-500" : "border-[#e0e0e0]";
  return (
    <div className="relative bg-white box-border flex items-center h-[50px] rounded-[8px] w-full">
      <div aria-hidden="true" className={`absolute border ${errorClasses} border-solid inset-0 pointer-events-none rounded-[8px] transition-colors`} />
      <input ref={ref} type={type} value={value} onChange={(e) => onChange(e.target.value)} onBlur={onBlur} placeholder={placeholder} className="w-full h-full bg-transparent border-none outline-none font-sans px-4 text-base md:text-lg text-black placeholder:text-[#828282] focus:placeholder-transparent transition-colors duration-300" />
    </div>
  );
});

//Password specific input component with visibility toggle
interface PasswordInputProps {
    value: string;
    onChange: (value: string) => void;
    onFocus: () => void;
    onBlur: () => void;
    placeholder: string;
    hasError?: boolean;
}

const PasswordInput = forwardRef(({ value, onChange, onFocus, onBlur, placeholder, hasError = false }: PasswordInputProps, ref: Ref<HTMLInputElement>) => {
    const [showPassword, setShowPassword] = useState(false);
    const toggleVisibility = () => { setShowPassword(!showPassword); };
    const errorClasses = hasError ? "border-red-500" : "border-[#e0e0e0]";

    return (
        <div className="relative bg-white box-border flex items-center h-[50px] rounded-[8px] w-full">
            <div aria-hidden="true" className={`absolute border ${errorClasses} border-solid inset-0 pointer-events-none rounded-[8px] transition-colors`} />
            <input
                ref={ref}
                type={showPassword ? "text" : "password"}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                onFocus={onFocus}
                onBlur={onBlur}
                placeholder={placeholder}
                className="w-full h-full bg-transparent border-none outline-none font-sans pl-4 pr-12 text-base md:text-lg text-black placeholder:text-[#828282] focus:placeholder-transparent transition-colors duration-300"
            />
            <button type="button" onClick={toggleVisibility} className="absolute right-0 top-0 h-full px-4 flex items-center text-gray-500 hover:text-gray-700" aria-label={showPassword ? "Hide password" : "Show password"}>
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
            </button>
        </div>
    );
});

//Dropdown component for selecting user role
interface RoleDropdownProps {
    value: string;
    onChange: (value: string) => void;
    onBlur: () => void;
    options: { value: string; label: string }[];
    hasError?: boolean;
}

const RoleDropdown = forwardRef(({ value, onChange, onBlur, options, hasError = false }: RoleDropdownProps, ref: Ref<HTMLSelectElement>) => {
    const textColorClass = value ? 'text-black' : 'text-[#828282]';
    const errorClasses = hasError ? "border-red-500" : "border-[#e0e0e0]";

    return (
        <div className="relative bg-white box-border flex items-center h-[50px] rounded-[8px] w-full">
            <div aria-hidden="true" className={`absolute border ${errorClasses} border-solid inset-0 pointer-events-none rounded-[8px] transition-colors`} />
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-500 pointer-events-none" />
            <select
                ref={ref}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                onBlur={onBlur}
                disabled={options.length === 0}
                className={`w-full h-full bg-transparent border-none outline-none font-sans px-4 appearance-none text-base md:text-lg ${textColorClass}`}
            >
                <option value="" disabled>
                    select a role...
                </option>
                {options.map((option) => (
                    <option key={option.value} value={option.value} className="text-black bg-white">
                        {option.label}
                    </option>
                ))}
            </select>
        </div>
    );
});

//Reusable button component with loading state and 2 variants
interface ActionButtonProps {
    onClick: () => void;
    children: React.ReactNode;
    variant?: 'primary' | 'secondary';
    isLoading?: boolean;
}

function ActionButton({ onClick, children, variant = 'primary', isLoading = false }: ActionButtonProps) {
    const baseClasses = "box-border cursor-pointer flex h-[50px] items-center justify-center rounded-[8px] w-full transition-colors font-medium";
    const variantClasses = {
        primary: "bg-[#c8102e] hover:bg-[#b00f29] active:bg-[#a00d25] text-white",
        secondary: "bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] text-black"
    };
    return (
        <button 
            onClick={onClick} 
            className={`${baseClasses} ${variantClasses[variant]} ${isLoading ? 'opacity-75 cursor-not-allowed' : ''}`}
            disabled={isLoading}
        >
            {isLoading ? <Loader2 className="animate-spin h-6 w-6" /> : <p className="text-lg md:text-xl">{children}</p>}
        </button>
    );
}

//Button divider component
function Divider() {
  return (
    <div className="flex gap-4 h-[25px] items-center justify-center w-full">
      <div className="grow bg-[#e6e6e6] h-px" />
      <p className="font-sans text-[#828282] text-base md:text-lg">or</p>
      <div className="grow bg-[#e6e6e6] h-px" />
    </div>
  );
}

//Component for the password requirements list
function PasswordRequirements({ password }: { password: string }) {
    const requirements = [
        { text: "At least 8 characters", regex: /.{8,}/ },
        { text: "At least one uppercase letter", regex: /[A-Z]/ },
        { text: "At least one lowercase letter", regex: /[a-z]/ },
        { text: "At least one number", regex: /[0-9]/ },
        { text: "At least one special character (!@#$%^&*.)", regex: /[!@#$%^&*.]/ },
    ];

    return (
        <div className="p-3 bg-gray-50 rounded-md border border-gray-200 mt-2 space-y-1">
            <p className="text-sm font-medium text-gray-700">Password must contain:</p>
            <ul className="text-xs text-gray-600 space-y-1">
                {requirements.map(req => {
                    const meets = req.regex.test(password);
                    return (
                        <li key={req.text} className={`flex items-center transition-colors ${meets ? 'text-green-600' : 'text-gray-500'}`}>
                            {meets ? <CheckCircle2 className="h-4 w-4 mr-2 flex-shrink-0" /> : <XCircle className="h-4 w-4 mr-2 flex-shrink-0" />}
                            <span>{req.text}</span>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}


// Main Register Frame Component
export default function FrameRegister() {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [role, setRole] = useState("");
    const [adminKey, setAdminKey] = useState("");
    const [errors, setErrors] = useState<{ name?: string; email?: string; password?: string; role?: string; adminKey?: string }>({});
    const [touched, setTouched] = useState<{ name?: boolean; email?: boolean; password?: boolean; role?: boolean; adminKey?: boolean }>({});
    const [serverError, setServerError] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [roleOptions, setRoleOptions] = useState<{ value: string; label: string }[]>([]);
    const [isPasswordFocused, setIsPasswordFocused] = useState(false);
    const navigate = useNavigate();

    const nameRef = useRef<HTMLInputElement>(null);
    const emailRef = useRef<HTMLInputElement>(null);
    const passwordRef = useRef<HTMLInputElement>(null);
    const roleRef = useRef<HTMLSelectElement>(null);
    const adminKeyRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
    document.title = "AIloQR - Register";
  }, []);

    //Fetch roles from backend on component mount
    useEffect(() => {
        const fetchRoles = async () => {
            try {
                const response = await fetch(`${API_URL}/api/roles`);
                if (!response.ok) throw new Error('Could not load roles');
                const rolesFromApi: string[] = await response.json();
                const options = rolesFromApi.map(roleName => ({ value: roleName, label: roleName }));
                setRoleOptions(options);
            } catch (err: any) {
                setServerError("Connection Error: Could not load roles.");
            }
        };
        fetchRoles();
    }, []);

    //Password validation function
    const validatePassword = (password: string, checkRequired: boolean = false) => {
        if (!password && checkRequired) return "Password is required.";
        if (password.length > 0 || checkRequired) {
            if (password.length < 8) return "Password must be at least 8 characters long.";
            if (!/[A-Z]/.test(password)) return "Must contain an uppercase letter.";
            if (!/[a-z]/.test(password)) return "Must contain a lowercase letter.";
            if (!/[0-9]/.test(password)) return "Must contain a number.";
            if (!/[!@#$%^&*.]/.test(password)) return "Must contain a special character.";
        }
        return undefined;
    };

    //Validation function for the format of the fields
    const validate = (checkAll = false) => {
        const newErrors: typeof errors = {};
        if (checkAll || touched.name) {
            if (!name) newErrors.name = "Name is required.";
        }
        if (checkAll || touched.email) {
            if (!email) newErrors.email = "Email is required.";
            else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) newErrors.email = "Invalid email format.";
        }
        if (checkAll || touched.password) {
            const passwordError = validatePassword(password, checkAll);
            if(passwordError) newErrors.password = passwordError;
        }
        if (checkAll || touched.role) {
            if (!role) newErrors.role = "Role is required.";
        }
        if (role === 'Admin' && (checkAll || touched.adminKey)) {
            if (!adminKey) newErrors.adminKey = "Admin key is required.";
        }
        return newErrors;
    };
    
    //Re-validate on change, but only for touched fields
    useEffect(() => {
        const newErrors: typeof errors = {};
        if (touched.name && !name) newErrors.name = "Name is required.";
        if (touched.email) {
            if(!email) newErrors.email = "Email is required.";
            else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) newErrors.email = "Invalid email format.";
        }
        if (touched.password && !isPasswordFocused) { //Only show password error if not focused
            newErrors.password = validatePassword(password, true);
        }
        if (touched.role && !role) newErrors.role = "Role is required.";
        if (role === 'Admin' && touched.adminKey && !adminKey) newErrors.adminKey = "Admin key is required.";
        setErrors(newErrors);
    }, [name, email, password, role, adminKey, touched, isPasswordFocused]);

    const handleBlur = (field: 'name' | 'email' | 'password' | 'role' | 'adminKey') => {
        setTouched(prev => ({ ...prev, [field]: true }));
    };

    //Handle registration submission
    const handleRegister = async () => {
        setServerError("");
        setTouched({ name: true, email: true, password: true, role: true, adminKey: true }); //Mark all as touched on submit
        const formErrors = validate(true);
        if (Object.keys(formErrors).length > 0) {
            setErrors(formErrors);
            return;
        }

        setIsLoading(true);
        try {
            const body = JSON.stringify({ name, email, password, role, admin_key: adminKey });

            const response = await fetch(`${API_URL}/api/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: body,
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.message || 'Error during registration');
            //On successful registration, store token and log in
            localStorage.setItem('token', data.token);
            if (data.role === 'Admin') {
                navigate('/admin'); //Navigate to admin panel if admin
            } else {
                navigate('/dashboard'); //Navigate to user dashboard if not admin
            }
        } catch (err: any) {
            setServerError(err.message);
        } finally {
            setIsLoading(false);
        }
    };
    

    //Navigate to login page
    const navigateToLogin = () => navigate('/login');


    //Enter key works as submit
    const handleKeyDown = (event: React.KeyboardEvent) => {
        if (event.key === 'Enter' && !isLoading) handleRegister();

        //Arrow key navigation between inputs
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault(); //Prevent default scrolling behavior

            //Dynamic input list based on role being admin or not
            const inputs = [nameRef, emailRef, passwordRef, roleRef];
            if (role === 'Admin') {
                inputs.push(adminKeyRef);
            }

            //Find current focused element index
            const currentIndex = inputs.findIndex(ref => ref.current === document.activeElement);

            let nextIndex;
            if (event.key === 'ArrowDown') {
                nextIndex = (currentIndex + 1) % inputs.length;
            } else { //ArrowUp
                nextIndex = (currentIndex - 1 + inputs.length) % inputs.length;
            }

            //Focus the next element
            inputs[nextIndex].current?.focus();
        }
    };

    return (
        <div className="w-11/12 max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl flex flex-col items-center gap-4 p-4" onKeyDown={handleKeyDown}>
            {/* TITLES */}
            <div className="text-center mb-4 md:mb-6">
                <p className="font-semibold text-3xl md:text-4xl xl:text-5xl text-black">Register</p>
                <p className="mt-2 font-semibold text-lg md:text-xl xl:text-2xl text-gray-700">Get started with a new account</p>
            </div>

            {/* SERVER ERROR MESSAGE */}
            {serverError && (
                <div className="w-full bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-md text-center mb-2">
                    <p>{serverError}</p>
                </div>
            )}
            
            {/* FORM */}
            <div className="w-full flex flex-col gap-1">
                <div className="flex flex-col mb-2">
                    <Input ref={nameRef} value={name} onChange={setName} onBlur={() => handleBlur('name')} placeholder="Name" type="name" hasError={!!errors.name} />
                    {errors.name && <p className="text-red-500 text-xs mt-1 ml-1">{errors.name}</p>}
                </div>
                <div className="flex flex-col mb-2">
                    <Input ref={emailRef} value={email} onChange={setEmail} onBlur={() => handleBlur('email')} placeholder="email@domain.com" type="email" hasError={!!errors.email} />
                    {errors.email && <p className="text-red-500 text-xs mt-1 ml-1">{errors.email}</p>}
                </div>
                <div className="flex flex-col mb-2">
                    <PasswordInput 
                        ref={passwordRef}
                        value={password} 
                        onChange={setPassword} 
                        onFocus={() => setIsPasswordFocused(true)} 
                        onBlur={() => { handleBlur('password'); setIsPasswordFocused(false); }} 
                        placeholder="password" 
                        hasError={!!errors.password && touched.password}
                    />
                    {errors.password && touched.password && !isPasswordFocused && <p className="text-red-500 text-xs mt-1 ml-1">{errors.password}</p>}
                    {isPasswordFocused && <PasswordRequirements password={password} />}
                </div>
                <div className="flex flex-col">
                    <RoleDropdown ref={roleRef} value={role} onChange={setRole} options={roleOptions} hasError={!!errors.role} onBlur={() => handleBlur('role')} />
                    {errors.role && <p className="text-red-500 text-xs mt-1 ml-1">{errors.role}</p>}
                </div>
                {role === 'Admin' && (
                    <div className="flex flex-col mt-2 transition-all duration-300">
                        <PasswordInput 
                            ref={adminKeyRef}
                            value={adminKey} 
                            onChange={setAdminKey} 
                            onFocus={() => {}}
                            onBlur={() => handleBlur('adminKey')}
                            placeholder="Admin Key"
                            hasError={!!errors.adminKey}
                        />
                        {errors.adminKey && <p className="text-red-500 text-xs mt-1 ml-1">{errors.adminKey}</p>}
                    </div>
                )}
            </div>
            
            {/* ACTION BUTTONS & LEGAL TEXT */}
            <div className="w-full flex flex-col gap-3 md:gap-4 mt-4">
                <ActionButton onClick={handleRegister} variant="primary" isLoading={isLoading}>Register</ActionButton>
                <Divider />
                <ActionButton onClick={navigateToLogin} variant="secondary">Back to Login</ActionButton>
            </div>
            <div className="mt-6 w-full text-center">
                <p className="text-xs md:text-sm text-gray-500">
                    By clicking register, you agree to our{' '}
                    <button type="button" className="font-medium text-black underline-offset-4 hover:underline focus:outline-none">
                        Terms of Service
                    </button>
                    {' '}and{' '}
                    <button type="button" className="font-medium text-black underline-offset-4 hover:underline focus:outline-none">
                        Privacy Policy
                    </button>
                    .
                </p>
            </div>
        </div>
    );
}