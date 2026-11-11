"""Understanding what a client types in the search box. Pure functions, no AI needed.

"barber shop near me" -> category "barber", near_me=True, words ["barber", "shop"]
"""
import re
from dataclasses import dataclass

# Words that point to a category. Matching is on whole words, lowercase.
CATEGORY_WORDS = {
    "barber": {"barber", "barbers", "barbershop", "barbershops", "haircut", "haircuts", "shave", "beard", "fade"},
    "salon": {"salon", "salons", "hairdresser", "hairdressers", "parlour", "parlor", "hair", "blowdry", "colour", "color"},
    "nail_studio": {"nail", "nails", "manicure", "pedicure", "gel", "acrylic"},
    "personal_trainer": {"trainer", "trainers", "pt", "coach", "gym", "workout"},
    "tutor": {"tutor", "tutors", "tuition", "tutoring", "lessons", "teacher", "coaching"},
    "therapist": {"therapist", "therapy", "counsellor", "counselor", "massage", "physio", "physiotherapy"},
    "fitness_class": {"yoga", "pilates", "zumba", "class", "classes", "dance"},
    "home_services": {"plumber", "electrician", "cleaner", "cleaning", "carpenter", "repair"},
    "photographer": {"photographer", "photography", "photoshoot", "photo"},
}
NEAR_ME = {"near", "nearby", "around", "close", "me", "closest", "nearest"}
FILLER = {"a", "an", "the", "in", "at", "for", "to", "of", "and", "best", "good", "top", "shop", "shops",
          "studio", "studios", "place", "places", "service", "services", "find", "book", "want", "need", "i"}


@dataclass(frozen=True)
class SearchIntent:
    category: str | None
    near_me: bool
    words: tuple[str, ...]      # meaningful words left over, to match names and services


def understand(query: str) -> SearchIntent:
    words = re.findall(r"[a-z0-9]+", (query or "").lower())
    near_me = bool({"near", "nearby", "closest", "nearest", "around"} & set(words))
    scores = {cat: sum(w in vocab for w in words) for cat, vocab in CATEGORY_WORDS.items()}
    best = max(scores, key=scores.get)
    category = best if scores[best] > 0 else None
    meaningful = tuple(w for w in words if w not in NEAR_ME and w not in FILLER and len(w) > 1)
    return SearchIntent(category=category, near_me=near_me, words=meaningful)