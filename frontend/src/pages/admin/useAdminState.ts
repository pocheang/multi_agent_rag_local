import { useShallow } from "zustand/react/shallow";
import { useAdminStore } from "@/stores/useAdminStore";

export function useAdminState() {
  // See useChatPageState for why this needs useShallow: without it, any field
  // change anywhere in the store re-renders the whole admin page.
  return useAdminStore(useShallow((s) => s));
}
