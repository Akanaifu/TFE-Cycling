"use client";

interface RideData {
  datetime: string;
  n_points: number;
  columns: string[];
  data: Record<string, unknown>[];
}

export default function RideSelector({
  rides,
  selectedIndex,
  onSelectRide,
}: {
  rides: RideData[];
  selectedIndex: number;
  onSelectRide: (index: number) => void;
}) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Sélectionner une ride
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {rides.map((ride, idx) => (
          <button
            key={`${ride.datetime}-${ride.n_points}`}
            type="button"
            onClick={() => onSelectRide(idx)}
            className={`p-4 rounded-lg border-2 transition-all text-left ${
              selectedIndex === idx
                ? "border-blue-600 bg-blue-50"
                : "border-gray-200 hover:border-gray-300 bg-white"
            }`}
          >
            <p className="font-semibold text-gray-900">Ride {idx + 1}</p>
            <p className="text-sm text-gray-600">{ride.datetime}</p>
            <p className="text-xs text-gray-500 mt-1">{ride.n_points} points</p>
          </button>
        ))}
      </div>
    </div>
  );
}
