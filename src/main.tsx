
import { createRoot } from "react-dom/client";
import App from "./app/App.tsx";
import { installClientErrorLogger } from "./api/systemClient";
import "./styles/index.css";

installClientErrorLogger();

createRoot(document.getElementById("root")!).render(<App />);