#!/bin/bash
#SBATCH --job-name=scattr_AllContacts_P224
#SBATCH --output=batch_logs/scattr_AllContacts_P224_%j.out
#SBATCH --error=batch_logs/scattr_AllContacts_P224_%j.err
#SBATCH --mem=256G
#SBATCH --cpus-per-task=128
#SBATCH --time=48:00:00
#SBATCH --partition=hx

mkdir -p batch_logs

# Load required modules
module load apptainer

# Set experiment name and directories
EXP_NAME="scattr_AllContacts_P224" 
TMP_DIR="/tmp/${EXP_NAME}"
PERSISTENT_DIR="/nfs/khan/trainees/mkhaled5/scattr-seeg/output/${EXP_NAME}" # Change to your persistent storage location
DATASET_SRC="/nfs/khan/trainees/mkhaled5/scattr-seeg/bids"
SCATTR_SRC="/nfs/khan/trainees/mkhaled5/scattr-seeg/scattr"

#start
# Set writable container cache directories
export SINGULARITY_CACHEDIR=/nfs/khan/trainees/mkhaled5/singularity_cache
export APPTAINER_CACHEDIR=/nfs/khan/trainees/mkhaled5/singularity_cache
export SINGULARITY_TMPDIR=/tmp/${EXP_NAME}_singularity_tmp
export APPTAINER_TMPDIR=/tmp/${EXP_NAME}_apptainer_tmp

# Create needed directories
mkdir -p ${SINGULARITY_CACHEDIR}
mkdir -p ${SINGULARITY_TMPDIR}
mkdir -p ${APPTAINER_TMPDIR}
#end


# Copy SCATTR pipeline and related data to /tmp
echo "Copying experiment to ${TMP_DIR}..."
mkdir -p ${TMP_DIR}
cp -r ${SCATTR_SRC} ${TMP_DIR}
cp -r ${DATASET_SRC} ${TMP_DIR}
cd ${TMP_DIR}/scattr

# Activate virtual environment
source ${HOME}/scattr-venv/bin/activate

# Run the SCATTR pipeline
echo "Running SCATTR pipeline..."
python run.py ${TMP_DIR}/bids ${TMP_DIR}/output participant \
  --participant-label P224 \
  --force-output \
  --cores all \
  --freesurfer-dir "${TMP_DIR}/bids/derivatives/freesurfer/" \
  --keep-going \
  --rerun-incomplete \
  --fs-license "${HOME}/license.txt" \
  --use-singularity \
  --singularity-args="--bind ${HOME}/license.txt:/usr/local/freesurfer/.license,${HOME}/license.txt:/home/UWO/mkhaled5/license.txt" \
  --show-failed-logs \
  --labelmerge-base-dir "${TMP_DIR}/bids/" \
  --labelmerge-base-desc AllContacts \
  --radial-search 4 \
  --skip-labelmerge \
  --skip-brainstem \
  --profile default

# Optional: Run inference or post-processing (uncomment if needed)
# python your_inference_script.py --config your_inference_config.yaml

# Copy the entire experiment folder back to persistent storage
echo "Copying results to ${PERSISTENT_DIR}..."
cp -r ${TMP_DIR}/output/ ${PERSISTENT_DIR}/

# Clean up temporary directory
cd /tmp
rm -rf ${TMP_DIR}

echo "Experiment ${EXP_NAME} completed and cleaned up!"
