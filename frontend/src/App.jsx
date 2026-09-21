import { Route, Routes } from "react-router-dom";
import SignupPage from "./pages/SignupPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import ProtectedPage from "./pages/ProtectedPage.jsx";
import { useSession } from "./useSession.js";

export default function App() {
  const [session, setSession] = useSession();

  return (
    <Routes>
      {/* The landing page is the thing the subject actually wanted. With no
          session that produces the RP's 401 - Figure 3 step 3 - rather than a
          login form the browser decided to show on its own. */}
      <Route
        path="/"
        element={<ProtectedPage session={session} onLogout={() => setSession(null)} />}
      />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/login" element={<LoginPage onLogin={setSession} />} />
      <Route
        path="/protected"
        element={<ProtectedPage session={session} onLogout={() => setSession(null)} />}
      />
    </Routes>
  );
}
