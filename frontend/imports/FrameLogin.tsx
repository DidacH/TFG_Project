import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Eye, EyeOff, Loader2 } from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || '';

// Reusable input component 
interface InputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  type?: "text" | "email";
}

function Input({ value, onChange, placeholder, type = "text" }: InputProps) {
  return (
    <div className="relative bg-white box-border flex items-center h-[45px] rounded-[8px] w-full">
      <div aria-hidden="true" className="absolute border border-[#e0e0e0] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full h-full bg-transparent border-none outline-none font-sans px-4
                   text-base md:text-lg text-black 
                   placeholder:text-[#828282] 
                   focus:placeholder-transparent transition-colors duration-300"
      />
    </div>
  );
}

// See/unsee password input component
interface PasswordInputProps {
    value: string;
    onChange: (value: string) => void;
    placeholder: string;
}

function PasswordInput({ value, onChange, placeholder }: PasswordInputProps) {
    const [showPassword, setShowPassword] = useState(false);

    const toggleVisibility = () => {
        setShowPassword(!showPassword);
    };

    return (
        <div className="relative bg-white box-border flex items-center h-[45px] rounded-[8px] w-full">
            <div aria-hidden="true" className="absolute border border-[#e0e0e0] border-solid inset-0 pointer-events-none rounded-[8px]" />
            <input
                type={showPassword ? "text" : "password"}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className="w-full h-full bg-transparent border-none outline-none font-sans pl-4 pr-12
                           text-base md:text-lg text-black 
                           placeholder:text-[#828282] 
                           focus:placeholder-transparent transition-colors duration-300"
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
}

// Reusable button component
interface ActionButtonProps {
    onClick: () => void;
    children: React.ReactNode;
    variant?: 'primary' | 'secondary';
    IsLoading?: boolean;
}

function ActionButton({ onClick, children, variant = 'primary', IsLoading = false }: ActionButtonProps) {
    const baseClasses = "box-border cursor-pointer flex h-[45px] items-center justify-center rounded-[8px] w-full transition-colors font-medium";
    const variantClasses = {
        primary: "bg-[#c8102e] hover:bg-[#b00f29] active:bg-[#a00d25] text-white",
        secondary: "bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] text-black"
    };

    return (
        <button 
          onClick={onClick} 
          className={`${baseClasses} ${variantClasses[variant]} ${IsLoading ? 'opacity-75 cursor-not-allowed' : ''}`}
          disabled={IsLoading} //Disable button while loading
        >
          {IsLoading ? (
                <Loader2 className="animate-spin h-6 w-6" /> //Showing loading icon spinner
            ) : (
                <p className="text-lg md:text-xl">{children}</p>
            )}
        </button>
    );
}

// Divider
function Divider() {
  return (
    <div className="flex gap-4 h-[25px] items-center justify-center w-full" data-name="Divider">
      <div className="grow bg-[#e6e6e6] h-px" />
      <p className="font-sans text-[#828282] text-base md:text-lg">or</p>
      <div className="grow bg-[#e6e6e6] h-px" />
    </div>
  );
}


// Main login frame component
export default function FrameLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();


  const validateEmail = (email: string) => {
    //Regular expression for basic email validation
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  useEffect(() => {
    if (location.state?.message) {
      setSuccessMessage(location.state.message);
      //Clean the state to prevent showing the message again on future visits
      window.history.replaceState({}, document.title)
    }
  }, [location]);

  //Login handler
  const handleContinue = async () => {
    setError(""); //Clean previous errors
    setSuccessMessage(""); //Clean previous success messages

    if (!email || !password) {
      setError("All fields must be filled in.");
      return;
    }

    if (!validateEmail(email)) {
      setError("Invalid email format.");
      return;
    }

    setIsLoading(true); //Start loading state
    try {
      const response = await fetch(`${API_URL}/api/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        //Show error message if there is an error
        throw new Error(data.message || 'Error during login');
      }

      //If login is successful we store the token and navigate to dashboard
      localStorage.setItem('token', data.token); //Store token for future sessions
      navigate('/dashboard'); //Dashboard redirection

    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false); //Finish loading state
    }
  };

  const handleForgotPassword = () => {
    //Forgot password logic here
    console.log("Forgot password clicked");
  };
  
  const navigateToRegister = () => {
      navigate('/register');
  }

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !isLoading) {
      handleContinue();
    }
  };

  return (
    <div className="w-11/12 max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl flex flex-col items-center gap-4 p-4" onKeyDown={handleKeyPress}>
      {/* TITLES */}
      <div className="text-center mb-4 md:mb-6">
        <p className="font-semibold text-3xl md:text-4xl xl:text-5xl text-black">
          Login
        </p>
        <p className="mt-2 font-semibold text-lg md:text-xl xl:text-2xl text-gray-700">
          Enter into your account
        </p>
      </div>

      {/* FORM */}
      <div className="w-full flex flex-col gap-3 md:gap-4">
        <Input value={email} onChange={setEmail} placeholder="email@domain.com" type="email" />
        <PasswordInput value={password} onChange={setPassword} placeholder="password" />
      </div>

      <button
        onClick={handleForgotPassword}
        className="self-start font-light text-sm text-black underline hover:opacity-80 active:opacity-60 transition-opacity mt-1"
      >
        Forgot password?
      </button>

      {/* MESSAGES BLOCK */}
      {error && (
        <div className="w-full bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-md text-center mb-4">
          <p>{error}</p>
        </div>
      )}
      {successMessage && (
        <div className="w-full bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded-md text-center mb-2">
          <p>{successMessage}</p>
        </div>
      )}

      {/* ACTION BUTTONS */}
      <div className="w-full flex flex-col gap-3 md:gap-4 mt-4">
        <ActionButton onClick={handleContinue} variant="primary" IsLoading={isLoading}>
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