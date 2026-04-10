"use client";

import React, { useEffect, useState } from "react";

interface CyclistSelectorProps {
  onSelectCyclist: (cyclist: string) => void;
  fromRideIndex: number;
  onRideIndexChange: (index: number) => void;
  selectedCyclist: string;
}

export default function CyclistSelector({
  onSelectCyclist,
  fromRideIndex,
  onRideIndexChange,
  selectedCyclist,
}: CyclistSelectorProps) {
  const [cyclists, setCyclists] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCyclists = async () => {
      setLoading(true);
      setError(null);
      try {
        const apiUrl =
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(`${apiUrl}/cyclists/list`);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        setCyclists(data.cyclists || []);

        // Select first cyclist by default
        if (data.cyclists && data.cyclists.length > 0) {
          onSelectCyclist(data.cyclists[0]);
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
  }, [onSelectCyclist]);

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-4">
      <h2 className="text-2xl font-bold text-gray-900">Configuration</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Cyclist Selector */}
        <div>
          <label className="block text-sm font-semibold text-gray-900 mb-2">
            Sélectionner un cycliste
          </label>
          {loading ? (
            <div className="text-gray-500 text-sm">Chargement...</div>
          ) : error ? (
            <div className="text-red-500 text-sm">{error}</div>
          ) : (
            <select
              value={selectedCyclist}
              onChange={(e) => onSelectCyclist(e.target.value)}
              className="w-full px-3 py-2 bg-white text-gray-950 border-2 border-gray-500 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-700"
            >
              {cyclists.map((cyclist) => (
                <option
                  key={cyclist}
                  value={cyclist}
                  className="text-gray-950 bg-white"
                >
                  {cyclist.charAt(0).toUpperCase() +
                    cyclist.slice(1).replace("cyclist", "Cycliste ")}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Training Ride Index Selector */}
        <div>
          <label className="block text-sm font-semibold text-gray-900 mb-2">
            Ride d&apos;entraînement (index, 1-based)
          </label>
          <input
            type="number"
            min="1"
            max="20"
            value={fromRideIndex}
            onChange={(e) => onRideIndexChange(parseInt(e.target.value))}
            className="w-full px-3 py-2 bg-white text-gray-950 border-2 border-gray-500 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-700"
          />
          <p className="text-xs text-gray-500 mt-1">
            Cette ride sera utilisée comme modèle pour les prédictions
          </p>
        </div>
      </div>
    </div>
  );
}
