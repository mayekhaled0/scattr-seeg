#!/usr/bin/env python
"""
filter_combine_tck.py

Replaces the shell block in filter_combine_tck rule.
For each node-pair edge:
  - Runs tckedit -exclude <mask> to remove anatomically implausible streamlines
  - Collects successfully filtered outputs
  - Combines all filtered tck files into a single tractogram
  - Concatenates all per-edge weight files into a single weights file
"""
import os
import subprocess
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snakemake.script import Snakemake
    snakemake: Snakemake


def run(cmd, **kwargs):
    """Run a shell command, return True on success."""
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"[WARN] Command failed (skipping): {' '.join(cmd)}")
        print(f"  stderr: {result.stderr.strip()}")
        return False
    return True


def main():
    tmp_dir       = Path(snakemake.resources.tmp_dir)
    tmp_combined_tck     = snakemake.resources.tmp_combined_tck
    tmp_combined_weights = snakemake.resources.tmp_combined_weights
    combined_tck         = snakemake.output.combined_tck
    combined_weights     = snakemake.output.combined_weights
    log                  = snakemake.log[0]
    threads              = snakemake.threads

    tmp_dir.mkdir(parents=True, exist_ok=True)
    Path(log).parent.mkdir(parents=True, exist_ok=True)

    # --- Gather inputs --------------------------------------------------
    filter_masks     = list(snakemake.input.filter_mask)
    weights_in       = list(snakemake.input.weights)
    tck_in           = list(snakemake.input.tck)
    filtered_weights = list(snakemake.params.filtered_weights)
    filtered_tck     = list(snakemake.params.filtered_tck)

    # --- Step 1: filter each edge pair ----------------------------------
    successful_tck     = []
    successful_weights = []

    for mask, w_in, fw_out, t_in, ft_out in zip(
        filter_masks, weights_in, filtered_weights, tck_in, filtered_tck
    ):
        Path(ft_out).parent.mkdir(parents=True, exist_ok=True)
        ok = run([
            "tckedit",
            "-exclude", mask,
            "-tck_weights_in",  w_in,
            "-tck_weights_out", fw_out,
            t_in, ft_out,
        ])
        if ok and Path(ft_out).exists() and Path(ft_out).stat().st_size > 0:
            successful_tck.append(ft_out)
            successful_weights.append(fw_out)

    print(f"[INFO] {len(successful_tck)} / {len(filter_masks)} edges produced filtered streamlines.")

    if not successful_tck:
        raise RuntimeError(
            "No edges produced filtered streamlines. "
            "Check that filter masks and input TCK files are non-empty."
        )

    # --- Step 2: combine filtered tck files (batched to avoid ARG_MAX) --
    # Write list to file and use MRtrix3 @file syntax
    tck_list_file = tmp_dir / "filtered_tck_exists.txt"
    tck_list_file.write_text("\n".join(successful_tck) + "\n")

    ok = run(["tckedit", f"@{tck_list_file}", tmp_combined_tck])

    if not ok:
        # Fallback: combine in chunks of 500
        print("[INFO] @file syntax failed, falling back to chunked combine...")
        chunk_size = 500
        chunks = [successful_tck[i:i+chunk_size]
                  for i in range(0, len(successful_tck), chunk_size)]

        tmp_chunk = str(tmp_dir / "chunk_combined.tck")
        shutil.copy(chunks[0][0], tmp_chunk)

        for chunk in chunks:
            tmp_out = str(tmp_dir / "chunk_out.tck")
            run(["tckedit", tmp_chunk] + chunk + [tmp_out])
            shutil.move(tmp_out, tmp_chunk)

        shutil.copy(tmp_chunk, tmp_combined_tck)

    # --- Step 3: concatenate per-edge weight files ----------------------
    with open(tmp_combined_weights, "w") as outf:
        for wf in successful_weights:
            p = Path(wf)
            if p.exists():
                outf.write(p.read_text())

    # --- Step 4: rsync to final output ----------------------------------
    run(["rsync", "-v", tmp_combined_tck, combined_tck])
    run(["rsync", "-v", tmp_combined_weights, combined_weights])

    # --- Step 5: clean up per-edge files --------------------------------
    for f in successful_tck + successful_weights:
        try:
            Path(f).unlink()
        except FileNotFoundError:
            pass

    print(f"[INFO] Done. Combined TCK: {combined_tck}")


if __name__ == "__main__":
    with open(snakemake.log[0], "w") as log_fh:
        import sys
        sys.stdout = log_fh
        sys.stderr = log_fh
        main()
