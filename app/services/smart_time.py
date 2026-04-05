from dataclasses import dataclass


@dataclass
class ActivityTimeProfile:
    """Defines when an activity is appropriate to schedule."""
    earliest_hour: int
    latest_hour: int
    preferred_duration_minutes: int
    prefer_weekends: bool
    category: str


ACTIVITY_PROFILES = {
    # Outdoor sports
    "pickleball": ActivityTimeProfile(9, 17, 90, True, "outdoor"),
    "tennis": ActivityTimeProfile(8, 18, 90, True, "outdoor"),
    "golf": ActivityTimeProfile(7, 16, 240, True, "outdoor"),
    "hiking": ActivityTimeProfile(7, 15, 180, True, "outdoor"),
    "running": ActivityTimeProfile(6, 19, 60, False, "outdoor"),
    "soccer": ActivityTimeProfile(9, 18, 90, True, "outdoor"),
    "basketball": ActivityTimeProfile(9, 21, 90, True, "outdoor"),

    # Fitness
    "gym": ActivityTimeProfile(5, 21, 60, False, "fitness"),
    "workout": ActivityTimeProfile(5, 21, 60, False, "fitness"),
    "yoga": ActivityTimeProfile(6, 20, 60, False, "fitness"),
    "crossfit": ActivityTimeProfile(5, 19, 60, False, "fitness"),
    "swimming": ActivityTimeProfile(6, 20, 60, False, "fitness"),

    # Social
    "dinner": ActivityTimeProfile(18, 21, 120, False, "social"),
    "lunch": ActivityTimeProfile(11, 14, 90, False, "social"),
    "brunch": ActivityTimeProfile(9, 13, 120, True, "social"),
    "coffee": ActivityTimeProfile(8, 17, 60, False, "social"),
    "drinks": ActivityTimeProfile(17, 22, 120, False, "social"),
    "happy hour": ActivityTimeProfile(16, 19, 120, False, "social"),
    "party": ActivityTimeProfile(18, 23, 180, True, "social"),
    "hangout": ActivityTimeProfile(10, 22, 120, True, "social"),

    # Work
    "meeting": ActivityTimeProfile(9, 17, 30, False, "work"),
    "standup": ActivityTimeProfile(9, 11, 15, False, "work"),
    "1:1": ActivityTimeProfile(9, 17, 30, False, "work"),
    "interview": ActivityTimeProfile(9, 17, 60, False, "work"),
    "review": ActivityTimeProfile(9, 17, 60, False, "work"),

    # Flexible
    "study": ActivityTimeProfile(8, 22, 120, False, "flexible"),
    "errands": ActivityTimeProfile(9, 18, 60, False, "flexible"),
    "appointment": ActivityTimeProfile(8, 18, 60, False, "flexible"),
}


def get_activity_profile(activity_name: str) -> ActivityTimeProfile:
    """Get time constraints for an activity. Fuzzy matches against profiles."""
    activity_lower = activity_name.lower().strip()

    if activity_lower in ACTIVITY_PROFILES:
        return ACTIVITY_PROFILES[activity_lower]

    for key, profile in ACTIVITY_PROFILES.items():
        if key in activity_lower or activity_lower in key:
            return profile

    return ActivityTimeProfile(8, 21, 60, False, "flexible")


def rank_time_slots(slots: list[dict], profile: ActivityTimeProfile) -> list[dict]:
    """Rank available time slots based on activity profile preferences. Returns top 3."""
    from datetime import datetime

    def score_slot(slot):
        start = datetime.fromisoformat(slot["start"])
        hour = start.hour
        is_weekend = start.weekday() >= 5

        score = 0
        mid_hour = (profile.earliest_hour + profile.latest_hour) / 2
        hour_distance = abs(hour - mid_hour)
        score -= hour_distance * 2

        if profile.prefer_weekends and is_weekend:
            score += 10

        days_from_now = (start - datetime.now(start.tzinfo)).days
        score -= days_from_now * 0.5

        return score

    ranked = sorted(slots, key=score_slot, reverse=True)
    return ranked[:3]
