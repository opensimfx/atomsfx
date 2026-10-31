"""Bright-star catalogue (J2000.0) used to place recognisable constellations.

Positions are rounded to 0.1 s of RA / 1 arcsecond of Dec; V magnitudes and B-V colour indices are
rounded to 0.01. They are standard published values entered by hand (see docs/REFERENCES.md); the
test-suite checks well-known angular separations (Orion's belt, the Southern Cross, the Pointers,
Vega-Altair-Deneb) so a gross transcription error cannot ship. Fainter stars are synthesised by
``starmap`` with a realistic magnitude law, not read from here.

Format of ``_RAW``: ``name | RA h m s | Dec d m s | V | B-V``.
"""
from __future__ import annotations

from dataclasses import dataclass

_RAW = """
Sirius|06 45 08.9|-16 42 58|-1.46|0.00
Canopus|06 23 57.1|-52 41 44|-0.74|0.15
Rigil Kentaurus|14 39 36.5|-60 50 02|-0.27|0.71
Arcturus|14 15 39.7|+19 10 57|-0.05|1.23
Vega|18 36 56.3|+38 47 01|0.03|0.00
Capella|05 16 41.4|+45 59 53|0.08|0.80
Rigel|05 14 32.3|-08 12 06|0.13|-0.03
Procyon|07 39 18.1|+05 13 30|0.34|0.42
Achernar|01 37 42.8|-57 14 12|0.46|-0.16
Betelgeuse|05 55 10.3|+07 24 25|0.42|1.85
Hadar|14 03 49.4|-60 22 23|0.61|-0.23
Altair|19 50 47.0|+08 52 06|0.76|0.22
Acrux|12 26 35.9|-63 05 57|0.77|-0.24
Aldebaran|04 35 55.2|+16 30 33|0.86|1.54
Antares|16 29 24.5|-26 25 55|0.96|1.83
Spica|13 25 11.6|-11 09 41|0.97|-0.23
Pollux|07 45 18.9|+28 01 34|1.14|1.00
Fomalhaut|22 57 39.0|-29 37 20|1.16|0.09
Deneb|20 41 25.9|+45 16 49|1.25|0.09
Mimosa|12 47 43.3|-59 41 19|1.25|-0.23
Regulus|10 08 22.3|+11 58 02|1.40|-0.11
Adhara|06 58 37.5|-28 58 20|1.50|-0.21
Castor|07 34 36.0|+31 53 18|1.58|0.03
Shaula|17 33 36.5|-37 06 14|1.62|-0.22
Gacrux|12 31 09.9|-57 06 48|1.64|1.59
Bellatrix|05 25 07.9|+06 20 59|1.64|-0.22
Elnath|05 26 17.5|+28 36 27|1.65|-0.13
Miaplacidus|09 13 12.0|-69 43 02|1.67|0.00
Alnilam|05 36 12.8|-01 12 07|1.69|-0.18
Alnair|22 08 14.0|-46 57 40|1.74|-0.13
Alnitak|05 40 45.5|-01 56 34|1.77|-0.21
Regor|08 09 32.0|-47 20 12|1.75|-0.22
Alioth|12 54 01.7|+55 57 35|1.76|-0.02
Dubhe|11 03 43.7|+61 45 03|1.79|1.07
Mirfak|03 24 19.4|+49 51 40|1.80|0.48
Wezen|07 08 23.5|-26 23 36|1.83|0.68
Kaus Australis|18 24 10.3|-34 23 05|1.85|-0.03
Alkaid|13 47 32.4|+49 18 48|1.86|-0.19
Avior|08 22 30.8|-59 30 34|1.86|1.20
Sargas|17 37 19.1|-42 59 52|1.87|0.40
Menkalinan|05 59 31.7|+44 56 51|1.90|0.08
Atria|16 48 39.9|-69 01 40|1.92|1.45
Alhena|06 37 42.7|+16 23 57|1.93|0.00
Peacock|20 25 38.9|-56 44 06|1.94|-0.20
Alsephina|08 44 42.2|-54 42 30|1.96|0.04
Mirzam|06 22 42.0|-17 57 22|1.98|-0.24
Alphard|09 27 35.2|-08 39 31|1.98|1.44
Polaris|02 31 49.1|+89 15 51|1.98|0.60
Hamal|02 07 10.4|+23 27 45|2.00|1.15
Algieba|10 19 58.4|+19 50 30|2.01|1.15
Diphda|00 43 35.4|-17 59 12|2.04|1.02
Nunki|18 55 15.9|-26 17 48|2.05|-0.20
Menkent|14 06 41.0|-36 22 12|2.06|1.01
Mirach|01 09 43.9|+35 37 14|2.05|1.58
Alpheratz|00 08 23.3|+29 05 26|2.06|-0.11
Rasalhague|17 34 56.1|+12 33 36|2.08|0.15
Kochab|14 50 42.3|+74 09 20|2.08|1.47
Saiph|05 47 45.4|-09 40 11|2.07|-0.17
Denebola|11 49 03.6|+14 34 19|2.14|0.09
Algol|03 08 10.1|+40 57 20|2.12|-0.05
Schedar|00 40 30.4|+56 32 14|2.23|1.17
Caph|00 09 10.7|+59 08 59|2.27|0.34
Almach|02 03 54.0|+42 19 47|2.26|1.37
Sadr|20 22 13.7|+40 15 24|2.23|0.67
Eltanin|17 56 36.4|+51 29 20|2.23|1.52
Mintaka|05 32 00.4|-00 17 57|2.23|-0.22
Alphecca|15 34 41.3|+26 42 53|2.23|0.03
Dschubba|16 00 20.0|-22 37 18|2.29|-0.12
Larawag|16 50 09.8|-34 17 36|2.29|1.15
Aspidiske|09 17 05.4|-59 16 31|2.25|0.04
Suhail|09 07 59.8|-43 25 57|2.21|1.66
Naos|08 03 35.0|-40 00 12|2.25|-0.27
Mizar|13 23 55.5|+54 55 31|2.23|0.02
Merak|11 01 50.5|+56 22 57|2.37|-0.02
Izar|14 44 59.2|+27 04 27|2.37|0.97
Phecda|11 53 49.8|+53 41 41|2.44|0.00
Enif|21 44 11.2|+09 52 30|2.39|1.52
Ankaa|00 26 17.1|-42 18 22|2.39|1.09
Scheat|23 03 46.5|+28 04 58|2.42|1.67
Sabik|17 10 22.7|-15 43 30|2.43|0.06
Aludra|07 24 05.7|-29 18 11|2.45|-0.08
Alderamin|21 18 34.8|+62 35 08|2.45|0.22
Gienah Cygni|20 46 12.7|+33 58 13|2.46|1.03
Navi|00 56 42.5|+60 43 00|2.47|-0.15
Markab|23 04 45.7|+15 12 19|2.49|-0.04
Menkar|03 02 16.8|+04 05 24|2.53|1.63
Zosma|11 14 06.5|+20 31 25|2.56|0.13
Arneb|05 32 43.8|-17 49 20|2.58|0.21
Gienah Corvi|12 15 48.4|-17 32 31|2.59|-0.11
Ascella|19 02 36.7|-29 52 49|2.60|0.08
Phact|05 39 38.9|-34 04 27|2.65|-0.12
Unukalhai|15 44 16.1|+06 25 32|2.65|1.17
Ruchbah|01 25 48.9|+60 14 07|2.68|0.13
Kaus Media|18 20 59.6|-29 49 41|2.70|1.38
Tarazed|19 46 15.6|+10 36 48|2.72|1.52
Kornephoros|16 30 13.2|+21 29 23|2.77|0.94
Cursa|05 07 51.0|-05 05 11|2.79|0.13
Imai|12 15 08.7|-58 44 56|2.80|-0.25
Kaus Borealis|18 27 58.2|-25 25 18|2.81|1.55
Algenib|00 13 14.2|+15 11 01|2.83|-0.19
Vindemiatrix|13 02 10.6|+10 57 33|2.83|0.94
Alcyone|03 47 29.1|+24 06 19|2.87|-0.09
Delta Cygni|19 44 58.5|+45 07 51|2.87|-0.03
Deneb Algedi|21 47 02.4|-16 07 38|2.87|0.29
Gomeisa|07 27 09.0|+08 17 22|2.89|-0.09
Cor Caroli|12 56 01.7|+38 19 06|2.89|-0.12
Sadalsuud|21 31 33.5|-05 34 16|2.91|0.83
Sadalmelik|22 05 47.0|-00 19 11|2.96|0.98
Pherkad|15 20 43.7|+71 50 02|3.05|0.05
Dabih|20 21 00.7|-14 46 53|3.05|0.79
Phi Sagittarii|18 45 39.7|-26 59 27|3.17|-0.11
Albireo|19 30 43.3|+27 57 35|3.18|1.13
Sulafat|18 58 56.6|+32 41 22|3.25|0.00
Megrez|12 15 25.6|+57 01 57|3.31|0.08
Tau Sagittarii|19 06 56.4|-27 40 14|3.32|1.17
Segin|01 54 23.7|+63 40 13|3.37|-0.15
Sheliak|18 50 04.8|+33 21 46|3.52|0.00
Meissa|05 35 08.3|+09 56 03|3.54|-0.18
Alshain|19 55 18.8|+06 24 24|3.71|0.86
"""


@dataclass(frozen=True)
class Star:
    name: str
    ra_deg: float
    dec_deg: float
    mag: float
    bv: float


def _parse_ra(text: str) -> float:
    h, m, s = text.split()
    return (float(h) + float(m) / 60.0 + float(s) / 3600.0) * 15.0


def _parse_dec(text: str) -> float:
    d, m, s = text.split()
    sign = -1.0 if d.startswith("-") else 1.0
    return sign * (abs(float(d)) + float(m) / 60.0 + float(s) / 3600.0)


def _load() -> tuple[Star, ...]:
    out = []
    for line in _RAW.strip().splitlines():
        name, ra, dec, v, bv = (p.strip() for p in line.split("|"))
        out.append(Star(name, _parse_ra(ra), _parse_dec(dec), float(v), float(bv)))
    return tuple(out)


CATALOG: tuple[Star, ...] = _load()
BY_NAME = {s.name: s for s in CATALOG}
CATALOG_VERSION = 1
