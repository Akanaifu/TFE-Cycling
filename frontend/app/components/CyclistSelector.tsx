"use client";

import { useEffect, useState } from "react";
import { cyclistSelectorStyles } from "./pipelineStyles";

interface CyclistSelectorProps {
  onSelectCyclist: (cyclist: string) => void;
  selectedCyclist: string;
  isAdmin: boolean;
  onMaxRideIndexChange?: (max: number) => void;
}

interface CyclistOption {
  value: string;
  label: string;
}

function formatCyclistLabel(cyclist: string): string {
  return (
    cyclist.charAt(0).toUpperCase() +
    cyclist.slice(1).replace("cyclist", "Cycliste ")
  );
}

function normalizeCyclistOption(value: unknown): CyclistOption | null {
  if (typeof value === "string") {
    return {
      value,
      label: formatCyclistLabel(value),
    };
  }

  if (!value || typeof value !== "object") {
    return null;
  }

  const record = value as Record<string, unknown>;
  const cyclistValue = String(record.value ?? record.cyclist ?? "").trim();
  if (!cyclistValue) {
    return null;
  }

  const label = String(
    record.label ?? record.display_name ?? cyclistValue,
  ).trim();
  return {
    value: cyclistValue,
    label: label || formatCyclistLabel(cyclistValue),
  };
}

export default function CyclistSelector({
  onSelectCyclist,
  selectedCyclist,
  isAdmin,
  onMaxRideIndexChange,
}: CyclistSelectorProps) {
  const [cyclists, setCyclists] = useState<CyclistOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCyclists = async () => {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
        const response = await fetch(`${apiUrl}/cyclists/list`, {
          credentials: "include",
        });

        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            throw new Error("Session invalide ou expirée.");
          }
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        const rawCyclists: unknown[] = Array.isArray(data.cyclists)
          ? data.cyclists
          : [];
        const fetchedCyclists = rawCyclists
          .map(normalizeCyclistOption)
          .filter((cyclist): cyclist is CyclistOption => cyclist !== null);
        setCyclists(fetchedCyclists);

        if (fetchedCyclists.length > 0) {
          if (
            !selectedCyclist ||
            !fetchedCyclists.some(
              (cyclist: CyclistOption) => cyclist.value === selectedCyclist,
            )
          ) {
            onSelectCyclist(fetchedCyclists[0].value);
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
  }, [onSelectCyclist, selectedCyclist]);

  useEffect(() => {
    const fetchRideCount = async () => {
      if (!selectedCyclist) {
        return;
      }

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
        const dirPath = `../DB/rides/${selectedCyclist}`;
        const response = await fetch(
          `${apiUrl}/rides/list?dir_path=${encodeURIComponent(dirPath)}`,
          {
            credentials: "include",
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
  }, [onMaxRideIndexChange, selectedCyclist]);

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
              key={cyclist.value}
              value={cyclist.value}
              className={cyclistSelectorStyles.option}
            >
              {cyclist.label}
            </option>
          ))}
        </select>
      ) : (
        <div className={cyclistSelectorStyles.hiddenPlaceholder}></div>
      )}
    </div>
  );
}
