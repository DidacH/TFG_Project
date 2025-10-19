import { useNavigate } from "react-router-dom";

export default function FrameDashboard() {
  const navigate = useNavigate();

  const handleLogout = () => {
    // Esborrem el token guardat per tancar la sessió
    localStorage.removeItem("token");
    // Redirigim a la pàgina de login
    navigate("/login");
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4">
      <div className="w-full max-w-2xl p-8 bg-white rounded-xl shadow-md text-center">
        <h1 className="text-3xl md:text-4xl font-bold text-gray-800">
          Benvingut al Dashboard!
        </h1>
        <p className="mt-4 text-lg text-gray-600">
          Has iniciat sessió correctament.
        </p>
        <button
          onClick={handleLogout}
          className="mt-8 px-6 py-3 bg-[#c8102e] text-white font-semibold rounded-lg shadow-md hover:bg-[#b00f29] transition-colors duration-300"
        >
          Tancar Sessió
        </button>
      </div>
    </div>
  );
}
