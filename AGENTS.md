# AGENTS Instructions

This repository hosts a React frontend and a FastAPI backend.

## Style
- Format Python code using `black` before committing:
  ```bash
  black backend/app
  ```
- Format JavaScript code with Prettier:
  ```bash
  npx prettier -w frontend/src
  ```

## Testing
- If you change backend code, run:
  ```bash
  pytest
  ```
- If you change frontend code, run:
  ```bash
  npm test -- --watchAll=false
  ```

## Development
- You can spin up the full stack with Docker:
  ```bash
  docker-compose up
  ```
