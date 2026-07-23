#!/usr/bin/env python3
"""Batch 2b: Fix NOAA data + additional WHO data"""
import os, subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ART = os.path.join(REPO_ROOT, "examples", "stage4_fifty_steps", "stage4_artifacts")
NOAA = os.environ.get("NOAA_CLI_PATH", os.path.join(REPO_ROOT, "..", ".skills", "skill_noaa-data-skill", "bin", "_cli_wrapper.py"))
WHO = os.environ.get("WHO_CLI_PATH", os.path.join(REPO_ROOT, "..", ".skills", "skill_who-data-skill", "scripts", "_cli_wrapper.py"))

def noaa(cmd, params=None):
    c = ["python3", NOAA, "call", cmd]
    if params:
        for k,v in params.items(): c.extend(["--param", f"{k}={v}"])
    r = subprocess.run(c, capture_output=True, text=True, timeout=60, cwd=os.path.dirname(NOAA))
    return r.stdout.strip() if r.returncode == 0 else f"ERR:{r.stderr[:300]}"

def who(cmd, params=None):
    c = ["python3", WHO, "call", cmd]
    if params:
        for k,v in params.items(): c.extend(["--param", f"{k}={v}"])
    r = subprocess.run(c, capture_output=True, text=True, timeout=60, cwd=os.path.dirname(WHO))
    return r.stdout.strip() if r.returncode == 0 else f"ERR:{r.stderr[:300]}"

def save(fn, content):
    with open(os.path.join(ART, fn), "w") as f: f.write(content)
    print(f"  Saved {fn} ({len(content)} chars)")

# Fix NOAA - use 9 year range
print("Fixing NOAA temperature data (2011-2019)...")
temp = noaa("get-data", {"datasetid":"GSOY","startdate":"2011-01-01","enddate":"2019-12-31",
    "locationid":"CITY:US390029","datatypeid":"TMAX,TMIN","units":"metric","limit":"100"})
save("step14_noaa_temp.json", temp)
print(f"  Content: {temp[:300]}")

print("Fixing NOAA precipitation data (2011-2019)...")
prcp = noaa("get-data", {"datasetid":"GSOY","startdate":"2011-01-01","enddate":"2019-12-31",
    "locationid":"CITY:US390029","datatypeid":"PRCP","units":"metric","limit":"100"})
save("step15_noaa_prcp.json", prcp)
print(f"  Content: {prcp[:300]}")

print("NYC data (2011-2019)...")
ny = noaa("get-data", {"datasetid":"GSOY","startdate":"2011-01-01","enddate":"2019-12-31",
    "locationid":"CITY:US360010","datatypeid":"TMAX,TMIN,PRCP","units":"metric","limit":"100"})
save("step15b_noaa_newyork.json", ny)
print(f"  Content: {ny[:300]}")

# Additional cities
print("Chicago data...")
chi = noaa("get-data", {"datasetid":"GSOY","startdate":"2011-01-01","enddate":"2019-12-31",
    "locationid":"CITY:US170014","datatypeid":"TMAX,TMIN,PRCP","units":"metric","limit":"100"})
save("step15c_noaa_chicago.json", chi)

# Try WHO NCD with correct code
print("WHO NCD mortality data...")
ncd = who("get-indicator-data", {"indicator_code":"NCDMORT_000001","time_from":"2010","time_to":"2019","top":"100"})
save("step17b_who_ncd.json", ncd)
print(f"  Content: {ncd[:300]}")

# Get air pollution health data
print("WHO air pollution health data...")
ap = who("get-indicator-data", {"indicator_code":"APM_0335","time_from":"2010","time_to":"2019","top":"100"})
save("step17d_who_airpol_data.json", ap)
print(f"  Content: {ap[:300]}")

print("\nBatch 2b complete!")
