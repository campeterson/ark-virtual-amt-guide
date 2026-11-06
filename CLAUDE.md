# Virtual AMT Guide — Build Instructions

The governing plan is Cam's **"Virtual AMT Guide – Plan"** doc. This file turns that plan into build steps. If the two disagree, the plan wins. Flag the conflict; don't resolve it yourself.

Author: Cam (A&P, aviation maintenance lecturer). Prefers direct, critical feedback.

---

## What we're building

A set of instructions that lets each AMT student build their own Claude-based virtual tutor. The tutor guides students through aviation maintenance topics in a back-and-forth chat, using the **FAA ACS (FAA-S-ACS-1)** and the **FAA-H-8083 handbooks** as its only sources.

**How students use it:**
- Each student sets up their own Claude account and creates their own Claude **Project**.
- Cam provides **one standard set of project instructions** to paste in, so every student ends up with the same tutor.
- Cam provides a **list of source links**, plus files to upload as a fallback.

This repo provides those instructions and hosts the sources.

**First subject: Landing Gear Systems.** Build only this subject for now, but structure everything so the other subjects can be added the same way later.

---

## Subjects and categories

Subjects are organized into three categories that match the three Areas of FAA-S-ACS-1:

| Category | ACS Area | Code prefix |
|---|---|---|
| `general` | I. General | `AM.I` |
| `airframe` | II. Airframe | `AM.II` |
| `powerplant` | III. Powerplant | `AM.III` |

Each subject is one ACS Subject (lettered task) within its Area. Slugs come from the ACS subject title. For example, Landing Gear Systems is **`AM.II.E`**, so it lives at `subjects/airframe/landing-gear-systems/`.

## ACS data source

ACS data comes from **https://github.com/campeterson/faa-acs-data** (Cam's extractor). Use `FAA-S-ACS-1/data/elements.json` or `FAA-S-ACS-1.json` from that repo. Don't re-parse the ACS PDF, and don't type elements by hand.

- Generate each subject's `acs.md` with a script (`scripts/build_acs.py`) that filters by subject code (e.g. `AM.II.E`) and writes the subject's objective plus its Knowledge, Risk Management and Skill elements, each with its code and verbatim text. Exclude elements marked `archived`.
- Pull the data in as a git submodule or pinned download, and record the commit used in the generated file so it's clear which ACS revision a subject was built from.
- The mechanic ACS has **no `References` field**, so each subject's handbook chapters must be chosen by hand. Confirm the chapter list with Cam.
- Sanity check for Landing Gear Systems: it should produce 13 K, 6 R and 21 S elements (`AM.II.E.K1`–`K13`, `R1`–`R6`, `S1`–`S21`).

Eventually a separate system will provide all of this data. Until then, keep this step to the one script so it's easy to replace.

---

## Source hosting rules

- Split the 8083 handbooks into **individual chapters**. They're public domain, so the converted chapters are committed to the repo.
- Convert chapters to **Markdown**, not PDF. PDF diagrams and tables often come through garbled, so:
  - Rebuild tables as Markdown tables and check every cell against the PDF.
  - Keep figure numbers and captions. Put a plain-text description of each figure under the caption, written only from what the figure and the surrounding text show.
  - Keep the handbook's headings, section numbering and page references so the tutor can cite them.
  - Don't paraphrase, summarize or "improve" the text. This is a faithful conversion.
- Host on **GitHub**. Students get **raw file links or a GitHub Pages site**, not normal repo pages, because the extra page clutter gets in Claude's way.
- Include a simple **index page** listing every chapter and its link.
- **Fallback:** if Claude doesn't fetch a link, the student downloads the chapter and uploads it to their project. Every chapter must work as a standalone upload.

---

## Repo layout (proposed; confirm with Cam before deviating)

```
CLAUDE.md                          ← this file
sources/                           ← original 8083 handbook PDFs
vendor/faa-acs-data/               ← ACS data (submodule or pinned copy)
scripts/build_acs.py               ← generates each subject's acs.md from the ACS data
handbooks/<handbook-id>/<chNN-slug>.md   ← converted chapters (shared; a chapter may serve several subjects)
subjects/
  general/
  airframe/
    landing-gear-systems/
      acs.md                       ← generated: AM.II.E elements, verbatim
      sources.md                   ← the source list students use: raw links to acs.md + handbook chapters
  powerplant/
project-instructions.md            ← the ONE standard set of Project instructions students paste in
index.md                           ← every subject (grouped by general / airframe / powerplant) and every chapter, with raw links
```

---

## Tutor behavior (`project-instructions.md`)

From the plan (marked "to draft"):
- Ask questions to guide the student instead of handing over answers.
- Make no assumptions. Base everything on what it reads in the reliable sources (ACS, 8083 handbooks).

Also needed for this to work:
- Tell the tutor to fetch the subject's source links. If a fetch fails, tell the student exactly which file to download and upload.
- The instructions must be **subject-agnostic**: one paste works for every subject. The student picks a category (general, airframe or powerplant) and then a subject, and the tutor uses that subject's `sources.md`.
- The tutor treats the subject's ACS elements as the map of what the student must know, and uses the K, R and S codes to track what's been covered.
- When a question goes beyond the loaded sources, the tutor says so instead of answering from general knowledge.

**Before drafting:** Cam may have earlier notes on tutor behavior (possibly in Google Drive; not found in chat history). Ask Cam for them first. Don't draft over them.

---

## Out of scope (deferred in the plan)

- **ASA test-prep questions:** postponed until their license is checked. Don't add them or reproduce them.
- **Scenario-based troubleshooting add-on** and the **pre/post-class quiz plan** are related but not part of this build. Don't build them here.

---

## Steps (from the plan's next steps)

1. Ask Cam for any earlier tutor-behavior notes.
2. Draft `project-instructions.md`. **Check in with Cam.**
3. Write `scripts/build_acs.py` and generate `subjects/airframe/landing-gear-systems/acs.md`. Verify the 13/6/21 element counts.
4. Convert and host the first handbook chapters. For Landing Gear Systems, that's the landing gear chapter of the AMT Airframe handbook (FAA-H-8083-31; identify the exact volume and chapter from the PDF in `sources/`). Check the ACS elements against the chapter. If any element, such as skis and floats (K13) or jacking (S5, R2), is covered in a different chapter, propose adding that chapter to the source list. Build `sources.md` and `index.md`.
5. Set up GitHub Pages and confirm the raw links fetch cleanly as plain text.
6. Test with this one subject before rolling out to students: run the tutor in a claude.ai Project with the pasted instructions, check that it fetches the links, cites the handbook, and guides with questions. Then report what broke.

Commit after each step. Don't push without asking.
