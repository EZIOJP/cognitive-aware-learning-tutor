import { Link } from "react-router";
import { AddWordsJson } from "../../features/vocab/components/AddWordsJson";

export function AddWordsPage() {
  return (
    <div className="h-full overflow-y-auto p-4">
      <Link to="/gre-vocab" className="text-sm text-primary hover:underline mb-4 inline-block">
        ← GRE Vocabulary
      </Link>
      <AddWordsJson />
    </div>
  );
}
