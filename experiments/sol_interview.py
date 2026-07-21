"""Self-steered interviews with gpt-5.6-sol as interviewer, medium as grader
(same grader as the Terra run, so the interviewer comparison is clean).

Baseline to beat: Terra interviewer — overall MAE 93 / rho 0.84, frontier
MAE 97 / rho 0.29.

    python -m experiments.sol_interview
"""
import experiments.self_steered_interview as ssi

ssi.INTERVIEWER = "openai/gpt-5.6-sol"
ssi.GRADER_MODEL = None  # mistral-medium, matching the Terra run
ssi.DATA_PATH = ssi.EXP / "sol_interview_data.json"
ssi.RESULTS_PATH = ssi.EXP / "sol_interview_results.json"

if __name__ == "__main__":
    ssi.main()
