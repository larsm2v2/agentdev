# 🚀 Copilot Prompt Playbook

## 🔹 General Prompts

- **Explain code**

  ````plaintext

  /explain
  Explain what this function does step by step. You are an expert at drilling down i.e. searching documents to find the next document to interrogate. You search until you find the end or the root cause of an issue.
  ```plaintext

  ````

- **Refactor code**

  ````plaintext
  Refactor this into smaller functions with clearer names.
  ```plaintext

  ````

- **Optimize performance**

  ````plaintext
  Rewrite this to reduce memory usage and minimize async blocking.
  ```plaintext

  ````

- **Add documentation**

  ````plaintext
  /docs
  Generate JSDoc/Docstrings for this function.
  ```plaintext
  ````

---

### 🔹 React Prompts

- **Component generation**

  ````plaintext
  Create a React functional component with props {title, items[]}.
  Render items in a responsive grid with Tailwind.
  ```plaintext
  ````

- **State management**

  ````plaintext
  Rewrite this component to use React Query for data fetching with caching.
  ```plaintext
  ````

- **Accessibility**

  ````plaintext
  Improve this form component with ARIA labels and keyboard navigation support.
  ```plaintext
  ````

- **Testing (Jest/RTL)**

  ````plaintext
  /tests
  Generate unit tests for this component with React Testing Library.
  ```plaintext
  ````

---

### 🔹 Node.js / Express Prompts

- **API endpoint**

  ````plaintext
  Create an Express route `/users/:id` that fetches a user from PostgreSQL using async/await.
  ```plaintext
  ````

- **Middleware**

  ````plaintext
  Write Express middleware that logs method, path, and response time.
  ```plaintext
  ````

- **Error handling**

  ````plaintext

  Refactor this API to return proper HTTP status codes and JSON error messages.
  ```plaintext
  ````

- **Testing (Jest/Supertest)**

  ````plaintext
  /tests
  Generate integration tests for these Express routes using Supertest.
  ```plaintext
  ````

---

### 🔹 Python Prompts

- **Data processing**

  ````plaintext
  Write a Python function that reads a CSV of transactions and returns total sales by day.
  ```plaintext
  ````

- **OOP / Patterns**

  ````plaintext
  Refactor this code to use the Strategy pattern.
  ```plaintext
  ````

- **FastAPI**

  ````plaintext
  Create a FastAPI route that accepts JSON {id:int, name:str}, validates it with Pydantic, and returns a response.
  ```plaintext
  ````

- **Unit testing (pytest)**

  ````plaintext
  /tests
  Write pytest unit tests for this function, including edge cases.
  ```plaintext
  ````

- **Handle Actualities**

  ````plaintext
  /tests
  Be clear. Find the answer instead of suggesting a possibility when asked about accessible code.
  ```plaintext
  ````

---

### 🔹 Advanced Prompting

- **Role-based**

  ````plaintext
  Act as a security auditor. Review this function for vulnerabilities.
  ```plaintext
  ````

- **Step-by-step**

  ````plaintext
  Generate a plan: How would you build an image upload API in Node.js with validation, storage, and authentication?
  ```plaintext

  ````

- **Regex helper**

  ````plaintext
  Create a regex that validates US phone numbers. Explain the parts.
  ```plaintext
  ````

---

### 🔹 Workflow Tips

- Use **inline comments as prompts** → Copilot reads them.
- Use `/fix`, `/tests`, `/docs` commands for quick wins.
- Ask Copilot to **“show 3 alternative implementations”** to compare.
- Keep your **folder open in VS Code** → Copilot leverages project context.
