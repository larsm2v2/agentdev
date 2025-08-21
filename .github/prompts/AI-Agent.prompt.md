---
mode: ask
project_context: "AI Agent with Python and Modern Web Stack"
summary: "AI agent project using Python backend, Alpine.js + Tailwind frontend, CrewAI orchestration, PostgreSQL, Redis, and Grafana."

brief_function: "Describe the agent's primary function here in one sentence (e.g., 'analyze financial data and generate market reports')."

part_1_core_principles:
  language: "Python 3.10+"
  style:
    - "Follow PEP 8."
    - "Use type hints for all function arguments and return values."
  docstrings: "All functions and classes must have Google-style docstrings."
  dependencies: "Prefer well-maintained libraries (requests, sqlalchemy, pydantic, fastapi, aiohttp)."

part_2_advanced_python_focus:
  async: "Prefer asyncio, async/await. Use FastAPI or aiohttp for async HTTP services."
  decorators_metaclasses: "Use decorators for behavior modification; use metaclasses only when necessary."
  generators_iterators: "Use generators to optimize memory where appropriate."
  design_patterns: "Consider Singleton, Factory, Strategy when appropriate."
  concurrency: "Differentiate threading vs multiprocessing and recommend the best approach."

part_3_testing_tdd:
  framework: "pytest"
  mocking: "Use unittest.mock.patch for external dependencies (DB, network, CrewAI)."
  test_structure:
    - "Clear, descriptive test names."
    - "Arrange-Act-Assert pattern."
  test_coverage_expectation:
    - "Happy path"
    - "Edge cases"
    - "Error handling"

part_4_tech_stack_instructions:
  crewai: "Recommend modular agents, tasks, and crews; keep components small and testable."
  postgresql: "Use SQLAlchemy ORM; suggest Alembic for migrations."
  redis: "Assume caching or lightweight message queueing scenarios."
  frontend: "When producing HTML/JS, use Tailwind utility classes and Alpine.js directives (x-data, x-on, x-bind)."

task_definition:
  description: >
    Define the immediate task to achieve. Include explicit requirements, constraints,
    and success criteria so the assistant can produce actionable code, tests, or infra changes.
  requirements:
    - "Provide a clear, prioritized list of deliverables (code, tests, infra changes, docs)."
    - "State target runtime (local, Docker, cloud) and any CI expectations."
    - "List all existing files to modify and specify entry points."
    - "Specify whether changes must be backward compatible."
  constraints:
    - "Adhere to the coding principles in part_1 and testing rules in part_3."
    - "Prefer minimal, incremental changes; avoid large refactors unless requested."
    - "Respect repository's Docker and CI workflows."
  success_criteria:
    - "Code compiles and lints (flake8/ruff or project linter) without new warnings."
    - "Unit tests pass locally (pytest) and integration smoke tests succeed in Docker."
    - "Changes include docs or usage notes for reviewers."
---

Define the task to achieve, including specific requirements, constraints, and success criteria.
