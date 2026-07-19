"""Assemble the VibeRank pitch page with both figure SVGs inlined.

Edit the HTML template below (all presentation copy lives in it), then:

    python -m experiments.build_pitch
"""
from pathlib import Path

EXP = Path(__file__).resolve().parent
OUT = EXP / "viberank_pitch.html"

trajectory_svg = (EXP / "trajectory_pitch.svg").read_text(encoding="utf-8")
scatter_svg = (EXP / "external_scatter.svg").read_text(encoding="utf-8")
graders_svg = (EXP / "grader_compare.svg").read_text(encoding="utf-8")

HTML = """
<title>VibeRank — Automating the Vibe Check</title>
<style>
  :root {
    --paper: #faf9f6;
    --plate: #fcfcfb;
    --ink: #16140f;
    --ink-2: #55524c;
    --ink-3: #8a857b;
    --accent: #d95b26;
    --accent-soft: #f3e3d9;
    --hair: #e6e2d8;
    --mono-bg: #f1eee6;
    --good: #1d6b32;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) {
      --paper: #16140f; --plate: #fcfcfb; --ink: #f2efe7; --ink-2: #b6b0a3;
      --ink-3: #7d786d; --accent: #ef7b45; --accent-soft: #33220f;
      --hair: #2c2921; --mono-bg: #211e17; --good: #58b573;
    }
  }
  :root[data-theme="dark"] {
    --paper: #16140f; --plate: #fcfcfb; --ink: #f2efe7; --ink-2: #b6b0a3;
    --ink-3: #7d786d; --accent: #ef7b45; --accent-soft: #33220f;
    --hair: #2c2921; --mono-bg: #211e17; --good: #58b573;
  }
  :root[data-theme="light"] {
    --paper: #faf9f6; --plate: #fcfcfb; --ink: #16140f; --ink-2: #55524c;
    --ink-3: #8a857b; --accent: #d95b26; --accent-soft: #f3e3d9;
    --hair: #e6e2d8; --mono-bg: #f1eee6; --good: #1d6b32;
  }
  * { box-sizing: border-box; }
  body {
    background: var(--paper); color: var(--ink);
    font: 17px/1.65 system-ui, -apple-system, "Segoe UI", sans-serif;
    margin: 0; padding: 0 20px 96px;
  }
  .col { max-width: 700px; margin: 0 auto; }
  .wide { max-width: 960px; margin: 0 auto; }
  .mono { font-family: ui-monospace, "Cascadia Code", Consolas, monospace; }
  .serif { font-family: "Iowan Old Style", Charter, Georgia, "Times New Roman", serif; }

  header { padding: 72px 0 8px; }
  .brand { display: flex; align-items: center; gap: 10px; color: var(--ink-3);
    font-size: 13px; letter-spacing: .14em; text-transform: uppercase; }
  .brand b { color: var(--accent); letter-spacing: normal; font-size: 15px; }
  h1 { font-family: "Iowan Old Style", Charter, Georgia, serif; font-weight: 500;
    font-size: clamp(34px, 6vw, 54px); line-height: 1.12; letter-spacing: -0.01em;
    margin: 20px 0 0; text-wrap: balance; }
  h1 .strike { position: relative; white-space: nowrap; }
  h1 .strike::after { content: ""; position: absolute; left: -2px; right: -2px;
    top: 54%; height: 3px; background: var(--accent); transform: rotate(-1.2deg); }
  .dek { color: var(--ink-2); font-size: 20px; line-height: 1.55; margin: 22px 0 0;
    text-wrap: balance; }
  .dek em { font-style: normal; color: var(--accent); font-weight: 600; }

  .statline { display: flex; flex-wrap: wrap; gap: 12px 36px; margin: 40px 0 0;
    padding: 18px 0; border-top: 1px solid var(--hair); border-bottom: 1px solid var(--hair); }
  .stat { min-width: 120px; }
  .stat .v { font-family: ui-monospace, Consolas, monospace; font-size: 26px;
    font-weight: 600; font-variant-numeric: tabular-nums; }
  .stat .v.accent { color: var(--accent); }
  .stat .k { color: var(--ink-3); font-size: 12px; letter-spacing: .1em;
    text-transform: uppercase; margin-top: 2px; }

  section { margin-top: 72px; }
  .eyebrow { color: var(--accent); font-size: 13px; letter-spacing: .16em;
    text-transform: uppercase; font-weight: 600; margin: 0 0 10px; }
  h2 { font-family: "Iowan Old Style", Charter, Georgia, serif; font-weight: 500;
    font-size: 30px; line-height: 1.2; margin: 0 0 18px; text-wrap: balance; }
  p { margin: 0 0 16px; color: var(--ink); }
  p.quiet, li.quiet { color: var(--ink-2); }
  .pull { font-family: "Iowan Old Style", Charter, Georgia, serif; font-size: 23px;
    line-height: 1.45; color: var(--ink); border-left: 3px solid var(--accent);
    padding: 4px 0 4px 22px; margin: 26px 0; }
  .pull .attr { display: block; font-family: system-ui, sans-serif; font-size: 14px;
    color: var(--ink-3); margin-top: 10px; }

  figure { margin: 28px 0 0; }
  .plate { background: var(--plate); border: 1px solid var(--hair); border-radius: 6px;
    padding: 10px; overflow-x: auto; }
  .plate svg { display: block; min-width: 640px; width: 100%; height: auto; }
  figcaption { color: var(--ink-3); font-size: 13.5px; line-height: 1.55; margin-top: 10px; }
  figcaption b { color: var(--ink-2); }

  table { border-collapse: collapse; width: 100%; margin: 20px 0 6px; font-size: 15.5px; }
  th { text-align: left; color: var(--ink-3); font-size: 12px; letter-spacing: .1em;
    text-transform: uppercase; font-weight: 600; padding: 8px 14px 8px 0;
    border-bottom: 1px solid var(--hair); }
  td { padding: 9px 14px 9px 0; border-bottom: 1px solid var(--hair); vertical-align: top; }
  td.num { font-family: ui-monospace, Consolas, monospace;
    font-variant-numeric: tabular-nums; white-space: nowrap; }
  td .win { color: var(--good); font-weight: 600; }
  tr.us td { background: linear-gradient(90deg, var(--accent-soft), transparent 85%); }
  tr.us td:first-child { padding-left: 10px; border-radius: 4px 0 0 4px; }

  .steps { counter-reset: step; margin: 24px 0 0; padding: 0; list-style: none; }
  .steps li { counter-increment: step; display: grid;
    grid-template-columns: 44px 1fr; gap: 14px; padding: 14px 0;
    border-top: 1px solid var(--hair); }
  .steps li::before { content: counter(step, decimal-leading-zero);
    font-family: ui-monospace, Consolas, monospace; color: var(--accent);
    font-size: 15px; padding-top: 2px; }
  .steps b { display: block; margin-bottom: 2px; grid-column: 2; }
  .steps span { color: var(--ink-2); font-size: 15.5px; grid-column: 2; }

  .demo { background: var(--mono-bg); border: 1px solid var(--hair); border-radius: 6px;
    padding: 22px 24px; margin-top: 24px; font-family: ui-monospace, Consolas, monospace;
    font-size: 14.5px; line-height: 1.8; overflow-x: auto; }
  .demo .c { color: var(--ink-3); }
  .demo .a { color: var(--accent); font-weight: 600; }
  .demo .g { color: var(--good); }
  .demo table { font-family: inherit; font-size: inherit; margin: 8px 0 0; }
  .demo td, .demo th { border: none; padding: 2px 22px 2px 0; }

  .caveats { margin: 20px 0 0; padding: 0 0 0 20px; }
  .caveats li { margin-bottom: 12px; color: var(--ink-2); font-size: 15.5px; }
  .caveats li b { color: var(--ink); }

  footer { margin-top: 88px; padding-top: 22px; border-top: 1px solid var(--hair);
    color: var(--ink-3); font-size: 13.5px; display: flex; align-items: center;
    gap: 12px; flex-wrap: wrap; }
  footer .cat { color: var(--accent); }
</style>

<div class="col">
  <header>
    <div class="brand"><b>VibeRank</b><span>· a $0.04 model evaluation</span></div>
    <h1>&ldquo;Don&rsquo;t <span class="strike">run benchmarks</span>. Just vibe-check the model.&rdquo;</h1>
    <p class="dek">Everyone says it. We <em>automated it</em> — five answers, one grader
      reading the whole transcript, calibrated against models of known Elo. It costs four
      cents, takes about a minute, and tracks the big capability indices.</p>
    <div class="statline">
      <div class="stat"><div class="v accent">$0.039</div><div class="k">per model, measured</div></div>
      <div class="stat"><div class="v">±86</div><div class="k">Elo MAE, 18-model LOO</div></div>
      <div class="stat"><div class="v">0.90</div><div class="k">Spearman vs Epoch ECI</div></div>
      <div class="stat"><div class="v">~1 min</div><div class="k">per model, end to end</div></div>
    </div>
  </header>

  <section>
    <p class="eyebrow">The problem</p>
    <h2>A benchmark buys a thousand-token trace and keeps one bit</h2>
    <p>A full capability index runs dozens of benchmarks with thousands of prompts each.
      Every prompt makes a model produce a long reasoning trace — and then the harness keeps
      a single right-or-wrong bit and throws the trace away. Multiply by reasoning-mode token
      prices and published run costs land in the <span class="mono">$10&sup2;–$10&sup3;</span>
      range per model; arena rankings need thousands of human votes instead. Almost all of
      that spend is confirmation, not information.</p>
    <p class="quiet">Meanwhile the standard practitioner advice is the opposite of a
      benchmark: ask the model five things you understand deeply, read <i>how</i> it answers,
      and trust that read. The vibe check works because ability leaks through every sentence
      of a transcript — the texture of a mistake, the shape of a derivation, what the model
      does with the hard part. A grader model sees all of that too. The only thing a raw vibe
      lacks is a scale.</p>
  </section>

  <section>
    <p class="eyebrow">The method</p>
    <h2>A vibe check with a unit attached</h2>
    <ol class="steps">
      <li><b>Five fixed reasoning questions</b><span>logic, probability, algorithm tracing,
        state transforms, dependency planning — frozen, so grader behavior is inspectable
        run to run.</span></li>
      <li><b>The grader reads the whole transcript</b><span>after every answer,
        mistral-medium-3.5 sees questions, private references, rubrics, and all answers so
        far, and names an Elo. Reading jointly is what makes it work: per-answer scores
        measured near-zero signal, the transcript-level read is strong.</span></li>
      <li><b>Calibration puts it on the public scale</b><span>the raw read is affine-corrected
        against a reference bank of 18 models with known Elo (5 families, 1210–1749), with
        residual noise measured per prefix length — so the interval is measured, never
        asserted.</span></li>
    </ol>
    <figure>
      <div class="plate">__GRADERS_SVG__</div>
      <figcaption><b>The method survives a grader swap.</b> Each grader speaks its own raw
        Elo dialect (their scales differ by up to 80 points on identical transcripts), but
        after its own cheap refit, every Mistral from Small up lands within ~20 Elo of the
        shipped accuracy — pick a price point.</figcaption>
    </figure>
  </section>
</div>

<div class="wide">
  <section>
    <p class="eyebrow" style="max-width:700px;margin-left:auto;margin-right:auto">Convergence</p>
    <div class="col" style="margin-bottom:4px">
      <h2>Three answers is enough</h2>
      <p>Error against public Elo, leave-one-out across the 18-model bank. The calibrated
        estimate lands at <span class="mono">107</span> MAE after a single answer and reaches
        its floor of <span class="mono">≈86</span> by the second or third — the fourth and
        fifth are confirmation. The gap between the two lines is the calibration layer:
        the same grader reads, roughly twice the accuracy once they&rsquo;re mapped onto the
        public scale with measured noise.</p>
    </div>
    <figure>
      <div class="plate">__TRAJECTORY_SVG__</div>
      <figcaption><b>Mean absolute Elo error after each question.</b> 18 live models across
        Mistral, Meta, Google, OpenAI-OSS, Qwen, DeepSeek, Moonshot families; every estimate
        made with the evaluated model held out of all calibration fits. Grader:
        mistral-medium-3.5.</figcaption>
    </figure>
  </section>

  <section>
    <p class="eyebrow" style="max-width:700px;margin-left:auto;margin-right:auto">External validity</p>
    <div class="col" style="margin-bottom:4px">
      <h2>Four cents, plotted against the expensive indices</h2>
      <p>The estimate was calibrated on aibenchmarks Elo — Epoch&rsquo;s Capabilities Index and
        the Artificial Analysis Intelligence Index never entered the pipeline. Correlating
        against them is an out-of-sample test, with a natural ceiling: our own ground truth
        only correlates with each index so well.</p>
    </div>
    <figure>
      <div class="plate">__SCATTER_SVG__</div>
      <figcaption><b>Left:</b> against Epoch ECI the five-answer estimate reaches
        ρ&nbsp;=&nbsp;0.90 of a 0.94 ceiling — ~96% of the achievable rank agreement, at
        n&nbsp;=&nbsp;10 overlap. <b>Right:</b> against the AA index it manages
        ρ&nbsp;=&nbsp;0.57 of a 0.89 ceiling (n&nbsp;=&nbsp;14) — real but weaker; the AA
        composite leans on hard reasoning and agentic harnesses our five questions
        don&rsquo;t probe. Variant matching follows how each model was actually served
        (non-reasoning endpoints matched to non-reasoning rows).</figcaption>
    </figure>
  </section>
</div>

<div class="col">
  <section>
    <p class="eyebrow">Cost</p>
    <h2>The part that changes what&rsquo;s possible</h2>
    <table>
      <thead><tr><th>Evaluation</th><th>What runs</th><th style="text-align:right">Cost / model</th></tr></thead>
      <tbody>
        <tr><td>Full capability index (e.g. Artificial Analysis)</td>
          <td class="quiet">dozens of benchmarks × 1000s of prompts × reasoning traces</td>
          <td class="num" style="text-align:right">~$10&sup2;–$10&sup3; <span class="quiet">(published run costs)</span></td></tr>
        <tr><td>Arena-style Elo</td>
          <td class="quiet">thousands of pairwise human votes</td>
          <td class="num" style="text-align:right">weeks of votes</td></tr>
        <tr class="us"><td><b>VibeRank</b></td>
          <td class="quiet">5 answers + 5 transcript reads + 5 rubric grades</td>
          <td class="num" style="text-align:right"><span class="win">$0.039 measured</span></td></tr>
      </tbody>
    </table>
    <p class="quiet" style="font-size:14.5px">Four orders of magnitude. At this price you can
      re-evaluate every new checkpoint, every fine-tune, every quantization — daily.</p>
  </section>

  <section>
    <p class="eyebrow">Live demo</p>
    <h2>One real run, end to end</h2>
    <p>Not a mock-up — the production API evaluating <span class="mono">mistral-small-latest</span>
      blind, with the dashboard showing every answer, every grader read, and the calibrated
      estimate converging:</p>
    <div class="demo">
      <div class="c">$ python -m viberank &nbsp;&nbsp;# then press Estimate Elo</div>
      <table>
        <tr><td class="c">after Q1</td><td>read 1800 → <b>1676</b> ± 130</td></tr>
        <tr><td class="c">after Q2</td><td>read 1750 → <b>1605</b> ± 112</td></tr>
        <tr><td class="c">after Q3</td><td>read 1650 → <b>1520</b> ± 108</td></tr>
        <tr><td class="c">after Q5</td><td>read 1750 → <b>1604</b> ± 108</td></tr>
      </table>
      <div style="margin-top:10px">estimate <span class="a">1604 ± 108</span>
        &nbsp;·&nbsp; public Elo <span class="g">1549–1574</span>
        &nbsp;·&nbsp; cost <span class="a">$0.039</span> &nbsp;·&nbsp; ~1 minute</div>
    </div>
    <p class="quiet" style="margin-top:16px">The dashboard exposes the full grader context —
      reference answers, rubrics, per-answer grades, raw and corrected reads — so every
      estimate can be audited, not just believed.</p>
  </section>

  <section>
    <p class="eyebrow">Why trust the number</p>
    <h2>Honesty is the feature</h2>
    <ul class="caveats">
      <li><b>The interval is measured, not vibes about vibes.</b> The &plusmn; comes from how
        the grader actually performed on models of known Elo — and a calibration that
        can&rsquo;t prove signal refuses to produce a number at all.</li>
      <li><b>Every estimate is auditable.</b> The dashboard shows the questions, the private
        references, every answer, and every grader read behind the number — inspect it,
        don&rsquo;t just believe it.</li>
      <li><b>It gets better for pennies.</b> Accuracy and coverage come from the reference
        bank, and extending it costs about ten cents per model. Today&rsquo;s calibrated
        range is ~1200–1750; frontier coverage is the active frontier of the research —
        harder questions and a stronger reader — on the same architecture.</li>
    </ul>
  </section>

  <footer>
    <svg class="cat" width="40" height="26" viewBox="0 0 176 112" aria-hidden="true" fill="currentColor">
      <path d="M32 32h16V16h16v16h48V16h16v16h16v64H32z"/>
      <rect x="144" y="40" width="16" height="40" rx="2"/>
      <rect x="56" y="56" width="16" height="16" rx="2" fill="var(--paper)"/>
      <rect x="104" y="56" width="16" height="16" rx="2" fill="var(--paper)"/>
    </svg>
    <span>VibeRank research MVP · grader mistral-medium-3.5 · reference bank: 18 models,
      5 families · all numbers leave-one-out · July 2026</span>
  </footer>
</div>
"""

html = (
    HTML.replace("__TRAJECTORY_SVG__", trajectory_svg)
    .replace("__SCATTER_SVG__", scatter_svg)
    .replace("__GRADERS_SVG__", graders_svg)
)
OUT.write_text(html, encoding="utf-8")
print(f"Saved {OUT} ({len(html):,} chars)")
