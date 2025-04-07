#!/bin/bash

# Define paths
VENV_PATH="/home/grace/Desktop/YT_scoreboard/venv"
MAIN_DIR="/home/grace/Desktop/YT_scoreboard"
SIM_DIR="${MAIN_DIR}/simulation"
LEDS_DIR="${MAIN_DIR}/leds"

# Function to open a terminal in a specific directory with the venv activated
open_terminal() {
    local directory=$1
    local title=$2

    # Set the PYTHONPATH to the specific directory for this terminal
    local python_path="${directory}"

    if command -v lxterminal &> /dev/null; then
        lxterminal --title="${title}" --working-directory="${directory}" \
          -e "bash -c \"cd ${directory} && source ${VENV_PATH}/bin/activate && export PYTHONPATH='${python_path}:\$PYTHONPATH' && echo 'Virtual environment activated in ${title} with PYTHONPATH=${python_path}. Press Ctrl+C to exit.' && exec bash\""
    elif command -v xfce4-terminal &> /dev/null; then
        xfce4-terminal --title="${title}" --working-directory="${directory}" \
          -e "bash -c \"cd ${directory} && source ${VENV_PATH}/bin/activate && export PYTHONPATH='${python_path}:\$PYTHONPATH' && echo 'Virtual environment activated in ${title} with PYTHONPATH=${python_path}. Press Ctrl+C to exit.' && exec bash\"" --hold
    elif command -v mate-terminal &> /dev/null; then
        mate-terminal --title="${title}" --working-directory="${directory}" \
          -e "bash -c \"cd ${directory} && source ${VENV_PATH}/bin/activate && export PYTHONPATH='${python_path}:\$PYTHONPATH' && echo 'Virtual environment activated in ${title} with PYTHONPATH=${python_path}. Press Ctrl+C to exit.' && exec bash\""
    elif command -v gnome-terminal &> /dev/null; then
        gnome-terminal --title="${title}" --working-directory="${directory}" \
          -- bash -c "cd ${directory} && source ${VENV_PATH}/bin/activate && export PYTHONPATH='${python_path}:\$PYTHONPATH' && echo 'Virtual environment activated in ${title} with PYTHONPATH=${python_path}. Press Ctrl+C to exit.' && exec bash"
    elif command -v xterm &> /dev/null; then
        xterm -title "${title}" -e "cd ${directory} && source ${VENV_PATH}/bin/activate && export PYTHONPATH='${python_path}:\$PYTHONPATH' && echo 'Virtual environment activated in ${title} with PYTHONPATH=${python_path}. Press Ctrl+C to exit.' && exec bash"
    else
        echo "No supported terminal emulator found."
        return 1
    fi

    sleep 1
}
# Open three terminals in the specified directories
echo "Opening terminals..."
open_terminal "${MAIN_DIR}" "Main Directory"
open_terminal "${SIM_DIR}" "Simulation Directory"
open_terminal "${LEDS_DIR}" "LEDs Directory"

echo "All terminals opened!"