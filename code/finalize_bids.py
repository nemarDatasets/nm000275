#!/usr/bin/env python
"""
Finalize + richly enrich BIDS metadata for the sustained-attention driving EEG
dataset. Reads convert_summary.json (from convert_to_bids.py) and writes/patches
all dataset-, subject- and session-level metadata.

All facts are sourced from the original publication and its machine-readable
metadata held under sourcedata/meta/:
  - Cao, Z., Chuang, C.-H., King, J.-K. & Lin, C.-T. (2019) Sci Data 6:19,
    https://doi.org/10.1038/s41597-019-0027-4  (open-access full text: PMC6472414)
  - ISA-Tab study metadata (Springer ESM, CC0)
  - CrossRef / DataCite records
"""
import json
import csv
import shutil
from pathlib import Path
from collections import defaultdict, OrderedDict

ROOT = Path("/expanse/lustre/projects/csd403/bpinto/driving_eeg")
BIDS = ROOT / "bids"
SUMMARY = json.loads((ROOT / "convert_summary.json").read_text())
RECORDS = SUMMARY["records"]

BIDS_VERSION = "1.9.0"
PAPER_DOI = "https://doi.org/10.1038/s41597-019-0027-4"
RAW_FIGSHARE = "https://doi.org/10.6084/m9.figshare.6427334.v5"
PRE_FIGSHARE = "https://doi.org/10.6084/m9.figshare.7666055.v3"
AUTHORS = ["Zehong Cao", "Chun-Hsiang Chuang", "Jung-Kai King", "Chin-Teng Lin"]
AUTHOR_AFFIL = [
    ("Zehong Cao", "0000-0003-3656-0328",
     "Discipline of ICT, School of Technology, Environments and Design, "
     "University of Tasmania, Hobart, TAS, Australia"),
    ("Chun-Hsiang Chuang", None,
     "Department of Computer Science and Engineering, National Taiwan Ocean "
     "University, Keelung, Taiwan"),
    ("Jung-Kai King", None,
     "Brain Research Center, National Chiao Tung University, Hsinchu, Taiwan"),
    ("Chin-Teng Lin", None,
     "Centre for Artificial Intelligence, Faculty of Engineering and IT, "
     "University of Technology Sydney, Sydney, NSW, Australia"),
]
# Related publications by the original team that used this dataset (ISA-Tab).
RELATED_PUBS = [
    "https://doi.org/10.1016/j.neuroimage.2014.01.015",
    "https://doi.org/10.1038/srep21353",
    "https://doi.org/10.1109/TBCAS.2014.2316224",
    "https://doi.org/10.1109/TNNLS.2013.2275003",
    "https://doi.org/10.1016/j.knosys.2015.01.007",
    "https://doi.org/10.1109/TNNLS.2015.2496330",
    "https://doi.org/10.1109/TFUZZ.2016.2633379",
]

UNDOC_255 = ("Additional trigger (value 255) present only in sub-54 and sub-55 "
             "(21 occurrences total); it is NOT defined in the source publication "
             "(Cao et al. 2019) and its meaning is unknown. Retained as recorded.")
EVENT_VALUE_LEVELS = OrderedDict([
    ("251", "Deviation onset - car drift induced toward the LEFT"),
    ("252", "Deviation onset - car drift induced toward the RIGHT"),
    ("253", "Response onset - subject starts steering back toward lane centre"),
    ("254", "Response offset - subject finishes steering; car back at lane centre"),
    ("255", UNDOC_255),
])
TRIAL_TYPE_LEVELS = OrderedDict([
    ("deviation_onset_left",  "Deviation onset, car drift induced toward the left (trigger 251)"),
    ("deviation_onset_right", "Deviation onset, car drift induced toward the right (trigger 252)"),
    ("response_onset",        "Response onset, subject starts the counter-steering response (trigger 253)"),
    ("response_offset",       "Response offset, car returns to lane centre (trigger 254)"),
    ("undocumented_255",      UNDOC_255),
])
# HED 8.2 inline tags. The response is a steering-wheel turn (a Move), NOT a
# button Press; onset/offset are annotated symmetrically.
HED_TAGS = OrderedDict([
    ("deviation_onset_left",
     "Sensory-event, Experimental-stimulus, Visual-presentation, Label/Lane-departure-left"),
    ("deviation_onset_right",
     "Sensory-event, Experimental-stimulus, Visual-presentation, Label/Lane-departure-right"),
    ("response_onset",
     "Agent-action, Participant-response, Move, Label/Steering-response-onset"),
    ("response_offset",
     "Agent-action, Participant-response, Move, Label/Steering-response-offset"),
    ("undocumented_255", "Label/Undocumented-trigger-255"),
])

