import { useState, useEffect, useRef, forwardRef, Ref } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Eye, EyeOff, Loader2 } from "lucide-react"; 

const API_URL = import.meta.env.VITE_API_URL || '';

// --- Reusable Components ---

interface InputProps {
  value: string;
  onChange: (value: string) => void;
  onBlur: () => void;
  placeholder: string;
  type?: "text" | "email";
  hasError?: boolean;
}

// Generic input component with dynamic error styling
const Input = forwardRef(({ value, onChange, onBlur, placeholder, type = "text", hasError = false }: InputProps, ref: Ref<HTMLInputElement>) => {
  const errorClasses = hasError ? "border-red-500" : "border-[#e0e0e0]";
  
  return (
    <div className="relative bg-white box-border flex items-center h-[50px] rounded-[8px] w-full">
      <div aria-hidden="true" className={`absolute border ${errorClasses} border-solid inset-0 pointer-events-none rounded-[8px] transition-colors`} />
      <input
        ref={ref}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        className="w-full h-full bg-transparent border-none outline-none font-sans px-4 text-base md:text-lg text-black placeholder:text-[#828282] focus:placeholder-transparent transition-colors duration-300"
      />
    </div>
  );
});

interface PasswordInputProps {
    value: string;
    onChange: (value: string) => void;
    onBlur: () => void;
    placeholder: string;
    hasError?: boolean;
}

// Password input component with visibility toggle
const PasswordInput = forwardRef(({ value, onChange, onBlur, placeholder, hasError = false }: PasswordInputProps, ref: Ref<HTMLInputElement>) => {
    const [showPassword, setShowPassword] = useState(false);
    const errorClasses = hasError ? "border-red-500" : "border-[#e0e0e0]";

    const toggleVisibility = () => setShowPassword(!showPassword);

    return (
        <div className="relative bg-white box-border flex items-center h-[50px] rounded-[8px] w-full">
            <div aria-hidden="true" className={`absolute border ${errorClasses} border-solid inset-0 pointer-events-none rounded-[8px] transition-colors`} />
            <input
                ref={ref}
                type={showPassword ? "text" : "password"}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                onBlur={onBlur}
                placeholder={placeholder}
                className="w-full h-full bg-transparent border-none outline-none font-sans pl-4 pr-12 text-base md:text-lg text-black placeholder:text-[#828282] focus:placeholder-transparent transition-colors duration-300"
            />
            <button
                type="button"
                onClick={toggleVisibility}
                className="absolute right-0 top-0 h-full px-4 flex items-center text-gray-500 hover:text-gray-700"
                aria-label={showPassword ? "Hide password" : "Show password"}
            >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
            </button>
        </div>
    );
});

interface ActionButtonProps {
    onClick: () => void;
    children: React.ReactNode;
    variant?: 'primary' | 'secondary';
    isLoading?: boolean;
    disabled?: boolean;
}

// Main action button with loading spinner integration
function ActionButton({ onClick, children, variant = 'primary', isLoading = false, disabled = false }: ActionButtonProps) {
    const baseClasses = "box-border flex h-[50px] items-center justify-center rounded-[8px] w-full transition-all duration-200 font-medium";
    const variantClasses = {
        primary: "bg-[#c8102e] text-white",
        secondary: "bg-[#eeeeee] text-black"
    };
    
    const isButtonDisabled = isLoading || disabled;

    const stateClasses = isLoading 
        ? "opacity-60 cursor-wait scale-[0.98]" 
        : disabled
            ? "opacity-50 cursor-not-allowed"
            : variant === 'primary' 
                ? "hover:bg-[#b00f29] active:bg-[#a00d25] cursor-pointer shadow-sm hover:shadow" 
                : "hover:bg-[#e0e0e0] active:bg-[#d5d5d5] cursor-pointer";

    return (
        <button 
            type="button"
            onClick={onClick} 
            className={`${baseClasses} ${variantClasses[variant]} ${stateClasses}`}
            disabled={isButtonDisabled}
        >
            {isLoading ? <Loader2 className="animate-spin h-6 w-6" /> : <span className="text-lg md:text-xl">{children}</span>}
        </button>
    );
}

// Visual separator for alternative actions
function Divider() {
  return (
    <div className="flex gap-4 h-[25px] items-center justify-center w-full">
      <div className="grow bg-[#e6e6e6] h-px" />
      <span className="font-sans text-[#828282] text-base md:text-lg">or</span>
      <div className="grow bg-[#e6e6e6] h-px" />
    </div>
  );
}

// --- Main Login Frame Component ---

