import os
import logging

def setup_logger(logger_name, log_file, level=logging.INFO):
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(os.path.dirname(log_dir), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_setup = logging.getLogger(logger_name)
    formatter = logging.Formatter('%(levelname)s: %(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    # Overwrites logs
    fileHandler = logging.FileHandler(os.path.join(log_dir, log_file), mode='w')
    # Appends logs
    # fileHandler = logging.FileHandler(os.path.join(log_dir, log_file), mode='a')

    fileHandler.setFormatter(formatter)

    log_setup.setLevel(level)
    log_setup.addHandler(fileHandler)

    return log_setup

