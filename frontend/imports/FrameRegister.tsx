import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Eye, EyeOff } from "lucide-react";


// Reusable input component
interface InputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  type?: "text" | "email" | "name";
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

// Role dropdown component
interface RoleDropdownProps {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}

function RoleDropdown({ value, onChange, options }: RoleDropdownProps) {
  const textColorClass = value ? 'text-black' : 'text-[#828282]';

  return (
    <div className="relative bg-white box-border flex items-center h-[45px] rounded-[8px] w-full">
      <div aria-hidden="true" className="absolute border border-[#e0e0e0] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-500 pointer-events-none" />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full h-full bg-transparent border-none outline-none font-sans px-4 appearance-none 
                   text-base md:text-lg 
                   ${textColorClass}`}
      >
        <option value="" disabled>select a role...</option>
        {options.map((option) => (
          <option key={option.value} value={option.value} className="text-black bg-white">
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

// Reusable button component
interface ActionButtonProps {
    onClick: () => void;
    children: React.ReactNode;
    variant?: 'primary' | 'secondary';
}

function ActionButton({ onClick, children, variant = 'primary' }: ActionButtonProps) {
    const baseClasses = "box-border cursor-pointer flex h-[50px] items-center justify-center rounded-[8px] w-full transition-colors font-medium";
    const variantClasses = {
        primary: "bg-[#c8102e] hover:bg-[#b00f29] active:bg-[#a00d25] text-white", //primary button
        secondary: "bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] text-black" //secondary button
    };

    return (
        <button onClick={onClick} className={`${baseClasses} ${variantClasses[variant]}`}>
             <p className="text-lg md:text-xl">{children}</p>
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


// Main Register Frame Component
export default function FrameRegister() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("");
  const navigate = useNavigate();

  const roleOptions = [
    { value: "student", label: "Student" },
    { value: "teacher", label: "Teacher" },
    { value: "admin", label: "Administrator" },
  ];

  const handleRegister = () => {
    //Registration logic
    console.log({ name, email, password, role });
  };
  
  const navigateToLogin = () => {
      navigate('/login');
  }

  return (
    <div className="w-11/12 max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl flex flex-col items-center gap-4 p-4">
      {/* TITLES */}
      <div className="text-center mb-4 md:mb-6">
        <p className="font-semibold text-3xl md:text-4xl xl:text-5xl text-black">
          Register
        </p>
        <p className="mt-2 font-semibold text-lg md:text-xl xl:text-2xl text-gray-700">
          Get started with a new account
        </p>
      </div>

      {/* FORM */}
      <div className="w-full flex flex-col gap-3 md:gap-4">
        <Input value={name} onChange={setName} placeholder="name" type="name" />
        <Input value={email} onChange={setEmail} placeholder="email@domain.com" type="email" />
        <PasswordInput value={password} onChange={setPassword} placeholder="password" />
        <RoleDropdown value={role} onChange={setRole} options={roleOptions} />
      </div>

      {/* ACTION BUTTONS */}
      <div className="w-full flex flex-col gap-3 md:gap-4 mt-4">
        <ActionButton onClick={handleRegister} variant="primary">
            Register
        </ActionButton>
        <Divider />
        <ActionButton onClick={navigateToLogin} variant="secondary">
            Back to Login
        </ActionButton>
      </div>
    </div>
  );
}