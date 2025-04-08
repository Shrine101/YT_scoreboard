#!/bin/bash

# Define paths
VENV_PATH="/home/grace/Desktop/YT_scoreboard/venv"
MAIN_DIR="/home/grace/Desktop/YT_scoreboard"
SIM_DIR="${MAIN_DIR}/real_life"
LEDS_DIR="${MAIN_DIR}/leds"

# Define which file to run in each directory
MAIN_SCRIPT="main.py"
SIM_SCRIPT="cv_writer.py"
LEDS_SCRIPT="LED_controller.py"  # needs to be run with sudo

# Function to open a terminal, activate virtualenv, set PYTHONPATH, and run one Python file
open_terminal() {
    local directory=$1
    local title=$2
    local script=$3
    local python_path="${directory}"

    # Decide if sudo is needed
    local command_to_run=""
    if [[ "${script}" == "LED_controller.py" && "${directory}" == "${LEDS_DIR}" ]]; then
        command_to_run="sudo ../venv/bin/python3 \"${script}\""
    else
        command_to_run="python \"${script}\""
    fi

    # Full shell command
    local full_command="cd ${directory} && \
source ${VENV_PATH}/bin/activate && \
export PYTHONPATH='${python_path}:\$PYTHONPATH' && \
echo 'Running ${script} in ${title} with PYTHONPATH=${python_path}' && \
${command_to_run} && \
exec bash"

    # Try launching with available terminal
    if command -v lxterminal &> /dev/null; then
        lxterminal --title="${title}" --working-directory="${directory}" \
          -e "bash -c \"${full_command}\""
    elif command -v xfce4-terminal &> /dev/null; then
        xfce4-terminal --title="${title}" --working-directory="${directory}" \
          -e "bash -c \"${full_command}\"" --hold
    elif command -v mate-terminal &> /dev/null; then
        mate-terminal --title="${title}" --working-directory="${directory}" \
          -e "bash -c \"${full_command}\""
    elif command -v gnome-terminal &> /dev/null; then
        gnome-terminal --title="${title}" --working-directory="${directory}" \
          -- bash -c "${full_command}"
    elif command -v xterm &> /dev/null; then
        xterm -title "${title}" -e "bash -c \"${full_command}\""
    else
        echo "No supported terminal emulator found."
        return 1
    fi

    sleep 1
}

# Launch the terminals
echo "Opening terminals..."
open_terminal "${MAIN_DIR}" "Main Directory" "${MAIN_SCRIPT}"
open_terminal "${SIM_DIR}" "Real Life Directory" "${SIM_SCRIPT}"
open_terminal "${LEDS_DIR}" "LEDs Directory" "${LEDS_SCRIPT}"
echo "All terminals opened!"
