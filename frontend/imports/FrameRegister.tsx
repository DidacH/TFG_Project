import { useState } from "react";

interface EmailProps {
  value: string;
  onChange: (value: string) => void;
}

function Email({ value, onChange }: EmailProps) {
  return (
    <div className="relative bg-white box-border content-stretch flex gap-[16px] h-[45px] items-center justify-center px-[16px] py-[8px] rounded-[8px] w-full" data-name="email">
      <div aria-hidden="true" className="absolute border border-[#e0e0e0] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <input
        type="email"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="email@domain.com"
        className="w-full h-full bg-transparent border-none outline-none font-regular text-[18px] text-black placeholder:text-[#828282] focus:placeholder-transparent transition-colors duration-300"
      />
    </div>
  );
}

interface PasswordProps {
  value: string;
  onChange: (value: string) => void;
}

function Password({ value, onChange }: PasswordProps) {
  return (
    <div className="relative bg-white box-border content-stretch flex gap-[16px] h-[45px] items-center justify-center px-[16px] py-[8px] rounded-[8px] w-full" data-name="password">
      <div aria-hidden="true" className="absolute border border-[#e0e0e0] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="password"
        className="w-full h-full bg-transparent border-none outline-none font-regular text-[18px] text-black placeholder:text-[#828282] focus:placeholder-transparent transition-colors duration-300"
      />
    </div>
  );
}

interface ContinueButtonProps {
  onClick: () => void;
}

function ContinueButton({ onClick }: ContinueButtonProps) {
  return (
    <button
      onClick={onClick}
      className="bg-[#c8102e] hover:bg-[#b00f29] active:bg-[#a00d25] box-border content-stretch cursor-pointer flex gap-[8px] h-[50px] items-center justify-center px-[16px] py-0 rounded-[8px] w-full transition-colors"
      data-name="Continue button"
    >
      <div className="font-medium font-medium text-[20px] text-nowrap text-white">
        <p>Continue</p>
      </div>
    </button>
  );
}

function Divider() {
  return (
    <div className="flex gap-[4px] h-[25px] items-center justify-center w-full" data-name="Divider">
      <div className="grow bg-[#e6e6e6] h-px" data-name="Divider" />
      <p className="font-['Inter:Regular',_sans-serif] font-normal text-[#828282] text-[18px] text-center">or</p>
      <div className="grow bg-[#e6e6e6] h-px" data-name="Divider" />
    </div>
  );
}

interface RegisterButtonProps {
  onClick: () => void;
}

function RegisterButton({ onClick }: RegisterButtonProps) {
  return (
    <button
      onClick={onClick}
      className="bg-[#eeeeee] hover:bg-[#e0e0e0] active:bg-[#d5d5d5] box-border content-stretch cursor-pointer flex gap-[8px] h-[50px] items-center justify-center px-[16px] py-0 rounded-[8px] w-full transition-colors"
      data-name="Register button"
    >
      <div className="font-medium font-medium text-[20px] text-black text-nowrap">
        <p>Register here</p>
      </div>
    </button>
  );
}

export default function FrameRegister() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleContinue = async () => {
    // ... lògica de login ...
  };

  const handleRegister = () => {
    // ... lògica de registre ...
  };

  const handleForgotPassword = () => {
    // ... lògica de contrasenya oblidada ...
  };

  return (
    //MAIN CONTAINER:
    <div className="w-11/12 max-w-xs md:max-w-md lg:max-w-lg flex flex-col items-center gap-4 p-4">
      
      {/* TITLES: */}
      <div className="text-center mb-4 md:mb-6">
        {/* - Mobile: text-3xl */}
        {/* - Tablet and higher: text-4xl */}
        <p className="font-semi-bold font-semibold text-3xl md:text-4xl text-black">Login</p>
        
        {/* - Mobile: text-lg (large) */}
        {/* - Tablet and higher: text-2xl */}
        <p className="mt-2 font-semi-bold font-semibold text-lg md:text-2xl text-gray-700">
          Enter into your account
        </p>
      </div>

      {/* FORM: */}
      {/* - Mobile: Gap between elements of 3 (gap-3) */}
      {/* - Tablet and higher: Gap of 4 (md:gap-4) */}
      <div className="w-full flex flex-col gap-3 md:gap-4">
        <Email value={email} onChange={setEmail} />
        <Password value={password} onChange={setPassword} />
      </div>

      <button
        onClick={handleForgotPassword}
        className="self-start font-light font-light text-sm text-black underline hover:opacity-80 active:opacity-60 transition-opacity"
      >
        Forgot password?
      </button>

      {/* ACTION BUTTONS: */}
      {/* - Mobile: Upper margin of 1 (mt-1) */}
      {/* - Tablet and higher: Upper margin of 2 (md:mt-2) */}
      <div className="w-full flex flex-col gap-3 md:gap-4 mt-1 md:mt-2">
        <ContinueButton onClick={handleContinue} />
        <Divider />
        <RegisterButton onClick={handleRegister} />
      </div>

    </div>
  );
}