def w_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=4, ensure_ascii=False) + "\n")
    print("wrote", path.relative_to(BIDS))

def w_tsv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        wr = csv.writer(f, delimiter="\t")
        wr.writerow(header)
        wr.writerows(rows)
    print("wrote", path.relative_to(BIDS))

# ---------------------------------------------------------------- dataset_description
def dataset_description():
    obj = OrderedDict([
        ("Name", "Multi-channel EEG recordings during a sustained-attention driving task"),
        ("BIDSVersion", BIDS_VERSION),
        ("HEDVersion", "8.2.0"),
        ("DatasetType", "raw"),
        ("License", "CC-BY-4.0"),
        ("Authors", AUTHORS),
        ("Acknowledgements",
         "Data collected (2005-2012) at the Brain Research Center, National Chiao "
         "Tung University, Hsinchu, Taiwan. The authors thank their partner groups "
         "at the University of California San Diego (UCSD) and the DCS Corporation "
         "for independent validation."),
        ("HowToAcknowledge",
         "Please cite Cao, Z., Chuang, C.-H., King, J.-K. & Lin, C.-T. "
         "Multi-channel EEG recordings during a sustained-attention driving task. "
         "Sci. Data 6, 19 (2019). " + PAPER_DOI),
        ("Funding", [
            "U.S. Army Research Laboratory (ARL) and Army Research Office (ARO), "
            "grant W911NF-10-2-0022",
            "U.S. Army Research Laboratory (ARL), grant W911NF-10-D-0002/TO 0023",
        ]),
        ("EthicsApprovals", [
            "Approved by the Institutional Review Board of the Veterans General "
            "Hospital, Taipei, Taiwan. The study followed the Guide for the "
            "Committee of Laboratory Care and Use of National Chiao Tung "
            "University, Taiwan. All participants gave written informed consent.",
        ]),
        ("ReferencesAndLinks", [PAPER_DOI, RAW_FIGSHARE, PRE_FIGSHARE] + RELATED_PUBS),
        ("SourceDatasets", [
            {"URL": RAW_FIGSHARE, "Version": "5",
             "Description": "Raw EEGLAB .set files (figshare 6427334 v5), CC BY 4.0"},
        ]),
        ("GeneratedBy", [
            {"Name": "mne-bids", "Version": "0.19.0",
             "Description": "Converted the original EEGLAB .set recordings to "
                            "BIDS-EEG (EEGLAB format retained) using the scripts "
                            "in code/ (convert_to_bids.py, finalize_bids.py); "
                            "added nominal 10-20 template electrode positions and "
                            "enriched metadata from the source publication."},
        ]),
    ])
    w_json(BIDS / "dataset_description.json", obj)

# ---------------------------------------------------------------- README / CHANGES
def license_file():
    src = BIDS / "code" / "cc-by-4.0.txt"
    dst = BIDS / "LICENSE"
    if src.exists():
        shutil.copyfile(src, dst)
        print("wrote LICENSE")
    else:
        print("WARNING: code/cc-by-4.0.txt missing; LICENSE not written")

