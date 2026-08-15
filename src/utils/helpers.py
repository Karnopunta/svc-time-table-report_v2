"""
Utility functions and helpers for the application.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import platform
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional

import keyring as kr
from keyrings.cryptfile.cryptfile import CryptFileKeyring

def setup_keyring(keyring_key: str = "9unn5"):
    """
    Sets up the keyring based on the operating system.

    Args:
        keyring_key (str): The keyring encryption key for non-MacOS systems.
    """
    if platform.system() != "Darwin":  # Darwin is MacOS
        keyring_backend = CryptFileKeyring()
        keyring_backend.keyring_key = keyring_key
        kr.set_keyring(keyring_backend)
    return kr

def setup_logging(config: Dict[str, Any], script_dir: str) -> None:
    """Configure root logging for the application."""
    # Always clear existing handlers to prevent duplicate logs.
    logger = logging.getLogger()
    if logger.hasHandlers():
        logger.handlers.clear()
    log_dir = os.path.dirname(
        os.path.join(script_dir, config.get("LOG_FILE_PATH", "logs/app.log"))
    )
    os.makedirs(log_dir, exist_ok=True)
    log_level_name = str(config.get("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_style = str(config.get("LOG_STYLE", "readable")).strip().lower()

    if log_style == "compact":
        log_format = "%(asctime)s | %(levelname).1s | %(message)s"
    elif log_style == "verbose":
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    else:
        # Default readable format: short time, short level, logger name, message.
        log_format = "%(asctime)s | %(levelname).1s | %(name)s | %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%H:%M:%S",
        handlers=[
            RotatingFileHandler(
                os.path.join(script_dir, config.get("LOG_FILE_PATH", "logs/app.log")),
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
            ),
            logging.StreamHandler(sys.stdout)
        ],
    )
    logging.info(
        "Setup logging initialized | level=%s | style=%s",
        log_level_name,
        log_style,
    )

# def setup_logging(config, script_dir):
#     import sys

#     log_dir = os.path.dirname(os.path.join(script_dir, config.get('LOG_FILE_PATH', 'logs/app.log')))
#     if log_dir and not os.path.exists(log_dir):
#         os.makedirs(log_dir)

#     log_level = getattr(logging, config.get('LOG_LEVEL', 'DEBUG').upper())

#     # Configure named logger
#     logger = logging.getLogger("PythonBoilerplate")
#     logger.setLevel(log_level)
#     logger.propagate = False  # Prevent double logging

#     # Remove all handlers
#     for handler in logger.handlers[:]:
#         logger.removeHandler(handler)

#     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

#     console_handler = logging.StreamHandler(sys.stdout)
#     console_handler.setLevel(log_level)
#     console_handler.setFormatter(formatter)
#     logger.addHandler(console_handler)

#     file_handler = RotatingFileHandler(
#         os.path.join(script_dir, config.get('LOG_FILE_PATH', 'logs/app.log')),
#         maxBytes=1024*1024*10,
#         backupCount=5
#     )
#     file_handler.setLevel(log_level)
#     file_handler.setFormatter(formatter)
#     logger.addHandler(file_handler)

#     return logger

def example_utility_function(text: str) -> str:
    """
    Example utility function that processes text.
    
    Args:
        text (str): Text to process.
        
    Returns:
        str: Processed text.
    """
    return text.strip().upper()    

def calculate_percentage(part: float, whole: float) -> float:
    """
    Calculate percentage.

    Args:
        part (float): Part value.
        whole (float): Whole value.

    Returns:
        float: Percentage value.
    """
    logging.info("Calculating percentage: %s of %s", part, whole)
    if whole == 0:
        return 0
    return (part / whole) * 100


def read_json_file(file_path: str) -> Dict[str, Any]:
    """
    Read a JSON file and return its contents as a dictionary.
    
    Args:
        file_path (str): Path to the JSON file.
        
    Returns:
        Dict[str, Any]: Contents of the JSON file.
        
    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def write_json_file(file_path: str, data: Dict[str, Any]) -> None:
    """
    Write data to a JSON file.
    
    Args:
        file_path (str): Path to the JSON file.
        data (Dict[str, Any]): Data to write to the file.
    """
    # Create directory if it doesn't exist.
    dir_name = os.path.dirname(file_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

def read_csv_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Read a CSV file and return its contents as a list of dictionaries.
    
    Args:
        file_path (str): Path to the CSV file.
        
    Returns:
        List[Dict[str, Any]]: Contents of the CSV file.
        
    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        return list(reader)

def write_csv_file(file_path: str, data: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    """
    Write data to a CSV file.
    
    Args:
        file_path (str): Path to the CSV file.
        data (List[Dict[str, Any]]): Data to write to the file.
        fieldnames (Optional[List[str]]): List of field names. If None, will use keys from first row.
    """
    if not data:
        return
    
    # Create directory if it doesn't exist.
    dir_name = os.path.dirname(file_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    
    # Determine fieldnames if not provided
    if fieldnames is None:
        fieldnames = list(data[0].keys())
    
    with open(file_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

def format_timestamp(
    timestamp: Optional[datetime] = None,
    format_str: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """
    Format a timestamp as a string.
    
    Args:
        timestamp (Optional[datetime]): Timestamp to format. If None, uses current time.
        format_str (str): Format string for the timestamp.
        
    Returns:
        str: Formatted timestamp string.
    """
    if timestamp is None:
        timestamp = datetime.now()
    return timestamp.strftime(format_str)

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning a default value if denominator is zero.
    
    Args:
        numerator (float): Numerator.
        denominator (float): Denominator.
        default (float): Default value to return if denominator is zero.
        
    Returns:
        float: Result of division or default value.
    """
    if denominator == 0:
        return default
    return numerator / denominator

def flatten_dict(
    d: Dict[str, Any],
    parent_key: str = "",
    sep: str = "_",
) -> Dict[str, Any]:
    """
    Flatten a nested dictionary.
    
    Args:
        d (Dict[str, Any]): Dictionary to flatten.
        parent_key (str): Parent key for recursion.
        sep (str): Separator for nested keys.
        
    Returns:
        Dict[str, Any]: Flattened dictionary.
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def get_environment_variable(
    var_name: str,
    default: Any = None,
    required: bool = False,
) -> str:
    """
    Get an environment variable with optional default value and requirement check.
    
    Args:
        var_name (str): Name of the environment variable.
        default (Any): Default value if variable is not set.
        required (bool): Whether the variable is required.
        
    Returns:
        str: Value of the environment variable.
        
    Raises:
        ValueError: If required variable is not set and no default provided.
    """
    value = os.getenv(var_name, default)
    if required and value is None:
        raise ValueError(f"Required environment variable '{var_name}' is not set")
    return value
