# VibeRank

**Five fixed answers, a calibrated holistic read, then an Elo estimate.**

VibeRank is a research MVP for testing whether a strong evaluator can read five free-form
answers and recover a useful estimate of a target model's public benchmark Elo at very low
cost. A live head-to-head on 18 known-Elo models across five families settled the
architecture: the grader's *whole-transcript holistic read*, affine-corrected against a
reference bank, is the primary estimator; the per-answer ordinal channel remains as the
inspectable diagnostic. The current default freezes the questions so grader behavior can be
inspected without question generation changing between runs.

For every debug step:

1. the target receives one of five fixed questions;
2. the evaluator receives the question, private reference answer, rubric, four answer anchors,
   and the target response;
3. it grades the response as a probability distribution over wrong, major error,
   minor error, and fully correct;
4. the Elo posterior is updated.

The dashboard exposes that exact grader context after the answer is collected. Reference answers
and rubrics are never included in the target-model prompt.

The implementation includes:

- five deterministic debug questions covering logic, probability, algorithms, state transforms,
  and dependency planning;
- live grading with Mistral;
- Mistral and OpenRouter target-model adapters;
- a four-category generalized partial-credit Elo model;
- soft grader probabilities rather than a forced hard label;
- a calibrated direct-regression "texture" channel that folds the grader's per-answer
  apparent-Elo read into the posterior (see below);
- a mean estimate and 90% posterior interval after every answer;
- author, target, and grader token accounting;
- a dependency-free Python HTTP API and browser dashboard;
- fixed-question simulation for free local sanity checks;
- preserved adaptive authoring behind `question_mode: "authored"` for the next experiment.

## Run it

Requires Python 3.11 or newer.

```powershell
python -m unittest discover -s tests -v
python -m viberank
```

Then open <http://127.0.0.1:8000>.

Simulation works without API keys. Live runs require:

```powershell
$env:MISTRAL_API_KEY = "..."
$env:OPENROUTER_API_KEY = "..." # only for OpenRouter targets
$env:MISTRAL_GRADER_MODEL = "mistral-medium-3.5" # grader
python -m viberank
```

Secrets are read only on the server and are never sent to the browser.

## Cost model

A live fixed-question evaluation makes two calls per question:

1. target model answers;
2. evaluator grades the answer.

VibeRank reports prompt, completion, and total tokens separately for authoring, target answers,
and grading. Author usage is zero in fixed mode, so the same accounting shape can be compared with
the later three-call authored mode. Any future verification or filtering call must be included in
total evaluation cost.

## Measurement model

The five fixed questions currently have provisional target difficulties of 1300, 1700, 2100,
1500, and 1900 Elo, plus three ordered transition thresholds each. Q4 and Q5 deliberately return
to the middle of the range after the difficult Q3, making them useful cross-checks for a suspicious
one-direction trajectory. These values are debugging assumptions, not calibrated claims. For
ability `theta`, the generalized partial-credit model assigns probabilities to the four ordinal
grades.

If the evaluator returns a soft grade distribution `q`, the Elo likelihood is:

```text
L(theta) = sum_k q[k] * P(grade=k | theta, fixed question)
```

The API returns the posterior mean, standard deviation, 90% interval, density series, realized
entropy reduction, and cumulative token usage after every question.

## Holistic channel (primary estimator)

After every answer, the grader reads the whole transcript so far — questions, private
references, rubrics, and the target's answers — and emits a direct Elo read. Raw reads carry a
systematic scale distortion (the grader over-reads reasoning-styled output and stretches the
top of the scale), so a per-prefix affine correction is fit against a reference bank of models
with known public Elo, with residual noise measured per prefix length and t-inflated for the
bank size. The corrected read is the headline estimate and interval.

Measured leave-one-out on the live bank: the raw holistic read beats the ordinal IRT channel
outright, and the affine correction improves the raw read's MAE by roughly a third. Fusing the
ordinal channel into the estimate was tested and *rejected* — its errors are correlated with
the holistic read (same grader, same questions), so fusion degrades the final metric. The
ordinal per-question grades stay in the product as the audit trail, not as evidence.

Fit or refresh the calibration from a collected bank:

