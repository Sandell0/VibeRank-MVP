"""Claude Fable 5.1 through the 80-item domain bank (tokens-to-solve),
same protocol as distilled_efficiency.py, accumulating into its data file.

    python -m experiments.fable51_bank
"""
import experiments.distilled_efficiency as de

M51 = "anthropic/claude-fable-5.1"
de.MODELS = ((M51, 0, (10.0, 50.0)),)
de.PRICE[M51] = (10.0, 50.0)
de.COST_CEILING_USD = 30.0

if __name__ == "__main__":
    de.main()
