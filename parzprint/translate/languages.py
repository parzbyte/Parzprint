"""Idiomas do Google Tradutor, com nomes em português do Brasil."""

from __future__ import annotations

import unicodedata

AUTO = "auto"
MAX_RECENT = 5

_RAW = (
    ("af", "Africâner"), ("sq", "Albanês"), ("de", "Alemão"), ("am", "Amárico"),
    ("ar", "Árabe"), ("hy", "Armênio"), ("as", "Assamês"), ("ay", "Aimará"),
    ("az", "Azerbaijano"), ("bm", "Bambara"), ("eu", "Basco"), ("bn", "Bengali"),
    ("be", "Bielorrusso"), ("bho", "Bhojpuri"), ("bs", "Bósnio"), ("bg", "Búlgaro"),
    ("my", "Birmanês"), ("kn", "Canarês"), ("ca", "Catalão"), ("ceb", "Cebuano"),
    ("cs", "Tcheco"), ("zh-CN", "Chinês (simplificado)"), ("zh-TW", "Chinês (tradicional)"),
    ("si", "Cingalês"), ("ko", "Coreano"), ("co", "Corso"), ("ht", "Crioulo haitiano"),
    ("hr", "Croata"), ("ku", "Curdo (kurmanji)"), ("ckb", "Curdo (sorani)"),
    ("da", "Dinamarquês"), ("dv", "Divehi"), ("doi", "Dogri"), ("sk", "Eslovaco"),
    ("sl", "Esloveno"), ("es", "Espanhol"), ("eo", "Esperanto"), ("et", "Estoniano"),
    ("ee", "Eve"), ("fi", "Finlandês"), ("fr", "Francês"), ("fy", "Frísio"),
    ("gd", "Gaélico escocês"), ("gl", "Galego"), ("cy", "Galês"), ("ka", "Georgiano"),
    ("el", "Grego"), ("gn", "Guarani"), ("gu", "Guzerate"), ("ha", "Hauçá"),
    ("haw", "Havaiano"), ("iw", "Hebraico"), ("hi", "Hindi"), ("hmn", "Hmong"),
    ("hu", "Húngaro"), ("yo", "Iorubá"), ("id", "Indonésio"), ("en", "Inglês"),
    ("ig", "Igbo"), ("ilo", "Ilocano"), ("ga", "Irlandês"), ("is", "Islandês"),
    ("it", "Italiano"), ("ja", "Japonês"), ("jv", "Javanês"), ("kk", "Cazaque"),
    ("km", "Khmer"), ("rw", "Quiniaruanda"), ("gom", "Concani"), ("kri", "Krio"),
    ("ky", "Quirguiz"), ("lo", "Laosiano"), ("la", "Latim"), ("lv", "Letão"),
    ("ln", "Lingala"), ("lt", "Lituano"), ("lg", "Luganda"), ("lb", "Luxemburguês"),
    ("mk", "Macedônio"), ("mai", "Maithili"), ("ml", "Malaiala"), ("ms", "Malaio"),
    ("mg", "Malgaxe"), ("mt", "Maltês"), ("mi", "Maori"), ("mr", "Marati"),
    ("mni-Mtei", "Meitei (manipuri)"), ("lus", "Mizo"), ("mn", "Mongol"),
    ("ne", "Nepalês"), ("no", "Norueguês"), ("ny", "Nianja"), ("or", "Odia (oriá)"),
    ("om", "Oromo"), ("nl", "Holandês"), ("ps", "Pachto"), ("fa", "Persa"),
    ("pl", "Polonês"), ("pt", "Português"), ("pa", "Punjabi"), ("qu", "Quíchua"),
    ("ro", "Romeno"), ("ru", "Russo"), ("sm", "Samoano"), ("sa", "Sânscrito"),
    ("nso", "Sepedi"), ("sr", "Sérvio"), ("st", "Sesoto"), ("sn", "Xona"),
    ("sd", "Sindi"), ("so", "Somali"), ("sw", "Suaíli"), ("sv", "Sueco"),
    ("su", "Sundanês"), ("tl", "Filipino (tagalo)"), ("tg", "Tadjique"), ("th", "Tailandês"),
    ("ta", "Tâmil"), ("tt", "Tártaro"), ("te", "Telugu"), ("ti", "Tigrínia"),
    ("ts", "Tsonga"), ("tr", "Turco"), ("tk", "Turcomeno"), ("ak", "Twi"),
    ("uk", "Ucraniano"), ("ug", "Uigur"), ("ur", "Urdu"), ("uz", "Uzbeque"),
    ("vi", "Vietnamita"), ("xh", "Xhosa"), ("yi", "Iídiche"), ("zu", "Zulu"),
    ("ach", "Acholi"),
)


def _key(name: str) -> str:
    base = unicodedata.normalize("NFD", name)
    return "".join(c for c in base if not unicodedata.combining(c)).casefold()


LANGUAGES: tuple[tuple[str, str], ...] = tuple(
    sorted(dict(_RAW).items(), key=lambda item: _key(item[1]))
)
_NAMES = dict(LANGUAGES)


def name_of(code: str) -> str:
    """Nome em português; AUTO vira "Detectar idioma" e código desconhecido volta como veio."""
    if code == AUTO:
        return "Detectar idioma"
    return _NAMES.get(code, code)


def ordered(recent: list[str], with_auto: bool) -> list[tuple[str, str]]:
    """Lista para os seletores: AUTO, recentes válidos e o resto em ordem alfabética."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    if with_auto:
        out.append((AUTO, name_of(AUTO)))
        seen.add(AUTO)
    for code in recent:
        if code in _NAMES and code not in seen:
            out.append((code, _NAMES[code]))
            seen.add(code)
    out.extend((c, n) for c, n in LANGUAGES if c not in seen)
    return out


def push_recent(recent: list[str], code: str) -> list[str]:
    """Põe o código na frente, sem repetir, até MAX_RECENT; ignora AUTO."""
    if code == AUTO:
        return list(recent)
    return [code, *(c for c in recent if c != code)][:MAX_RECENT]
