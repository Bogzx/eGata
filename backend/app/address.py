"""Split a Romanian postal address into the parts the forms ask for.

Profiles hold the address as one string (`current_address`, e.g. "Str. Avram
Iancu 5, Cluj-Napoca"), while 17 of the 23 procedures ask for `strada`,
`numar`, `bloc`, `scara`, `etaj`, `apartament`, `localitate`, `judet`, ...
separately — so the agent used to ask a known citizen for their own street.

Conservative by design: a part is returned only when the text says it (a
labelled "bl. B2", "ap. 12", "jud. Cluj", "sector 3", a 6-digit postal code,
the number after the street) or, for the county, when the locality is a
county seat. Nothing is guessed; a missing part is simply asked for.
"""
from __future__ import annotations

import re
import unicodedata

# Keys produced, matching procedure field names.
PARTS = ("strada", "numar", "bloc", "scara", "etaj", "apartament",
         "localitate", "judet", "sector", "cod_postal")

# A label is a word, then a dot or whitespace, so street names that merely
# start like one ("Aprodului", "Blajului", "Etajului") are not mistaken for it.
_SEP = r"(?:\.\s*|\s+)"
_LABELLED: list[tuple[str, re.Pattern[str]]] = [
    ("bloc", re.compile(rf"\b(?:bl|bloc(?:ul)?){_SEP}([A-Za-z0-9][\w/-]*)", re.I)),
    ("scara", re.compile(rf"\b(?:sc|scara){_SEP}([A-Za-z0-9][\w-]*)", re.I)),
    ("etaj", re.compile(rf"\b(?:et|etaj(?:ul)?){_SEP}(parter|[A-Za-z0-9-]+)", re.I)),
    ("apartament", re.compile(rf"\b(?:ap|apt|apartament(?:ul)?){_SEP}([A-Za-z0-9][\w/-]*)", re.I)),
    ("sector", re.compile(rf"\b(?:sect|sector(?:ul)?){_SEP}([1-6])\b", re.I)),
    ("judet", re.compile(rf"\b(?:jud|jude[tț](?:ul)?){_SEP}([^,;]+)", re.I)),
    ("cod_postal", re.compile(r"\b(?:cod\s+po[sș]tal|c\.?\s*p\.?)\s*:?\s*(\d{6})\b|\b(\d{6})\b", re.I)),
    ("numar", re.compile(rf"\b(?:nr|num[aă]r(?:ul)?){_SEP}([0-9]+[A-Za-z]?(?:[/-][0-9A-Za-z]+)?)", re.I)),
]

# "Str." / "Strada" is what the templates already print before {{strada}};
# other street types (Bd., Calea, Aleea, ...) are part of the name.
_STREET_PREFIX = re.compile(r"^(?:str(?:ada)?\.?)\s+", re.I)
_STREET_TYPES = re.compile(
    r"^(?:str(?:ada)?|b(?:ule)?v?d(?:ul)?|b-dul|calea|cal|aleea|al|pia[tț]a|p-[tț]a|splaiul|"
    r"[sș]os(?:eaua)?|intrarea|int|drumul|pasajul|fundătura|fundatura)\b\.?",
    re.I,
)
_LOCALITY_PREFIX = re.compile(
    r"^(?:mun(?:icipiul|\.)?|ora[sș](?:ul)?|com(?:una|\.)?|sat(?:ul)?|loc(?:alitatea|\.)?)\s+",
    re.I,
)
_TRAILING_NUMBER = re.compile(r"\s+([0-9]+[A-Za-z]?(?:[/-][0-9A-Za-z]+)?)$")

# County seat -> county, keyed by diacritic-free lowercase name.
_COUNTY_SEATS = {
    "alba iulia": "Alba", "arad": "Arad", "pitesti": "Argeș", "bacau": "Bacău",
    "oradea": "Bihor", "bistrita": "Bistrița-Năsăud", "botosani": "Botoșani",
    "braila": "Brăila", "brasov": "Brașov", "buzau": "Buzău", "calarasi": "Călărași",
    "resita": "Caraș-Severin", "cluj-napoca": "Cluj", "constanta": "Constanța",
    "sfantu gheorghe": "Covasna", "targoviste": "Dâmbovița", "craiova": "Dolj",
    "galati": "Galați", "giurgiu": "Giurgiu", "targu jiu": "Gorj",
    "miercurea ciuc": "Harghita", "deva": "Hunedoara", "slobozia": "Ialomița",
    "iasi": "Iași", "buftea": "Ilfov", "baia mare": "Maramureș",
    "drobeta-turnu severin": "Mehedinți", "targu mures": "Mureș",
    "piatra neamt": "Neamț", "slatina": "Olt", "ploiesti": "Prahova",
    "zalau": "Sălaj", "satu mare": "Satu Mare", "sibiu": "Sibiu",
    "suceava": "Suceava", "alexandria": "Teleorman", "timisoara": "Timiș",
    "tulcea": "Tulcea", "ramnicu valcea": "Vâlcea", "vaslui": "Vaslui",
    "focsani": "Vrancea", "bucuresti": "București",
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


def parse_ro_address(text: str | None) -> dict[str, str]:
    if not text or not text.strip():
        return {}
    rest = " ".join(text.split())
    out: dict[str, str] = {}

    for key, pattern in _LABELLED:
        m = pattern.search(rest)
        if not m:
            continue
        value = next(g for g in m.groups() if g)
        out[key] = value.strip().rstrip(".")
        rest = rest[: m.start()] + "," + rest[m.end():]

    segments = [s.strip(" .;") for s in rest.split(",")]
    segments = [s for s in segments if s]

    street_idx = next((i for i, s in enumerate(segments) if _STREET_TYPES.match(s)), None)
    if street_idx is not None:
        street = segments.pop(street_idx)
        if "numar" not in out:
            m = _TRAILING_NUMBER.search(street)
            if m:
                out["numar"] = m.group(1)
                street = street[: m.start()]
        street = _STREET_PREFIX.sub("", street).strip()
        if street:
            out["strada"] = street

    for seg in segments:
        if re.search(r"\d", seg) and not _LOCALITY_PREFIX.match(seg):
            continue  # leftovers like a lone number are not a locality
        locality = _LOCALITY_PREFIX.sub("", seg).strip()
        # A bare phrase counts as the locality only in address position
        # (after a recognised street), with an explicit mun./com./sat
        # prefix, or when it is a known county seat.
        if locality and (
            street_idx is not None
            or _LOCALITY_PREFIX.match(seg)
            or _fold(locality) in _COUNTY_SEATS
        ):
            out["localitate"] = locality
            break

    if "judet" not in out and "localitate" in out:
        county = _COUNTY_SEATS.get(_fold(out["localitate"]).replace("–", "-"))
        if county:
            out["judet"] = county
    return out