def readme():
    n_sub = SUMMARY["n_subjects"]
    n_ses = len(RECORDS)
    # aggregate stats for the glance table
    total_dev = sum(
        r["event_counts"].get("deviation_onset_left", 0)
        + r["event_counts"].get("deviation_onset_right", 0) for r in RECORDS)
    durs = sorted(r["duration_sec"] for r in RECORDS)
    tot_hours = sum(durs) / 3600.0
    # actual channel labels as written to channels.tsv / electrodes.tsv (the
    # original classic, upper-case nomenclature kept from the source files)
    chan_list = ("FP1, FP2, F7, F3, FZ, F4, F8, FT7, FC3, FCZ, FC4, FT8, T3, C3, "
                 "CZ, C4, T4, TP7, CP3, CPZ, CP4, TP8, A1, T5, P3, PZ, P4, T6, A2, "
                 "O1, OZ, O2")
    affil = "\n".join(
        f"{i+1}. {n}{(' (ORCID ' + o + ')') if o else ''} - {a}"
        for i, (n, o, a) in enumerate(AUTHOR_AFFIL))
    refs = "\n".join(f"- {r}" for r in RELATED_PUBS)
    txt = f"""# Multi-channel EEG recordings during a sustained-attention driving task

BIDS-EEG conversion of the **raw** dataset from:

> Cao, Z., Chuang, C.-H., King, J.-K. & Lin, C.-T. (2019).
> Multi-channel EEG recordings during a sustained-attention driving task.
> *Scientific Data* 6, 19. {PAPER_DOI}

Original data (CC BY 4.0): figshare {RAW_FIGSHARE} (raw),
{PRE_FIGSHARE} (pre-processed). Open-access full text: PMC6472414.

## Dataset at a glance

| Property | Value |
|---|---|
| Modality | EEG (`eeg`) |
| Task | `driving` (event-related lane-departure, sustained attention) |
| Participants | {n_sub} healthy adults (aged 22-28) |
| Sessions (recordings) | {n_ses} |
| Total recording time | ~{tot_hours:.0f} hours (per-session ~{durs[0]/60:.0f}-{durs[-1]/60:.0f} min) |
| Channels | 32 EEG (30 scalp + A1/A2 mastoid refs) + 1 `vehicle_position` (misc) |
| Sampling rate | 500 Hz, 16-bit |
| Lane-departure (deviation) trials | {total_dev} total |
| Event markers | 251/252 deviation L/R, 253 response onset, 254 response offset (+ undocumented 255 in 2 recordings) |
| Data format | EEGLAB `.set` (BIDS-EEG) |
| Electrode positions | nominal 10-20 template (not individually measured) |
| License | CC BY 4.0 |
| BIDS version | {BIDS_VERSION} |

## Authors and affiliations

{affil}

## Overview

{n_sub} participants (students/staff of National Chiao Tung University, aged
22-28, normal or corrected-to-normal vision, all holding a valid driver's
licence and with no history of psychological/neurological disorders or drug
use) performed a sustained-attention driving task (designed for ~90 minutes),
at one or more sessions on the same or different days, yielding **{n_ses} EEG
sessions**. Actual recording durations vary
(~{durs[0]/60:.0f}-{durs[-1]/60:.0f} min; median ~{durs[len(durs)//2]/60:.0f} min).
Recordings were collected between 2005 and 2012. Participants received ~USD $20
per session and completed a pre-test session to rule out simulator sickness.

### Task: event-related lane-departure paradigm

A virtual-reality (VR) dynamic driving simulator (built with WorldToolKit R9 and
Visual C++) was mounted on a six-degree-of-freedom Stewart motion platform, with
a real Ford Probe car frame and six projected scenes giving a near-360-degree
field of view. Participants drove a visually monotonous night-time straight
four-lane divided highway with no other traffic at a constant 100 km/h, keeping
the car centred in the third lane. Road position was quantised to 0-255 (lane
width 60 units). Lane-departure events were randomly induced with equal
probability to the left or right (**deviation onset**); the participant
counter-steered (**response onset**) to bring the car back to the lane centre
(**response offset**), using the steering wheel only (no accelerator/brake). The
next trial began 5-10 s after the previous one. The interval from deviation
onset to response onset is the **reaction time (RT)**, an index of fatigue and
drowsiness. The task was designed to run ~90 minutes without breaks; the actual
recorded duration varies by session (see the glance table and each
`sub-XX_sessions.tsv`).

## Acquisition

- Amplifier: Compumedics Neuroscan **Scan SynAmps2 Express** system (Compumedics
  Ltd., VIC, Australia). NOTE: the source paper inconsistently also refers to a
  "Scan NuAmps Express" system in one section.
- Cap: 32-channel **Quik-Cap** (Compumedics NeuroScan), Ag/AgCl electrodes.
- Acquisition software: Neuroscan Scan 4.5 (raw saved originally as .cnt).
- Sampling rate: 500 Hz; 16-bit quantisation.
- Electrodes: 30 scalp EEG electrodes (modified international 10-20 system) plus
  2 mastoid reference electrodes (A1, A2). Electrode-skin impedance kept < 5 kOhm
  (NaCl conductive Quik-Gel; Nuprep + 70% isopropyl-alcohol skin prep).
- Power-line frequency: 60 Hz (Taiwan).
- Channel order (32 EEG): {chan_list}.
  Classic names map to modern ones as T3/T4/T5/T6 = T7/T8/P7/P8.
- A 33rd channel, `vehicle_position` (BIDS type `misc`), stores the simulated
  car's lateral position (quantised 0-255) sampled with the EEG at 500 Hz. In
  the source files it is literally named "vehicle position"; the space was
  replaced by an underscore for BIDS.

### Electrode positions

The source recordings did **not** include measured electrode coordinates. For
convenience, each recording carries **nominal 10-20 template positions** (MNE
`standard_1020`) under the original channel names, written to
`*_electrodes.tsv` / `*_coordsystem.json`. These are idealised, identical across
all recordings, and are **not** individually measured - treat them as
approximate only.

## Events

Each `*_events.tsv` has `trial_type` (descriptive label) and `value` (original
integer trigger):

| value | trial_type             | meaning                                          |
|-------|------------------------|--------------------------------------------------|
| 251   | deviation_onset_left   | car drift induced toward the left                |
| 252   | deviation_onset_right  | car drift induced toward the right               |
| 253   | response_onset         | subject starts steering back toward lane centre  |
| 254   | response_offset        | subject finishes steering; car back at centre    |
| 255   | undocumented_255       | extra trigger in sub-54 & sub-55 only (21x); not defined in the source publication, meaning unknown |

## Subjects and sessions

Subject labels preserve the original numbering (`sub-01` = original `s01`), so
numbering is non-consecutive. Sessions `ses-01`, `ses-02`, ... are ordered
chronologically per subject. `sub-XX/sub-XX_sessions.tsv` maps each session to
the original recording file name, acquisition date, and the original one-letter
filename suffix (`m`/`n`) - an opaque label from the source naming whose meaning
is not defined in the original publication.

## Relationship to the pre-processed dataset

A separately published pre-processed version ({PRE_FIGSHARE}) applied a 1-Hz
high-pass and 50-Hz low-pass FIR filter and removed ocular/muscular artefacts
(manual eye-blink rejection + the EEGLAB AAR plug-in). **This** BIDS dataset
contains the **raw**, unfiltered recordings.

## Related publications using this dataset

{refs}

## Loading the data (Python / MNE)

```python
import mne
from mne_bids import BIDSPath, read_raw_bids
bp = BIDSPath(subject="01", session="01", task="driving",
              datatype="eeg", root="/path/to/this/dataset")
raw = read_raw_bids(bp)          # mne Raw with events as annotations
print(raw.info)                  # 32 EEG + vehicle_position (misc), 500 Hz
events, event_id = mne.events_from_annotations(raw)
```

The `vehicle_position` channel (type `misc`) holds the simulated car's lateral
position (quantised 0-255) and can be epoched alongside the EEG to recover the
steering trajectory and verify reaction times.

## Validation

This dataset passes the official `bids-validator` (Deno schema validator,
v1.15.0+) with **0 errors**. One non-blocking warning remains
(`MISSING_SESSION`): participants intentionally have different numbers of
sessions (1-5), which is an inherent property of the original study design, not
an error.

## Differences from the original figshare release

This is a faithful BIDS repackaging of the raw recordings; signal values and
event latencies are unchanged. The following organisational changes were made:

- Files renamed to BIDS entities; original names are preserved in each
  `sub-XX/sub-XX_sessions.tsv` (`original_filename`).
- Subject labels keep the original numbers (`sub-01` = `s01`), so they are
  non-consecutive (no s03, s07, s08, s10, ...).
- The behavioural channel "vehicle position" was renamed `vehicle_position`
  (space -> underscore) and typed `misc`.
- Numeric event codes were given descriptive `trial_type` labels while the
  original integer code is retained in the `value` column.
- Nominal 10-20 **template** electrode coordinates were added (the source
  provided none); they are documented as template-only in `*_coordsystem.json`.
- Metadata was enriched from the source paper and its ISA-Tab record (equipment,
  task, ethics, funding, references).

## License

Released under **CC BY 4.0** (see the `LICENSE` file), matching the original
data record and publication. When you use these data, please cite the original
Data Descriptor (see "How to acknowledge" / `dataset_description.json`).

## Provenance / source data

`sourcedata/` holds the exact materials used for this conversion:
- `meta/esm_extracted/` - ISA-Tab study metadata (Springer ESM, CC0).
- `meta/pmc_*` - open-access full text (PMC6472414) + BioC.
- `meta/crossref_article.json`, `meta/datacite_*` - citation metadata.
- `meta/figshare_*` - figshare API records (file manifests + checksums).
- `raw/manifest.tsv`, `raw/md5sums.txt`, `raw/download_progress.log` - download
  manifest, checksums, and verified-download log (all files md5-checked).
- `raw/*.set` - original EEGLAB files; `raw/code availability.zip` and the
  tutorial PDF as provided on figshare.
"""
    (BIDS / "README").write_text(txt)
    print("wrote README")
    (BIDS / "CHANGES").write_text(
        "1.0.0 2026-06-25\n"
        "  - BIDS-EEG conversion from the figshare raw dataset (6427334 v5)\n"
        "    using MNE-BIDS 0.19.0; metadata enriched from the source publication.\n")
    print("wrote CHANGES")

