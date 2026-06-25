#!/usr/bin/env python
"""
Convert the Cao et al. (2019) "Multi-channel EEG recordings during a
sustained-attention driving task" RAW dataset (figshare 6427334 v5) to BIDS-EEG.

Source : EEGLAB .set files in sourcedata/raw/
Output : BIDS dataset in bids/

One long-lived process (mne import is expensive on this filesystem).
Run with the neuroai env python.
"""
import os
import re
import sys
import json
import time
import collections
from pathlib import Path

import numpy as np

ROOT = Path("/expanse/lustre/projects/csd403/bpinto/driving_eeg")
BIDS = ROOT / "bids"
# sourcedata lives inside the BIDS root (self-contained dataset)
RAW = BIDS / "sourcedata" / "raw"
META = BIDS / "sourcedata" / "meta"

t0 = time.time()
def log(m): print(f"[{time.time()-t0:7.1f}s] {m}", flush=True)

log("importing mne / mne_bids ...")
import mne
import mne_bids
from mne_bids import BIDSPath, write_raw_bids, make_dataset_description
log(f"mne {mne.__version__}, mne_bids {mne_bids.__version__}")

TASK = "driving"
LINE_FREQ = 60.0  # Taiwan (National Chiao Tung University)

# Event code -> human-readable trial_type (BIDS events.tsv).
# Source: Cao et al. 2019, Sci Data, event-related lane-departure paradigm.
EVENT_LABELS = {
    "251": "deviation_onset_left",
    "252": "deviation_onset_right",
    "253": "response_onset",
    "254": "response_offset",
    # Trigger 255 occurs only in sub-54 and sub-55 and is not defined in the
    # source publication (Cao et al. 2019). Kept and labelled transparently.
    "255": "undocumented_255",
}
EVENT_DESCRIPTIONS = {
    "deviation_onset_left":  "Car drift (lane-departure) randomly induced toward the LEFT.",
    "deviation_onset_right": "Car drift (lane-departure) randomly induced toward the RIGHT.",
    "response_onset":  "Subject begins steering the car back toward cruising lane center.",
    "response_offset": "Subject finishes steering; car back at cruising lane center.",
}

# Mastoid reference electrodes (recorded as EEG-type channels). Kept as 'eeg'.
REF_CHANNELS = {"A1", "A2"}
# Behavioral channel embedded in the recording (car lateral position). -> misc.
BEHAV_CHAN_SRC = "vehicle position"
BEHAV_CHAN_DST = "vehicle_position"

# Map the dataset's (classic, upper-case) electrode names to the modern
# standard_1020 names so we can attach NOMINAL TEMPLATE positions while keeping
# the original channel labels in the data. Names not listed (and A1/A2) get no
# template position. Source montage is the modified international 10-20 system.
TEMPLATE_NAME_MAP = {
    "FP1": "Fp1", "FP2": "Fp2", "F7": "F7", "F3": "F3", "FZ": "Fz", "F4": "F4",
    "F8": "F8", "FT7": "FT7", "FC3": "FC3", "FCZ": "FCz", "FC4": "FC4",
    "FT8": "FT8", "T3": "T7", "C3": "C3", "CZ": "Cz", "C4": "C4", "T4": "T8",
    "TP7": "TP7", "CP3": "CP3", "CPZ": "CPz", "CP4": "CP4", "TP8": "TP8",
    "T5": "P7", "P3": "P3", "PZ": "Pz", "P4": "P4", "T6": "P8",
    "O1": "O1", "OZ": "Oz", "O2": "O2",
}

def build_template_montage(ch_names):
    """DigMontage with nominal 10-20 template positions keyed by ORIGINAL names."""
    std = mne.channels.make_standard_montage("standard_1020")
    std_pos = std.get_positions()["ch_pos"]
    ch_pos = {}
    for ch in ch_names:
        std_name = TEMPLATE_NAME_MAP.get(ch.upper())
        if std_name and std_name in std_pos:
            ch_pos[ch] = std_pos[std_name]
    if not ch_pos:
        return None, 0
    mont = mne.channels.make_dig_montage(ch_pos=ch_pos, coord_frame="head")
    return mont, len(ch_pos)

# ---- filename parsing: sNN_YYMMDD[_K]<suffix>.set -----------------------------
FNAME_RE = re.compile(r"^s(?P<sub>\d+)_(?P<date>\d{6})(?:_(?P<runidx>\d+))?(?P<suf>[a-z])$")

def parse_stem(stem):
    m = FNAME_RE.match(stem)
    if not m:
        raise ValueError(f"cannot parse {stem!r}")
    d = m.groupdict()
    yy, mm, dd = d["date"][:2], d["date"][2:4], d["date"][4:6]
    year = 2000 + int(yy)
    acq_date = f"{year:04d}-{mm}-{dd}"
    return {
        "orig_sub": f"s{d['sub']}",
        "sub": f"{int(d['sub']):02d}",
        "date_raw": d["date"],
        "acq_date": acq_date,
        "runidx": d["runidx"],            # may be None
        "suffix": d["suf"],               # 'm' or 'n'
        "stem": stem,
    }

def load_sizes():
    sizes = {}
    sp = RAW / "sizes.tsv"
    if sp.exists():
        for line in sp.read_text().splitlines():
            name, sz = line.split("\t")
            sizes[name] = int(sz)
    return sizes