export default function FrameLogin() {
  // Form state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  
  // Validation state
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [touched, setTouched] = useState<{ email?: boolean; password?: boolean }>({});
  
  // UI feedback state
  const [serverError, setServerError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  const navigate = useNavigate();
  const location = useLocation();

  // Network request controller
  const abortControllerRef = useRef<AbortController | null>(null);

  // Input references for keyboard navigation
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const inputs = [emailRef, passwordRef];

  // Set document title
  useEffect(() => {
    document.title = "AIloQR - Login";
  }, []);

  // Cleanup pending requests on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // Form validation logic
  const validate = () => {
    const newErrors: { email?: string; password?: string } = {};
    if (!email) {
        newErrors.email = "Email is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        newErrors.email = "Invalid email format.";
    }
    if (!password) {
        newErrors.password = "Password is required.";
    }
    return newErrors;
  };
  
  // Real-time validation based on touched fields
  useEffect(() => {
    const newErrors = validate();
    const activeErrors: { email?: string; password?: string } = {};
    if (touched.email) activeErrors.email = newErrors.email;
    if (touched.password) activeErrors.password = newErrors.password;
    setErrors(activeErrors);
  }, [email, password, touched]);

  // Handle successful registration redirects
  useEffect(() => {
    if (location.state?.message) {
      setSuccessMessage(location.state.message);
      setServerError("");
      window.history.replaceState({}, document.title);
    }
  }, [location]);

  const handleBlur = (field: 'email' | 'password') => {
    setTouched(prev => ({ ...prev, [field]: true }));
  };
  
  // Main authentication handler
  const handleContinue = async () => {
    setServerError(""); 
    setSuccessMessage("");
    setTouched({ email: true, password: true }); 

    const formErrors = validate();
    if (Object.keys(formErrors).length > 0) {
      setErrors(formErrors);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    
    try {
      const response = await fetch(`${API_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
        signal: controller.signal
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.message || 'Login failed');
      }
      
      // Store session data
      localStorage.setItem('token', data.token);
      localStorage.setItem('role', data.role);

      // Route based on role
      if (data.role === 'Admin') {
          navigate('/admin');
      } else {
          navigate('/dashboard');
      }
    } catch (err: any) {
      if (err.name === 'AbortError') return; // Ignore aborted requests
      setServerError(err.message);
    } finally {
      if (abortControllerRef.current === controller) {
        setIsLoading(false);
      }
    }
  };

  const handleForgotPassword = () => {
      // Placeholder for future implementation
      console.log("Forgot password clicked");
  };

  const navigateToRegister = () => navigate('/register');

  // Keyboard navigation support
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (isLoading) return;

    if (event.key === 'Enter') {
      handleContinue();
      return;
    }

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault(); 
        const currentIndex = inputs.findIndex(ref => ref.current === document.activeElement);

        let nextIndex;
        if (event.key === 'ArrowDown') {
            nextIndex = (currentIndex + 1) % inputs.length;
        } else { 
            nextIndex = (currentIndex - 1 + inputs.length) % inputs.length;
        }

        inputs[nextIndex].current?.focus();
    }
  };

  return (
    <div className="w-11/12 max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl flex flex-col items-center gap-4 p-4" onKeyDown={handleKeyDown}>
      {/* Header */}
      <div className="text-center mb-4 md:mb-6">
        <h1 className="font-semibold text-3xl md:text-4xl xl:text-5xl text-black">
          Login
        </h1>
        <p className="mt-2 font-semibold text-lg md:text-xl xl:text-2xl text-gray-700">
          Enter into your account
        </p>
      </div>

      {/* Notifications */}
      {successMessage && (
        <div className="w-full bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded-md text-center mb-2">
          <p>{successMessage}</p>
        </div>
      )}
      
      {serverError && (
        <div className="w-full bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-md text-center mb-2 animate-in fade-in zoom-in-95 duration-200">
          <p>{serverError}</p>
        </div>
      )}

      {/* Input Fields */}
      <div className="w-full flex flex-col gap-1">
        <div className="flex flex-col mb-2">
            <Input 
                ref={emailRef}
                value={email} 
                onChange={setEmail} 
                onBlur={() => handleBlur('email')}
                placeholder="email@domain.com" 
                type="email" 
                hasError={!!errors.email}
            />
            {errors.email && <p className="text-red-500 text-xs mt-1 ml-1">{errors.email}</p>}
        </div>
        <div className="flex flex-col">
            <PasswordInput 
                ref={passwordRef}
                value={password} 
                onChange={setPassword} 
                onBlur={() => handleBlur('password')}
                placeholder="password"
                hasError={!!errors.password}
            />
            {errors.password && <p className="text-red-500 text-xs mt-1 ml-1">{errors.password}</p>}
        </div>
      </div>

      {/* Auxiliary Actions */}
      <button
        type="button"
        onClick={handleForgotPassword}
        disabled={isLoading}
        className={`self-start font-light text-sm text-black underline mt-1 transition-opacity ${isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-80 active:opacity-60'}`}
      >
        Forgot password?
      </button>

      {/* Primary Actions */}
      <div className="w-full flex flex-col gap-3 md:gap-4 mt-4">
        <ActionButton onClick={handleContinue} variant="primary" isLoading={isLoading}>
            Continue
        </ActionButton>
        <Divider />
        <ActionButton onClick={navigateToRegister} variant="secondary" disabled={isLoading}>
            Register here
        </ActionButton>
      </div>
    </div>
  );
}