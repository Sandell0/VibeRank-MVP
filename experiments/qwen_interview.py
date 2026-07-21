"""Self-steered interviews with qwen3.7-max as interviewer AND grader.

Head-to-head against the Terra-interviewer run (overall MAE 93, rho 0.84;
frontier MAE 97). Separate data files; nothing overwritten.

    python -m experiments.qwen_interview
"""
import experiments.self_steered_interview as ssi

ssi.INTERVIEWER = "qwen/qwen3.7-max"
ssi.GRADER_MODEL = "qwen/qwen3.7-max"
ssi.DATA_PATH = ssi.EXP / "qwen_interview_data.json"
ssi.RESULTS_PATH = ssi.EXP / "qwen_interview_results.json"

if __name__ == "__main__":
    ssi.main()
