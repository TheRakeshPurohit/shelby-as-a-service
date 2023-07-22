#!/bin/bash
# start_up.sh

# Start scripts in background
python app/run.py --deployment test personal discord &
python app/run.py --deployment test tatum slack &


# Wait for all background processes to finish
wait