# ---------------------------------------------------------------- participants
def participants():
    by_sub = defaultdict(list)
    for r in RECORDS:
        by_sub[r["sub"]].append(r)
    rows = []
    for sub in sorted(by_sub):
        recs = by_sub[sub]
        rows.append([f"sub-{sub}", "s" + sub, "homo sapiens", "n/a", "n/a",
                     "n/a", "control", len(recs)])
    w_tsv(BIDS / "participants.tsv",
          ["participant_id", "original_id", "species", "age", "sex",
           "handedness", "group", "n_sessions"], rows)
    w_json(BIDS / "participants.json", OrderedDict([
        ("original_id", {"Description": "Subject identifier in the original figshare dataset."}),
        ("species", {"Description": "Binomial species name."}),
        ("age", {"Description": "Age in years. Not provided per subject in the "
                                "source data; the cohort was aged 22-28.",
                 "Units": "years"}),
        ("sex", {"Description": "Biological sex. Not provided in the source dataset.",
                 "Levels": {"M": "male", "F": "female"}}),
        ("handedness", {"Description": "Handedness. Not provided in the source dataset.",
                        "Levels": {"L": "left", "R": "right", "A": "ambidextrous"}}),
        ("group", {"Description": "Cohort group. All participants are healthy "
                                  "controls (no psychiatric/neurological/drug-use history).",
                  "Levels": {"control": "healthy control participant"}}),
        ("n_sessions", {"Description": "Number of recording sessions for this subject."}),
    ]))

