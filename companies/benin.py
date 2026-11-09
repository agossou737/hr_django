"""Jours fériés légaux du Bénin (dates fixes + fêtes mobiles chrétiennes calculées).

Les fêtes musulmanes (Aïd el-Fitr, Aïd el-Kébir, Maouloud) dépendent de l'observation de la lune
et sont fixées par décret : elles doivent être ajoutées manuellement chaque année.
"""
import datetime


def easter(year):
    """Dimanche de Pâques (calendrier grégorien, algorithme de Meeus/Jones/Butcher)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return datetime.date(year, month, day)


def benin_holidays(year):
    """Liste de (date, libellé) triée."""
    paques = easter(year)
    days = [
        (datetime.date(year, 1, 1), "Jour de l'An"),
        (paques + datetime.timedelta(days=1), "Lundi de Pâques"),
        (datetime.date(year, 5, 1), "Fête du Travail"),
        (paques + datetime.timedelta(days=39), "Ascension"),
        (paques + datetime.timedelta(days=50), "Lundi de Pentecôte"),
        (datetime.date(year, 8, 1), "Fête de l'Indépendance"),
        (datetime.date(year, 8, 15), "Assomption"),
        (datetime.date(year, 11, 1), "Toussaint"),
        (datetime.date(year, 12, 25), "Noël"),
    ]
    return sorted(days)
