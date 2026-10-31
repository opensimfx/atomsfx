"""Generate ``atmosfx/data/presets.json`` from the tables below.

Run from the repository root:  python tools/gen_presets.py
Presets are described as small overrides of a base so intent is visible; the JSON is the shipped artifact.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from atmosfx.core import clouds as C  # noqa: E402
from atmosfx.core import presets as P  # noqa: E402

BASE = P.Preset(id="base", name="Base")


def layer(kind: str, **kw) -> P.CloudLayerCfg:
    k = C.kind(kind)
    d = dict(kind=kind, altitude_m=k.altitude_m, thickness_m=k.thickness_m, coverage=k.coverage,
             density=k.density, scale_m=k.scale_m, detail=k.detail, anisotropy=k.anisotropy)
    d.update(kw)
    return P.CloudLayerCfg(**d)


def make(pid, name, cat, desc, tags=(), **over):
    return P.derive(BASE, id=pid, name=name, category=cat, description=desc, tags=list(tags), **over)


NO_STARS = {"enabled": False}
NIGHT_SUN = {"elevation_deg": -35.0}

PRESETS = [
    # ------------------------------------------------------------------ Time of day
    make("clear_noon", "Clear noon", "Time of day", "High sun, deep blue sky, almost no cloud.", ["day", "clear"],
         sun={"elevation_deg": 68.0, "azimuth_deg": 180.0, "hour": 12.0}, stars=NO_STARS,
         moon={"enabled": False}, fog={"enabled": True, "mode": "WORLD", "visibility_m": 60000.0, "scale_height_m": 1500.0}),
    make("clear_morning", "Clear morning", "Time of day", "Low warm sun in a clean, slightly hazy sky.", ["day", "morning"],
         sun={"elevation_deg": 24.0, "azimuth_deg": 105.0, "hour": 8.0}, stars=NO_STARS, moon={"enabled": False},
         sky={"aerosol_density": 1.3}, fog={"enabled": True, "mode": "WORLD", "visibility_m": 25000.0, "scale_height_m": 1500.0}),
    make("golden_hour", "Golden hour", "Time of day", "Sun a few degrees up, long warm light, thin cirrus.", ["sunset", "warm"],
         sun={"elevation_deg": 6.0, "azimuth_deg": 255.0, "hour": 18.5}, stars=NO_STARS, moon={"enabled": False},
         sky={"aerosol_density": 1.6},
         deck={"enabled": True, "coverage": 0.35, "altitude_m": 9000.0, "scale_m": 7000.0, "opacity": 0.65, "fibre": 3.0},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 18000.0, "scale_height_m": 1500.0}),
    make("sunset_clouds", "Sunset with clouds", "Time of day", "Low sun lighting an altocumulus field gold while the ground is already in shadow.",
         ["sunset", "clouds"], sun={"elevation_deg": 4.0, "azimuth_deg": 268.0, "hour": 19.2}, stars=NO_STARS,
         moon={"enabled": False}, sky={"aerosol_density": 2.0},
         clouds=[layer("ALTOCUMULUS", coverage=0.42, altitude_m=4200.0)],
         deck={"enabled": True, "coverage": 0.4, "opacity": 0.6, "fibre": 4.0},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 15000.0, "scale_height_m": 1500.0}),
    make("sunrise_mist", "Sunrise over mist", "Time of day", "Sun at the horizon, low ground mist.", ["sunrise", "mist"],
         sun={"elevation_deg": 2.0, "azimuth_deg": 92.0, "hour": 6.2}, stars=NO_STARS, moon={"enabled": False},
         sky={"aerosol_density": 1.5},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 1200.0, "scale_height_m": 90.0, "anisotropy": 0.5,
              "noise_amount": 0.35}),
    make("blue_hour", "Blue hour", "Time of day", "Sun 5 degrees below the horizon; the sky glows deep blue.", ["twilight"],
         sun={"elevation_deg": -5.0, "azimuth_deg": 270.0, "hour": 19.9}, moon={"enabled": False},
         stars={"brightness": 1.0, "magnitude_limit": 2.0}),
    make("civil_twilight", "Civil twilight", "Time of day", "Sun 3 degrees below the horizon; the brightest stars appear.",
         ["twilight"], sun={"elevation_deg": -3.0, "azimuth_deg": 270.0, "hour": 19.6}, moon={"enabled": False},
         stars={"magnitude_limit": 1.0}),
    # ------------------------------------------------------------------- Night sky
    make("starry_night", "Starry night", "Night sky", "Moonless sky, full star field and Milky Way.", ["night", "stars"],
         sun=NIGHT_SUN, moon={"enabled": True, "phase": 0.0, "elevation_deg": -20.0},
         stars={"brightness": 1.2, "magnitude_limit": 6.3, "milky_way": 1.0}, sky={"night_glow": 0.003}),
    make("milky_way_dark_site", "Milky Way, dark site", "Night sky", "Remote dark-sky night, strong Milky Way and extra faint stars.",
         ["night", "milky way"], sun={"elevation_deg": -45.0}, moon={"enabled": True, "phase": 0.0, "elevation_deg": -30.0},
         stars={"brightness": 1.4, "magnitude_limit": 6.5, "milky_way": 1.6, "density": 1.4}, sky={"night_glow": 0.004}),
    make("full_moon_night", "Full moon night", "Night sky", "High full moon; bright stars only, moonlit sky.", ["night", "moon"],
         sun=NIGHT_SUN, moon={"enabled": True, "phase": 0.5, "elevation_deg": 48.0, "azimuth_deg": 160.0, "strength": 0.15},
         stars={"magnitude_limit": 4.5, "milky_way": 0.35}, sky={"night_glow": 0.002}),
    make("crescent_dusk", "Crescent moon at dusk", "Night sky", "Thin waxing crescent low in the west after sunset.",
         ["night", "moon", "twilight"], sun={"elevation_deg": -9.0, "azimuth_deg": 278.0, "hour": 20.2},
         moon={"enabled": True, "phase": 0.1, "elevation_deg": 18.0, "azimuth_deg": 262.0, "strength": 0.1},
         stars={"magnitude_limit": 3.5}),
    make("half_moon_evening", "Half moon", "Night sky", "First-quarter moon high in the evening sky.", ["night", "moon"],
         sun={"elevation_deg": -25.0, "azimuth_deg": 280.0}, moon={"enabled": True, "phase": 0.25, "elevation_deg": 50.0, "azimuth_deg": 190.0},
         stars={"magnitude_limit": 5.0, "milky_way": 0.6}),
    # --------------------------------------------------------------------- Weather
    make("fair_weather_cumulus", "Fair-weather cumulus", "Weather", "Scattered cumulus on a blue day.", ["day", "clouds"],
         sun={"elevation_deg": 52.0, "azimuth_deg": 170.0, "hour": 13.0}, stars=NO_STARS, moon={"enabled": False},
         clouds=[layer("CUMULUS", coverage=0.38)],
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 35000.0, "scale_height_m": 1500.0}),
    make("cumulus_day", "Billowing cumulus", "Weather", "Big towering cumulus with deep shadows.", ["day", "clouds"],
         sun={"elevation_deg": 45.0, "azimuth_deg": 150.0, "hour": 14.0}, stars=NO_STARS, moon={"enabled": False},
         clouds=[layer("CUMULUS", coverage=0.55, thickness_m=1800.0, density=0.026, scale_m=1100.0)],
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 30000.0, "scale_height_m": 1500.0}),
    make("stratocumulus_sky", "Stratocumulus deck", "Weather", "Low lumpy cloud sheet with bright gaps.", ["day", "clouds"],
         sun={"elevation_deg": 35.0, "azimuth_deg": 200.0, "hour": 15.0}, stars=NO_STARS, moon={"enabled": False},
         clouds=[layer("STRATOCUMULUS", coverage=0.62)],
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 15000.0, "scale_height_m": 1200.0}),
    make("overcast_stratus", "Overcast", "Weather", "Uniform grey stratus; flat soft light.", ["day", "overcast"],
         sun={"elevation_deg": 40.0, "azimuth_deg": 180.0, "hour": 13.0}, stars=NO_STARS, moon={"enabled": False},
         clouds=[layer("STRATUS", coverage=0.97, thickness_m=500.0, density=0.016)],
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 9000.0, "scale_height_m": 1000.0}),
    make("storm_cumulonimbus", "Storm front", "Weather", "Towering cumulonimbus with a dark base and anvil.", ["storm", "clouds"],
         sun={"elevation_deg": 28.0, "azimuth_deg": 230.0, "hour": 16.0}, stars=NO_STARS, moon={"enabled": False},
         clouds=[layer("CUMULONIMBUS", coverage=0.3, radius_m=25000.0),
                 layer("STRATUS", coverage=0.5, altitude_m=800.0, density=0.014)],
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 12000.0, "scale_height_m": 1200.0}),
    make("mackerel_sky", "Mackerel sky", "Weather", "Rows of altocumulus across a high sun.", ["day", "clouds"],
         sun={"elevation_deg": 40.0, "azimuth_deg": 190.0, "hour": 12.5}, stars=NO_STARS, moon={"enabled": False},
         clouds=[layer("ALTOCUMULUS", coverage=0.6)],
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 40000.0, "scale_height_m": 1500.0}),
    make("cirrus_wisps", "Cirrus wisps", "Weather", "High ice-crystal streaks on a clear day (2D deck, no cost).",
         ["day", "cirrus"], sun={"elevation_deg": 55.0, "azimuth_deg": 170.0, "hour": 13.0}, stars=NO_STARS,
         moon={"enabled": False}, deck={"enabled": True, "coverage": 0.45, "opacity": 0.55, "fibre": 5.0},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 50000.0, "scale_height_m": 1500.0}),
    make("volumetric_cirrus_sunset", "Volumetric cirrus sunset", "Weather", "Volumetric cirrus layer lit by a low sun.",
         ["sunset", "cirrus"], sun={"elevation_deg": 3.0, "azimuth_deg": 260.0, "hour": 19.0}, stars=NO_STARS,
         moon={"enabled": False}, sky={"aerosol_density": 1.8},
         clouds=[layer("CIRRUS", coverage=0.5, density=0.004)],
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 20000.0, "scale_height_m": 1500.0}),
    # ---------------------------------------------------------------- Fog and haze
    make("summer_haze", "Summer haze", "Fog and haze", "Warm humid haze, 6 km visibility.", ["haze"],
         sun={"elevation_deg": 40.0, "azimuth_deg": 150.0, "hour": 14.0}, stars=NO_STARS, moon={"enabled": False},
         sky={"aerosol_density": 3.0},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 6000.0, "scale_height_m": 1500.0, "anisotropy": 0.5}),
    make("morning_mist", "Morning mist", "Fog and haze", "Low sun through 1.5 km mist hugging the ground.", ["mist"],
         sun={"elevation_deg": 9.0, "azimuth_deg": 110.0, "hour": 7.0}, stars=NO_STARS, moon={"enabled": False},
         sky={"aerosol_density": 1.6},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 1500.0, "scale_height_m": 80.0, "anisotropy": 0.55,
              "noise_amount": 0.3}),
    make("dense_fog", "Dense fog", "Fog and haze", "Visibility 80 m (WMO dense fog).", ["fog"],
         sun={"elevation_deg": 30.0, "azimuth_deg": 180.0, "hour": 10.0}, stars=NO_STARS, moon={"enabled": False},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 80.0, "scale_height_m": 300.0, "anisotropy": 0.6}),
    make("valley_fog", "Valley fog bank", "Fog and haze", "A placeable fog domain: thick pooled fog with a clear sky above.",
         ["fog", "domain"], sun={"elevation_deg": 12.0, "azimuth_deg": 100.0, "hour": 7.5}, stars=NO_STARS,
         moon={"enabled": False},
         fog={"enabled": True, "mode": "BOTH", "visibility_m": 30000.0, "scale_height_m": 1500.0,
              "domain_visibility_m": 220.0, "domain_radius_m": 1500.0, "domain_height_m": 120.0, "noise_amount": 0.6,
              "noise_scale_m": 250.0}),
    make("city_smog", "City smog", "Fog and haze", "Brown-grey polluted air, 3 km visibility.", ["haze", "pollution"],
         sun={"elevation_deg": 35.0, "azimuth_deg": 160.0, "hour": 15.0}, stars=NO_STARS, moon={"enabled": False},
         sky={"aerosol_density": 6.0},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 3000.0, "scale_height_m": 800.0, "absorption": 0.35,
              "color": [0.95, 0.85, 0.7]}),
    make("desert_dust", "Dust storm haze", "Fog and haze", "Orange dust-laden air, 2 km visibility.", ["haze", "dust"],
         sun={"elevation_deg": 30.0, "azimuth_deg": 200.0, "hour": 15.0}, stars=NO_STARS, moon={"enabled": False},
         sky={"aerosol_density": 9.0},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 2000.0, "scale_height_m": 1200.0, "absorption": 0.2,
              "color": [1.0, 0.72, 0.42]}),
    # -------------------------------------------------------------------- Special
    make("arctic_clear", "Arctic clarity", "Special", "Very clean air: crisp distance, 90 km visibility.", ["day", "clear"],
         sun={"elevation_deg": 22.0, "azimuth_deg": 185.0, "hour": 12.0}, stars=NO_STARS, moon={"enabled": False},
         sky={"aerosol_density": 0.25, "air_density": 0.95},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 90000.0, "scale_height_m": 2000.0}),
    make("high_altitude", "High altitude", "Special", "Viewpoint at 5 km: thinner air, deeper blue, curved depth.", ["day"],
         sun={"elevation_deg": 50.0, "azimuth_deg": 170.0, "hour": 12.0}, stars=NO_STARS, moon={"enabled": False},
         sky={"altitude_m": 5000.0, "aerosol_density": 0.5},
         fog={"enabled": True, "mode": "WORLD", "visibility_m": 120000.0, "scale_height_m": 3000.0}),
]


def main() -> int:
    errs = []
    ids = set()
    for p in PRESETS:
        e = P.validate(p)
        if p.id in ids:
            e.append("duplicate id")
        ids.add(p.id)
        errs += [f"{p.id}: {x}" for x in e]
    if errs:
        print("\n".join(errs))
        return 1
    out = os.path.join(ROOT, "atmosfx", "data", "presets.json")
    P.save_file(out, PRESETS)
    print(f"wrote {len(PRESETS)} presets -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