# ---------------------------------------------------------------- sessions
SESSIONS_SIDECAR = OrderedDict([
    ("acq_date", {"Description": "Acquisition date (YYYY-MM-DD) parsed from the original file name."}),
    ("original_filename", {"Description": "Original recording file name on figshare (without extension)."}),
    ("recording_suffix", {"Description": "One-letter suffix ('m' or 'n') from the "
        "original file name. Its meaning is not specified in the source publication."}),
    ("original_run_index", {"Description": "Run index from the original file name when a "
        "subject had multiple recordings on the same date; n/a otherwise."}),
    ("duration_sec", {"Description": "Recording duration.", "Units": "s"}),
    ("n_deviation_trials", {"Description": "Number of lane-departure (deviation onset) trials."}),
    ("n_events", {"Description": "Total number of event markers in the recording."}),
])

def sessions():
    by_sub = defaultdict(list)
    for r in RECORDS:
        by_sub[r["sub"]].append(r)
    for sub in sorted(by_sub):
        recs = sorted(by_sub[sub], key=lambda r: r["ses"])
        rows = []
        for r in recs:
            ec = r["event_counts"]
            n_dev = ec.get("deviation_onset_left", 0) + ec.get("deviation_onset_right", 0)
            rows.append([
                f"ses-{r['ses']}", r["acq_date"], r["stem"], r["suffix"],
                r["runidx"] if r["runidx"] else "n/a",
                r["duration_sec"], n_dev, r["n_events"],
            ])
        w_tsv(BIDS / f"sub-{sub}" / f"sub-{sub}_sessions.tsv",
              ["session_id", "acq_date", "original_filename",
               "recording_suffix", "original_run_index", "duration_sec",
               "n_deviation_trials", "n_events"], rows)
        # per-subject sidecar (BIDS has sessions metadata only at subject level,
        # not at dataset root).
        w_json(BIDS / f"sub-{sub}" / f"sub-{sub}_sessions.json", SESSIONS_SIDECAR)

