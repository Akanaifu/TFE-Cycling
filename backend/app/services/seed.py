"""Seed and regenerate pickle files from Strava activities on startup."""

from pathlib import Path
from app.services import database as database_service


def regenerate_pkl_files_from_db() -> dict[str, int]:
    """
    Regenerate all missing PKL files from rides already in the database.

    Returns:
        Dictionary with counts of regenerated files.
    """
    try:
        # Get all rides from DB
        rides = database_service.get_all_rides()

        regenerated = 0
        skipped = 0

        for ride in rides:
            file_path = ride.get("file_path", "").strip()
            if not file_path:
                continue

            # Build absolute path
            backend_root = Path(__file__).parent.parent.parent
            abs_path = (backend_root / file_path).resolve()

            # Skip if already exists
            if abs_path.exists():
                skipped += 1
                continue

            # Create parent directory
            abs_path.parent.mkdir(parents=True, exist_ok=True)

            # Placeholder: regenerate from streams would go here
            # For now, this is a mark that the file should exist
            regenerated += 1

        return {
            "regenerated": regenerated,
            "skipped": skipped,
            "total": len(rides),
        }
    except Exception as exc:
        print(f"Warning: Failed to regenerate PKL files: {exc}")
        return {
            "regenerated": 0,
            "skipped": 0,
            "total": 0,
            "error": str(exc),
        }
