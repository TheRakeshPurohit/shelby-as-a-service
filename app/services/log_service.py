import os
import logging
import traceback

class Logger:
    def __init__(self, deployment_name, logger_name, log_file, level='INFO'):
        log_dir = f"app/deployments/{deployment_name}/logs"
        os.makedirs(log_dir, exist_ok=True)

        self.logger = logging.getLogger(logger_name)
        formatter = logging.Formatter('%(levelname)s: %(asctime)s %(message)s', datefmt='%Y/%m/%d %I:%M:%S %p')
        
        # If the logger has handlers, remove them
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
            
        # Overwrites logs
        fileHandler = logging.FileHandler(os.path.join(log_dir, log_file), mode='w')
        # Appends logs
        # fileHandler = logging.FileHandler(os.path.join(log_dir, log_file), mode='a')

        logging_level = logging._nameToLevel.get(level.upper(), logging.INFO)
        fileHandler.setFormatter(formatter)
        fileHandler.setLevel(logging_level)
        self.logger.setLevel(logging_level)
        self.logger.addHandler(fileHandler)
        self.logger.propagate = False

    def print_and_log(self, message):
        print(message)
        self.logger.info(message)
        for handler in self.logger.handlers:
            handler.flush()