def discover():
    sizes = load_sizes()
    files = []
    for p in sorted(RAW.glob("*.set")):
        exp = sizes.get(p.name)
        if exp is not None and p.stat().st_size != exp:
            log(f"skip incomplete {p.name} ({p.stat().st_size} != {exp})")
            continue
        files.append(p)
    if not files:
        raise RuntimeError(
            f"No .set files found under {RAW}. Check that the source data is "
            f"present before running the conversion.")
    parsed = []
    for p in files:
        info = parse_stem(p.stem)
        info["path"] = p
        parsed.append(info)
    # group by subject, order sessions by (date, numeric runidx, suffix)
    by_sub = collections.defaultdict(list)
    for info in parsed:
        by_sub[info["sub"]].append(info)
    for sub in by_sub:
        by_sub[sub].sort(key=lambda x: (x["date_raw"], int(x["runidx"] or 0), x["suffix"]))
        for i, info in enumerate(by_sub[sub], start=1):
            info["ses"] = f"{i:02d}"
    return by_sub

def build_raw(info):
    raw = mne.io.read_raw_eeglab(info["path"], preload=True, verbose="ERROR")
    # rename the behavioral "vehicle position" channel (drop the space) and
    # mark it as a misc (non-EEG) channel.
    if BEHAV_CHAN_SRC in raw.ch_names:
        raw.rename_channels({BEHAV_CHAN_SRC: BEHAV_CHAN_DST})
    if BEHAV_CHAN_DST in raw.ch_names:
        raw.set_channel_types({BEHAV_CHAN_DST: "misc"}, verbose="ERROR")
    # A1/A2 mastoid references are physical EEG electrodes -> keep type 'eeg'.
    raw.info["line_freq"] = LINE_FREQ
    # Attach nominal 10-20 template positions (documented as template, not measured).
    mont, n_pos = build_template_montage(raw.ch_names)
    if mont is not None:
        raw.set_montage(mont, on_missing="ignore", verbose="ERROR")
    return raw

def make_events(raw):
    """Return (events ndarray, event_id dict label->int) for write_raw_bids."""
    descs = list(raw.annotations.description)
    uniq = sorted(set(descs))
    # map each raw description to a label + a stable integer code
    label_for = {}
    code_for_label = {}
    next_code = 1000  # for unexpected codes
    for d in uniq:
        if d in EVENT_LABELS:
            label = EVENT_LABELS[d]
            code = int(d)
        else:
            label = d.strip().replace(" ", "_") or "unknown"
            try:
                code = int(float(d))
            except ValueError:
                code = next_code; next_code += 1
        label_for[d] = label
        code_for_label[label] = code
    # rename annotations to labels so events_from_annotations keys are labels
    new_desc = [label_for[d] for d in descs]
    raw.annotations.description = np.array(new_desc, dtype=object)
    events, ev_id = mne.events_from_annotations(
        raw, event_id=code_for_label, verbose="ERROR")
    # Drop annotations so write_raw_bids derives events.tsv ONLY from the
    # events array (otherwise events get written twice).
    raw.set_annotations(None)
    return events, ev_id

def main():
    by_sub = discover()
    n_sessions = sum(len(v) for v in by_sub.values())
    log(f"discovered {len(by_sub)} subjects, {n_sessions} sessions ready")

    BIDS.mkdir(parents=True, exist_ok=True)
    all_event_labels = set()
    records = []
    written = 0

    for sub in sorted(by_sub):
        for info in by_sub[sub]:
            tag = f"sub-{sub} ses-{info['ses']} <- {info['stem']}"
            try:
                raw = build_raw(info)
                n_chan = len(raw.ch_names)
                dur = raw.n_times / raw.info["sfreq"]
                events, ev_id = make_events(raw)
                ev_counts = {lbl: int((events[:, 2] == code).sum())
                             for lbl, code in ev_id.items()}
                all_event_labels.update(ev_id.keys())
                bp = BIDSPath(subject=sub, session=info["ses"], task=TASK,
                              datatype="eeg", root=BIDS)
                write_raw_bids(
                    raw, bp, events=events, event_id=ev_id,
                    overwrite=True, allow_preload=True, format="EEGLAB",
                    verbose="ERROR")
                records.append({
                    "sub": sub, "ses": info["ses"], "orig_sub": info["orig_sub"],
                    "stem": info["stem"], "acq_date": info["acq_date"],
                    "suffix": info["suffix"], "runidx": info["runidx"],
                    "n_chan": n_chan, "duration_sec": round(dur, 3),
                    "n_events": int(len(events)), "event_counts": ev_counts,
                })
                written += 1
                log(f"OK  {tag}  (chan={n_chan} dur={dur:.0f}s n_events={len(events)})")
            except Exception as e:
                log(f"FAIL {tag}: {type(e).__name__}: {e}")
                raise
    log(f"wrote {written} recordings")
    summary = {
        "records": records,
        "event_labels": sorted(all_event_labels),
        "n_written": written,
        "n_subjects": len(by_sub),
    }
    (ROOT / "convert_summary.json").write_text(json.dumps(summary, indent=2))
    log("summary written -> convert_summary.json")

if __name__ == "__main__":
    main()
