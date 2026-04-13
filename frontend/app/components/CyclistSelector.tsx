"use client";

import { useEffect, useState } from "react";
import { cyclistSelectorStyles } from "./pipelineStyles";

interface CyclistSelectorProps {
  onSelectCyclist: (cyclist: string) => void;
  selectedCyclist: string;
  authToken: string | null;
  isAdmin: boolean;
  onMaxRideIndexChange?: (max: number) => void;
}

export default function CyclistSelector({
  onSelectCyclist,
  selectedCyclist,
  authToken,
  isAdmin,
  onMaxRideIndexChange,
}: CyclistSelectorProps) {
  const [cyclists, setCyclists] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCyclists = async () => {
      if (!authToken) {
        setCyclists([]);
        setError("Connecte-toi pour charger les cyclistes.");
        return;
      }

      setLoading(true);
      setError(null);
      try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://tfe-cycling.onrender.com";
        const response = await fetch(`${apiUrl}/cyclists/list`, {
          headers: { Authorization: `Bearer ${authToken}` },
        });

        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            throw new Error("Session invalide ou expirée.");
          }
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        const fetchedCyclists = data.cyclists || [];
        setCyclists(fetchedCyclists);

        if (fetchedCyclists.length > 0) {
          if (!selectedCyclist || !fetchedCyclists.includes(selectedCyclist)) {
            onSelectCyclist(fetchedCyclists[0]);
          }
        } else {
          onSelectCyclist("");
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load cyclists",
        );
      } finally {
        setLoading(false);
      }
    };

    fetchCyclists();
  }, [authToken, onSelectCyclist, selectedCyclist]);

  useEffect(() => {
    const fetchRideCount = async () => {
      if (!authToken || !selectedCyclist) {
        return;
      }

      try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://tfe-cycling.onrender.com";
        const dirPath = `../DB/rides/${selectedCyclist}`;
        const response = await fetch(
          `${apiUrl}/rides/list?dir_path=${encodeURIComponent(dirPath)}`,
          {
            headers: { Authorization: `Bearer ${authToken}` },
          },
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        const rideCount = Number(data?.n_rides ?? 0);
        const computedMax = Math.max(
          1,
          Number.isFinite(rideCount) ? rideCount : 1,
        );
        onMaxRideIndexChange?.(computedMax);
      } catch {
        onMaxRideIndexChange?.(1);
      }
    };

    fetchRideCount();
  }, [authToken, onMaxRideIndexChange, selectedCyclist]);

  return (
    <div className={cyclistSelectorStyles.container}>
      <label htmlFor="cyclist-select" className={cyclistSelectorStyles.label}>
        {isAdmin ? "Sélectionner un cycliste" : ""}
      </label>
      {loading ? (
        <div className={cyclistSelectorStyles.loading}>Chargement...</div>
      ) : error ? (
        <div className={cyclistSelectorStyles.error}>{error}</div>
      ) : isAdmin ? (
        <select
          id="cyclist-select"
          value={selectedCyclist}
          onChange={(e) => onSelectCyclist(e.target.value)}
          className={cyclistSelectorStyles.select}
        >
          {cyclists.map((cyclist) => (
            <option
              key={cyclist}
              value={cyclist}
              className={cyclistSelectorStyles.option}
            >
              {cyclist.charAt(0).toUpperCase() +
                cyclist.slice(1).replace("cyclist", "Cycliste ")}
            </option>
          ))}
        </select>
      ) : (
        <div className={cyclistSelectorStyles.hiddenPlaceholder}></div>
      )}
    </div>
  );
}