# ---------------------------------------------------------------- events sidecar
def events_json():
    obj = OrderedDict([
        ("onset", {"Description": "Event onset relative to recording start.", "Units": "s"}),
        ("duration", {"Description": "Event duration.", "Units": "s"}),
        ("trial_type", {"Description": "Descriptive event label.",
                        "Levels": dict(TRIAL_TYPE_LEVELS), "HED": dict(HED_TAGS)}),
        ("value", {"Description": "Original integer trigger value recorded with the EEG.",
                   "Levels": dict(EVENT_VALUE_LEVELS)}),
        ("sample", {"Description": "Onset expressed in samples (at 500 Hz)."}),
    ])
    w_json(BIDS / "task-driving_events.json", obj)
    # mne-bids writes a generic per-run *_events.json; under the BIDS inheritance
    # principle the nearer per-run file overrides the root one key-by-key, so we
    # must write the rich dictionary into every per-run sidecar too.
    n = 0
    for jpath in sorted(BIDS.rglob("*_task-driving_events.json")):
        if jpath.name == "task-driving_events.json":
            continue
        jpath.write_text(json.dumps(obj, indent=4, ensure_ascii=False) + "\n")
        n += 1
    print(f"enriched {n} per-run events.json")

# ---------------------------------------------------------------- drop non-electrode rows
def clean_electrodes():
    """Remove the behavioural vehicle_position channel from *_electrodes.tsv
    (it is a misc channel, not a scalp electrode)."""
    n = 0
    for tpath in sorted(BIDS.rglob("*_electrodes.tsv")):
        lines = tpath.read_text().splitlines()
        kept = [lines[0]] + [ln for ln in lines[1:]
                             if ln.split("\t")[0] != "vehicle_position"]
        if len(kept) != len(lines):
            tpath.write_text("\n".join(kept) + "\n")
            n += 1
    print(f"cleaned vehicle_position from {n} electrodes.tsv")

