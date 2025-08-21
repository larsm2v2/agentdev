// Component Loader - Loads HTML components into containers
class ComponentLoader {
  constructor() {
    // Force development mode
    this.basePath = "/static/components/";
    this.components = {
      "status-notifications-container": "status-notifications.html",
      "header-container": "header.html",
      "function-cards-container": "function-cards.html",
      "statistics-container": "statistics.html",
      "tab-content-container": "tab-container.html",
      "shelving-tab-container": "../tabs/shelving-tab.html",
      "cataloging-tab-container": "../tabs/cataloging-tab.html",
      "reclassification-tab-container": "../tabs/reclassification-tab.html",
      "workflows-tab-container": "../tabs/workflows-tab.html",
    };
  }

  async loadComponent(containerId, componentPath) {
    try {
      console.log(`📦 Loading component: ${componentPath} → #${containerId}`);
      const response = await fetch(this.basePath + componentPath);
      if (!response.ok) {
        throw new Error(
          `Failed to load component: ${componentPath} (${response.status})`
        );
      }
      const html = await response.text();
      const container = document.getElementById(containerId);
      if (container) {
        container.innerHTML = html;
        console.log(`✅ Loaded component: ${containerId}`);
      } else {
        console.warn(`⚠️ Container not found: ${containerId}`);
      }
    } catch (error) {
      console.error(`❌ Error loading component ${componentPath}:`, error);
    }
  }

  async loadAllComponents() {
    const loadPromises = Object.entries(this.components).map(
      ([containerId, componentPath]) =>
        this.loadComponent(containerId, componentPath)
    );

    try {
      await Promise.all(loadPromises);
      console.log("All components loaded successfully");
    } catch (error) {
      console.error("Error loading components:", error);
    }
  }
}

// Auto-load components when DOM is ready
document.addEventListener("DOMContentLoaded", async () => {
  console.log("🔄 Starting component loading...");
  const loader = new ComponentLoader();
  await loader.loadAllComponents();
});

// Also try loading after Alpine.js is available
document.addEventListener("alpine:init", async () => {
  console.log("🔄 Alpine.js initialized, loading components...");
  const loader = new ComponentLoader();
  await loader.loadAllComponents();
});

// Export for potential future use
window.ComponentLoader = ComponentLoader;
