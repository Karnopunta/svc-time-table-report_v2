Boiler Plate

I want to create a Python boilerplate for my developers to use when starting a new project.

The boilerplate should include:
- A well-structured project folder following Python best practices
- A tests/ directory with an example test case using pytest or unittest
- A lib/ or src/ folder for custom reusable code
- A logging setup that follows best practices (e.g., logs to file and console, different levels per environment)

The project should support two environments:
- Production
- Local Development

The configuration should allow different input/output sources and behavior depending on the environment (e.g., different file paths or logging levels). Environment switching should be managed using .env or OS environment variables.

We usually start development in Jupyter Notebooks for exploration, then migrate the final logic into .py files for deployment. Please include guidance or structure to support this workflow.

Lastly, I’d like advice on how to implement a centralized shared library (e.g., company_utils) that can be used across multiple applications in our ecosystem. Suggest the best approach to organize, version, and import this library in each project.
