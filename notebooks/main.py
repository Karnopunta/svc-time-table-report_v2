#!/usr/bin/env python
# coding: utf-8

# # Develop Main in Jupyter
# 
# This notebook is for initial data exploration and experimentation. Code developed here should be migrated to .py files in the src/ directory for production use.
# 
# Environment Name : boilerplate

# In[1]:


# Import necessary libraries
import logging
logging.getLogger().handlers.clear()


# In[2]:


import sys
import os
import argparse
from datetime import datetime, timedelta

# Add project root directory to path for importing our modules
# This assumes the notebook is in the notebooks/ directory at the project root
project_root = os.path.abspath(os.path.join(os.getcwd(), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Check if running in a Jupyter Notebook
if 'get_ipython' in globals():
    # Running in Jupyter Notebook
    script_dir = os.path.abspath(os.path.join(os.getcwd(), '..'))
    # print("Running in Jupyter Notebook")
else:
    # Running in a standard Python script
    script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from src.utils.helpers import example_utility_function

import keyring as kr
from keyrings.cryptfile.cryptfile import CryptFileKeyring

from config.settings import load_config
from src.utils.helpers import setup_logging, setup_keyring

from config.settings import load_config, set_config
from src.utils.helpers import setup_logging, setup_keyring

## Global Variables
# Load configuration based on environment
config = load_config(script_dir)
set_config(config)
# Set up logging
setup_logging(config,script_dir)
kr = setup_keyring()


# In[3]:


# START COPY FROM HERE

## New Libraries goes here
from src.db.connection import conn
from src.utils.helpers import calculate_percentage
from src.db import repository as repo
from src.utils.backoff import next_retry_at
from src.utils.timeutils import now_tz
import uuid
import time



# In[4]:


from src.jobs.sample_push_orders import SamplePushOrdersProcessor

def main():
    """Main application function."""
    # ...existing argument parsing and config setup...
    job_code = 'SAMPLE_PUSH_ORDERS'
    processor = SamplePushOrdersProcessor(job_code, repo, config, logging)
    processor.process()
    processor.finish()

if __name__ == "__main__":
    main()


# In[ ]:
