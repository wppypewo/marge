# Marge

English | [繁體中文](README.zh-TW.md)

Grading students' handwritten French essays with AI models that are free or under your own control. The name is French for *margin*, where a teacher writes corrections next to an essay.

**Stage: evaluation done, product not started.** This repository holds the product requirements, the decision log and the evaluation tools; the student-facing app does not exist yet.

The documents are in Traditional Chinese.

## The problem

Students in a French writing course hand-write a short essay every week, then photograph it and run the teacher's grading prompt in Gemini: OCR first, then grading. Since 2026-10-09 the free Gemini tier routes most requests to Flash-Lite, and grading quality dropped. On the same essay, where the prompt allows fewer than 12 ⚠️ marks, Flash-Lite placed 28 and only marked positions without giving corrections.

Most free alternatives train on the essays they receive. An evaluation from 2026-10-16 to 10-23 compared the free and paid Gemini tiers, Nemotron 3.5 Super VL and dots on OpenRouter, and Qwen3.6 running locally.

## Evaluation summary

| Model | Where it runs | Does it train on essays? | Result |
|---|---|---|---|
| Gemini free (Flash-Lite) | Google | — | 28 ⚠️ marks (limit: fewer than 12), positions only, no corrections; missed that the essay was over the word limit; B2 rewrite 116 words, under the 120 minimum |
| Nemotron 3.5 Super VL | OpenRouter free endpoint | **Requires** opting in to "free endpoints may train on request data"; returns 404 otherwise | Best quality among free models; about 235 s per essay; quota about 7 essays a day |
| dots | OpenRouter free endpoint | No opt-in needed | Below Nemotron on most items; its OCR "corrected" the student's mistakes the most (18 words off); about 325 s; needs an extra `oui` turn |
| Qwen3.6 | Local machine | Data never leaves the computer | Needs 24 GB of memory; got the word count wrong in both runs |

In short: the best free model costs the students their essays. Cerebras and Cloudflare Workers AI, whose official terms say they do not keep or train on data, have not been tested yet. Four open decisions (provider, student app, how the prompt is delivered, where results are stored) are in [PRD section 3.2](PRD.md#32-待定決策).

Figures and their sources are in PRD sections 1.1, 3.1 and 3.2. The full evaluation report contains student essays and is not published (see below).

## Files

| File | Contents |
|---|---|
| [`PRD.md`](PRD.md) | Problem, target users, functional requirements F1–F11, open decisions D1–D4, ADRs, log, open issues |
| [`docs/MAINTAINING.md`](docs/MAINTAINING.md) | Rules for updating the PRD and citing evidence, what each script is for, how this repository relates to the evidence folder |
| [`tools/bench/`](tools/bench/) | Evaluation scripts: run the grading flow on a local model, compare OCR, check grading format, build and fill blind-review forms |
| [`tools/report/`](tools/report/) | Turn the report into a PDF and sync it to Google Drive |

## Evaluation evidence is not public

The evaluation report, model replies and raw OCR live in a sibling folder, `../local-first-ai/`. It contains student essays, so it is not on GitHub. Links in the PRD that point to `../local-first-ai/` only work locally.

## Using the tools

The Python scripts use only the standard library. `build_pdf.sh` prints the PDF with headless Google Chrome and `sync_drive.sh` needs Google Drive for desktop; both have only been tested on macOS. Usage is at the top of each script. Run them from the evidence folder:

```bash
# Compare OCR output with the reference transcription
python3 -I ../marge/tools/bench/ocr_diff.py OCR_<model>.txt
# Check grading format (number of ⚠️ marks, word counts, the seven section headings)
python3 -I ../marge/tools/bench/check_grading.py reply_<model>.txt
```

The evidence folder defaults to `../local-first-ai`; set `MARGE_EVIDENCE` to change it.

## License

[MIT](LICENSE), covering the code and documents in this repository.
