"""
Configuration management module.
Loads different configurations based on the environment.

# Now you can import CONFIG from settings.py anywhere
from config.settings import CONFIG
"""
import os
import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


CONFIG = None  # Global variable

def set_config(config_dict):
    global CONFIG
    CONFIG = config_dict

def load_config(script_dir):
    """
    Load configuration based on the current environment.
    
    Returns:
        dict: Configuration dictionary for the current environment.
    """
    environment = os.getenv('ENVIRONMENT', 'dev')
    YAML_FILE_NAME = os.getenv('YAML_FILE_NAME', 'local')
    
    print(f"Loading configuration for environment: {environment} (Developer: {YAML_FILE_NAME})")
    
    # Determine the config file path based on environment
    if environment == 'prod':
        config_file = 'config/config/prod.yaml'
    else:
        # Ensure filename has a yaml extension
        if not YAML_FILE_NAME.endswith('.yaml') and not YAML_FILE_NAME.endswith('.yml'):
            YAML_FILE_NAME = f"{YAML_FILE_NAME}.yaml"
        config_file = os.path.join(script_dir, 'config', 'config', YAML_FILE_NAME)
        # if environment.startswith('dev_'):
        #     config_file = os.path.join(script_dir, f'config/config/{YAML_FILE_NAME}')
        # else:
        #     config_file = os.path.join(script_dir, 'config/config/local.yaml')
    
    # Load YAML configuration
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, 'r') as f:
        CONFIG = yaml.safe_load(f)
    
    # Add environment variables to config (they take precedence)
    CONFIG['ENVIRONMENT'] = environment
    CONFIG['YAML_FILE_NAME'] = YAML_FILE_NAME
    CONFIG['LOG_LEVEL'] = os.getenv('LOG_LEVEL', CONFIG.get('LOG_LEVEL', 'DEBUG'))
    CONFIG['LOG_FILE_PATH'] = os.getenv('LOG_FILE_PATH', CONFIG.get('LOG_FILE_PATH', 'logs/app.log'))
    CONFIG['LOG_STYLE'] = os.getenv('LOG_STYLE', CONFIG.get('LOG_STYLE', 'readable'))
    CONFIG['APP_NAME'] = os.getenv('APP_NAME', CONFIG.get('APP_NAME', 'Python Boilerplate'))
    CONFIG['APP_VERSION'] = os.getenv('APP_VERSION', CONFIG.get('APP_VERSION', '1.0.0'))
    # Add DB config from environment
    CONFIG['DB_HOST'] = os.getenv('DB_HOST', CONFIG.get('DB_HOST', '127.0.0.1'))
    CONFIG['DB_PORT'] = int(os.getenv('DB_PORT', CONFIG.get('DB_PORT', 5432)))
    CONFIG['DB_NAME'] = os.getenv('DB_NAME', CONFIG.get('DB_NAME', 'your_db'))
    CONFIG['DB_USER'] = os.getenv('DB_USER', CONFIG.get('DB_USER', 'your_user'))
    CONFIG['DB_PASSWORD'] = os.getenv('DB_PASSWORD', CONFIG.get('DB_PASSWORD', 'your_password'))

    return CONFIG

# Export global config variable


