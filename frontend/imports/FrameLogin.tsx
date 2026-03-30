import { useState, useEffect, useRef, forwardRef, Ref } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Eye, EyeOff, Loader2 } from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || '';

// Reusable Components


//Generic input component
//Used for email and name fields
interface InputProps {
  value: string;
  onChange: (value: string) => void;
  onBlur: () => void; //To track when the user leaves the field
  placeholder: string;
  type?: "text" | "email";
  hasError?: boolean; //To apply red border on error
}

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

// Password specific input component with visibility toggle
interface PasswordInputProps {
    value: string;
    onChange: (value: string) => void;
    onBlur: () => void;
    placeholder: string;
    hasError?: boolean;
}

const PasswordInput = forwardRef(({ value, onChange, onBlur, placeholder, hasError = false }: PasswordInputProps, ref: Ref<HTMLInputElement>) => {
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

//Divider
function Divider() {
  return (
    <div className="flex gap-4 h-[25px] items-center justify-center w-full">
      <div className="grow bg-[#e6e6e6] h-px" />
      <p className="font-sans text-[#828282] text-base md:text-lg">or</p>
      <div className="grow bg-[#e6e6e6] h-px" />
    </div>
  );
}


// Main Login Frame Component
export default function FrameLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  
  //State for individual field errors
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  //State to track which fields have been touched
  const [touched, setTouched] = useState<{ email?: boolean; password?: boolean }>({});
  
  const [serverError, setServerError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const inputs = [emailRef, passwordRef];

  useEffect(() => {
    document.title = "AIloQR - Login";
  }, []);

  const validate = () => {
    const newErrors: { email?: string; password?: string } = {};
    if (!email) newErrors.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) newErrors.email = "Invalid email format.";
    if (!password) newErrors.password = "Password is required.";
    return newErrors;
  };
  
  //Re-validate on change, but only for touched fields
  useEffect(() => {
    const newErrors = validate();
    const activeErrors: { email?: string; password?: string } = {};
    if (touched.email) activeErrors.email = newErrors.email;
    if (touched.password) activeErrors.password = newErrors.password;
    setErrors(activeErrors);
  }, [email, password, touched]);

  useEffect(() => {
    if (location.state?.message) {
      setSuccessMessage(location.state.message);
      setServerError("");
      window.history.replaceState({}, document.title)
    }
  }, [location]);

  const handleBlur = (field: 'email' | 'password') => {
    setTouched(prev => ({ ...prev, [field]: true }));
  };
  
  //Handle form submission
  const handleContinue = async () => {
    setServerError(""); 
    setSuccessMessage("");
    setTouched({ email: true, password: true }); //Mark all as touched on submit

    const formErrors = validate();
    if (Object.keys(formErrors).length > 0) {
      setErrors(formErrors);
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || 'Login failed');
      }
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

  //Handle forgot password click
  const handleForgotPassword = () => console.log("Forgot password clicked");

  //Navigate to register page
  const navigateToRegister = () => navigate('/register');

  //Enter key works as submit
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !isLoading) {
      handleContinue();
    }

    //Arrow key navigation between inputs
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault(); //Prevent default scrolling behavior
        const currentIndex = inputs.findIndex(ref => ref.current === document.activeElement);

        let nextIndex;
        if (event.key === 'ArrowDown') {
            nextIndex = (currentIndex + 1) % inputs.length;
        } else { //ArrowUp
            nextIndex = (currentIndex - 1 + inputs.length) % inputs.length;
        }

        inputs[nextIndex].current?.focus();
    }
  };

  return (
    <div className="w-11/12 max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl flex flex-col items-center gap-4 p-4" onKeyDown={handleKeyDown}>
      {/* TITLES */}
      <div className="text-center mb-4 md:mb-6">
        <p className="font-semibold text-3xl md:text-4xl xl:text-5xl text-black">
          Login
        </p>
        <p className="mt-2 font-semibold text-lg md:text-xl xl:text-2xl text-gray-700">
          Enter into your account
        </p>
      </div>

      {/* GLOBAL MESSAGES */}
      {successMessage && (
        <div className="w-full bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded-md text-center mb-2">
          <p>{successMessage}</p>
        </div>
      )}
      {serverError && (
        <div className="w-full bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-md text-center mb-2">
          <p>{serverError}</p>
        </div>
      )}

      {/* FORM */}
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

      {/* FORGOT PASSWORD */}
      <button
        onClick={handleForgotPassword}
        className="self-start font-light text-sm text-black underline hover:opacity-80 active:opacity-60 transition-opacity mt-1"
      >
        Forgot password?
      </button>

      {/* ACTION BUTTONS */}
      <div className="w-full flex flex-col gap-3 md:gap-4 mt-4">
        <ActionButton onClick={handleContinue} variant="primary" isLoading={isLoading}>
            Continue
        </ActionButton>
        <Divider />
        <ActionButton onClick={navigateToRegister} variant="secondary">
            Register here
        </ActionButton>
      </div>
    </div>
  );
}