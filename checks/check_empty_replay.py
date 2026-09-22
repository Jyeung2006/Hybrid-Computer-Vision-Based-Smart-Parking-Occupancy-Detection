"""Compatibility command: validate the current method-confirmed decision policy."""
from check_decisions import main


if __name__ == "__main__":
    print("Empty-image final overrides are retired. Running the current decision check.", flush=True)
    main()
