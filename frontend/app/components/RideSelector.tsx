"use client";

interface RideData {
  datetime: string;
  n_points: number;
  columns: string[];
  data: Record<string, unknown>[];
}

function sec2min(nbPoint: number) {
  const hours = Math.floor(nbPoint / 3600);
  const minute = Math.floor((nbPoint % 3600) / 60);
  const seconde_remain = (nbPoint % 3600) % 60;
  return [hours, minute, seconde_remain];
}

function displayTime(nbPoint: number) {
  const heures = sec2min(nbPoint)[0];
  const minutes = sec2min(nbPoint)[1];
  const secondes = sec2min(nbPoint)[2];
  return `${heures}:${minutes}:${secondes}`;
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
    <div className="rounded-2xl border border-[#003566]/70 bg-[#001d3d]/88 p-6 shadow-[0_20px_50px_rgba(0,0,0,0.28)]">
      <h3 className="mb-4 text-lg font-semibold text-[#ffd60a]">
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
                ? "border-[#ffc300] bg-[#003566]/70"
                : "border-[#003566] bg-[#000814]/50 hover:border-[#ffc300]/40"
            }`}
          >
            <p className="font-semibold text-[#fff8d6]">Ride {idx + 1}</p>
            <p className="text-sm text-[#dbeafe]/80">{ride.datetime}</p>
            <p className="mt-1 text-xs text-[#9fb4d2]">
              {displayTime(ride.n_points)}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}
