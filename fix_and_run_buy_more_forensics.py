from pathlib import Path
import subprocess
import sys

target = Path("tests/buy_more_signal_score_forensics.py")

if not target.exists():
    raise SystemExit(f"ERROR: {target} not found")

text = target.read_text()

old_signature = """def reconstruct_lineage(
    decisions,
    recommendations,
):"""

new_signature = """def reconstruct_lineage(
    decisions,
    recommendations,
    evaluations,
):"""

old_call = """frame = reconstruct_lineage(
            decisions,
            recommendations,
        )"""

new_call = """frame = reconstruct_lineage(
            decisions,
            recommendations,
            evaluations,
        )"""

if old_signature not in text:
    if new_signature not in text:
        raise SystemExit(
            "ERROR: Expected reconstruct_lineage signature not found. "
            "No changes made."
        )
    signature_changed = False
else:
    text = text.replace(
        old_signature,
        new_signature,
        1,
    )
    signature_changed = True

if old_call not in text:
    if new_call not in text:
        raise SystemExit(
            "ERROR: Expected reconstruct_lineage call not found. "
            "No changes made."
        )
    call_changed = False
else:
    text = text.replace(
        old_call,
        new_call,
        1,
    )
    call_changed = True

target.write_text(text)

print(
    f"Updated {target} "
    f"(signature={signature_changed}, call={call_changed})"
)
print()
print("Running forensic analysis...")
print("=" * 76)

result = subprocess.run(
    [
        sys.executable,
        str(target),
    ],
    text=True,
)

raise SystemExit(result.returncode)