```powershell
python -m experiments.method_battle          # collect/extend the reference bank
python -m viberank.calibrate_holistic        # fit; writes holistic-calibration.json
```

The channel activates only when the artifact exists, is usable, and was fit for the exact
grader in use; otherwise the server falls back to the ordinal posterior and says so.

## Direct-regression texture channel

**Status: empirically dead on live data.** Per-answer apparent-Elo reads measured r² of
0.001–0.018 against public Elo across the reference bank — the read collapses into an echo of
the correctness grade. The machinery is retained because its honesty guards correctly refuse
to activate on such a fit, and because the transcript-level version of the same idea (the
holistic channel above) is what works. Simulation results below validate the estimator only.

Four ordinal categories extract at most two bits per answer, which caps the five-question
posterior at roughly 140–160 Elo standard deviation. Most of the ability signal in a free-form
answer lives in its texture — reasoning depth, error character, how the hard part is handled —
which the grader already sees. The texture channel recovers it:

1. The grader emits `apparent_elo`, a raw single-answer ability read, on the same grading call
   (zero extra API cost).
2. `python -m viberank.calibrate` fits the measurement model `raw = a + b * true` against models
   of known public Elo (classical calibration, so extreme reads are not shrunk toward the
   calibration population), and decomposes residual noise into a shared per-model grader bias
   `tau` and independent per-answer noise `sigma_w`, both in Elo.
3. During an evaluation, the running mean of k calibrated reads enters the posterior as one
   Gaussian likelihood with variance `tau^2 + sigma_w^2 / k`, so correlated reads never
   overcount, and `tau` remains a hard information floor no number of questions can beat.

Honesty guards, in order: the channel stays off without a calibration file; a fit on too few
models, too narrow an Elo span, or with no positive raw-to-true signal is marked unusable and
refused; noise components carry a small-sample t inflation (`df/(df-2)`) so a lucky draw cannot
manufacture overconfidence; measured noise is floored at `sigma_w >= 50`, `tau >= 25`; and a
calibration only activates for the grader it was fit on — a simulation fit never applies to live
runs, and changing `MISTRAL_GRADER_MODEL` deactivates the channel until recalibration.

Commands:

```powershell
python -m viberank.calibrate --simulate                  # free plumbing check + demo
python -m viberank.calibrate --provider openrouter `
  --models "model-id=1521,other-id=1645,third-id=1210"   # live fit against known Elos
```

The file is written to `calibration.json` (override with `$env:VIBERANK_CALIBRATION_PATH`).
Use as many calibration models as feasible and span an Elo range wider than the targets you
plan to evaluate; the shared-bias component is estimated with `models - 1` degrees of freedom,
so its t inflation shrinks as models are added.

In simulation with a simulated calibration (same seeds, 5 questions), the channel drops the
posterior SD from about 140 to about 80 and the mean absolute error from about 110 to about 70,
with 90% interval coverage staying near nominal. Those numbers validate the estimator only; the
live claim still requires a real calibration run against held-out models.

## Experimental standard

The only primary outcomes are:

- absolute Elo error after questions 1, 2, and 3;
- total API cost after questions 1, 2, and 3.

Interval coverage is a secondary calibration check. The immediate debugging question is whether
the grader's probabilities, explanation, error label, and satisfied criteria make sense given the
displayed reference, rubric, anchors, and target response. Elo accuracy still requires held-out
models with known Elo and empirical calibration of the fixed-question difficulties.

## API

- `GET /api/config`
- `GET /api/leaderboard-models?limit=200&minimum_benchmarks=5`
- `POST /api/evaluate`
- `POST /api/validate`

Example free simulation:

```json
{
  "provider": "simulation",
  "model": "synthetic-1700",
  "target_elo": 1700,
  "questions": 5,
  "question_mode": "fixed",
  "seed": 7
}
```

Omit `question_mode` to use the current default, `fixed`. The adaptive implementation is retained
for later experiments with `"question_mode": "authored"` or
`$env:VIBERANK_QUESTION_MODE = "authored"`.

`/api/leaderboard-models` reads current targets from
<https://aibenchmarks.dev/data/unified-irt.json>.