# ---------------------------------------------------------------- patch eeg.json
def patch_eeg_json():
    patch = OrderedDict([
        ("InstitutionName", "National Chiao Tung University"),
        ("InstitutionAddress", "Brain Research Center, Hsinchu, Taiwan"),
        ("Manufacturer", "Compumedics Neuroscan"),
        ("ManufacturersModelName", "Scan SynAmps2 Express (the source paper also "
                                    "refers to a Scan NuAmps Express system)"),
        ("CapManufacturer", "Compumedics NeuroScan"),
        ("CapManufacturersModelName", "Quik-Cap (32-channel)"),
        ("SoftwareVersions", "Neuroscan Scan 4.5"),
        ("EEGReference",
         "Mastoid reference electrodes A1 and A2 placed on opposite lateral "
         "mastoid bones (both recorded as data channels)."),
        ("EEGGround", "n/a"),
        ("EEGPlacementScheme",
         "Modified international 10-20 system: 30 scalp electrodes plus mastoid "
         "references A1, A2 (classic nomenclature; T3/T4/T5/T6 = T7/T8/P7/P8)."),
        ("HardwareFilters", "n/a"),
        ("SoftwareFilters", "n/a"),
        ("TaskName", "driving"),
        ("TaskDescription",
         "Event-related lane-departure sustained-attention driving task "
         "(designed for ~90 min; actual recording durations vary) in a VR "
         "driving simulator on a six-degree-of-freedom Stewart motion platform. "
         "Night-time straight four-lane highway at 100 km/h; random left/right "
         "lane drifts to which the participant counter-steers."),
        ("Instructions",
         "Keep the car cruising in the centre of the third lane and steer it "
         "back to the centre as quickly as possible whenever it drifts; use the "
         "steering wheel only (no accelerator or brake)."),
    ])
    n = 0
    for jpath in sorted(BIDS.rglob("*_task-driving_eeg.json")):
        obj = json.loads(jpath.read_text())
        obj.update(patch)
        jpath.write_text(json.dumps(obj, indent=4, ensure_ascii=False) + "\n")
        n += 1
    print(f"patched {n} eeg.json sidecars")

# ---------------------------------------------------------------- patch coordsystem
def patch_coordsystem():
    n = 0
    note = (
        "NOMINAL TEMPLATE positions from the MNE 'standard_1020' montage "
        "(modified international 10-20 system), identical for every recording and "
        "NOT individually measured/digitised; the source dataset provided no "
        "electrode locations. Use as approximate scalp positions only. "
    )
    # canonical mne-bids CapTrak description (kept verbatim, appended after the note)
    canonical = (
        "The X-axis goes from the left preauricular point (LPA) through the right "
        "preauricular point (RPA). The Y-axis goes orthogonally to the X-axis "
        "through the nasion (NAS). The Z-axis goes orthogonally to the XY-plane "
        "through the vertex of the head. This corresponds to a \"RAS\" orientation "
        "with the origin of the coordinate system approximately between the ears. "
        "See Appendix VIII in the BIDS specification."
    )
    for jpath in sorted(BIDS.rglob("*_coordsystem.json")):
        obj = json.loads(jpath.read_text())
        # idempotent: always reconstruct from note + canonical (do not prepend
        # to whatever is already there, which duplicates on re-runs)
        obj["EEGCoordinateSystemDescription"] = note + canonical
        jpath.write_text(json.dumps(obj, indent=4, ensure_ascii=False) + "\n")
        n += 1
    print(f"patched {n} coordsystem.json")

def main():
    dataset_description()
    license_file()
    readme()
    participants()
    sessions()
    events_json()
    patch_eeg_json()
    patch_coordsystem()
    clean_electrodes()
    print("FINALIZE DONE")

if __name__ == "__main__":
    main()
