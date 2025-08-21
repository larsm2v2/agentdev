// Component Loader Script
document.addEventListener("DOMContentLoaded", () => {
  console.log("Component Loader Script initialized");

  // Function to load HTML components with container existence check
  async function loadComponent(elementId, componentPath) {
    const container = document.getElementById(elementId);

    if (!container) {
      console.error(`Container not found: ${elementId}`);
      return;
    }

    try {
      console.log(`Loading component into ${elementId} from ${componentPath}`);
      const response = await fetch(componentPath);
      if (!response.ok) {
        throw new Error(
          `Failed to load component: ${componentPath} (${response.status})`
        );
      }
      const html = await response.text();
      container.innerHTML = html;
      console.log(`Component loaded successfully: ${componentPath}`);
    } catch (error) {
      console.error(
        `Error loading component ${componentPath}: ${error.message}`
      );
      container.innerHTML = `
        <div class="p-4 text-red-500">
          <p>Error loading component: ${error.message}</p>
        </div>
      `;
    }
  }

  // Wait a brief moment to ensure containers are properly initialized
  setTimeout(() => {
    // Load all components
    loadComponent("shelving-tab-container", "/static/tabs/shelving-tab.html");
    loadComponent(
      "cataloging-tab-container",
      "/static/tabs/cataloging-tab.html"
    );
    loadComponent(
      "reclassification-tab-container",
      "/static/tabs/reclassification-tab.html"
    );
    loadComponent("workflows-tab-container", "/static/tabs/workflows-tab.html");
  }, 100);
});
