import { useState, useCallback } from "react";

/**
 * Hook to handle plan limit errors (402 responses).
 * Returns: { upgradeOpen, upgradeMessage, handleApiError, closeUpgrade }
 * Usage: call handleApiError(error) in catch blocks, render UpgradeDialog with upgradeOpen/upgradeMessage
 */
export function useUpgradeDialog() {
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [upgradeMessage, setUpgradeMessage] = useState("");

  const handleApiError = useCallback((error, fallbackMessage) => {
    if (error?.response?.status === 402) {
      setUpgradeMessage(error.response?.data?.detail || "Limite do plano atingido. Faça upgrade.");
      setUpgradeOpen(true);
      return true; // handled
    }
    return false; // not a plan limit error
  }, []);

  const closeUpgrade = useCallback(() => {
    setUpgradeOpen(false);
    setUpgradeMessage("");
  }, []);

  return { upgradeOpen, upgradeMessage, handleApiError, closeUpgrade };
}
