import { useNavigate } from "react-router-dom";
import { useCallback } from "react";

export default function FrameAdmin() {
  const navigate = useNavigate();

  //Logout handler
  const handleLogout = useCallback(() => {
    //Remove the authentication token
    localStorage.removeItem("token");
    //Navigate to login
    navigate("/login");
  }, [navigate]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4">
      <div className="w-full max-w-2xl p-8 bg-white rounded-xl shadow-md text-center">
        <h1 className="text-3xl md:text-4xl font-bold text-gray-800">
          Welcome to the Admin page!
        </h1>
        <p className="mt-4 text-lg text-gray-600">
          You logged in successfully.
        </p>
        <button
          onClick={handleLogout}
          className="mt-8 px-6 py-3 bg-[#c8102e] text-white font-semibold rounded-lg shadow-md hover:bg-[#b00f29] transition-colors duration-300"
        >
          Log Out
        </button>
      </div>
    </div>
  );
}