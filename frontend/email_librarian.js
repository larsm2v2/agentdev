/**
 * Email Librarian - Advanced Frontend Controller
 * Handles API communication and advanced state management
 */

class EmailLibrarianController {
  constructor() {
    this.apiBase = "/api";
    this.websocket = null;
    this.functions = {
      shelving: { name: "Shelving", endpoint: "/shelving", status: "inactive" },
      cataloging: {
        name: "Cataloging",
        endpoint: "/cataloging",
        status: "inactive",
      },
      reclassification: {
        name: "Reclassification",
        endpoint: "/reclassification",
        status: "inactive",
      },
    };
    this.eventListeners = {};
  }

  // Initialize the controller
  async init() {
    try {
      await this.connectWebSocket();
      await this.loadInitialData();
      this.startHeartbeat();
      console.log("📚 Email Librarian Controller initialized");
    } catch (error) {
      console.error(
        "❌ Failed to initialize Email Librarian Controller:",
        error
      );
    }
  }

  // WebSocket connection for real-time updates
  async connectWebSocket() {
    const wsProtocol =
      window.location.protocol === "https:" ? "wss://" : "ws://";
    const wsUrl = `${wsProtocol}${window.location.host}/ws/librarian`;

    this.websocket = new WebSocket(wsUrl);

    this.websocket.onopen = () => {
      console.log("🔌 WebSocket connected");
      this.emit("websocket:connected");
    };

    this.websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleWebSocketMessage(data);
    };

    this.websocket.onclose = () => {
      console.log("🔌 WebSocket disconnected, attempting to reconnect...");
      setTimeout(() => this.connectWebSocket(), 5000);
    };
  }

  // Handle incoming WebSocket messages
  handleWebSocketMessage(data) {
    switch (data.type) {
      case "function_status":
        this.functions[data.function].status = data.status;
        this.emit("function:status_changed", {
          function: data.function,
          status: data.status,
        });
        break;
      case "processing_update":
        this.emit("processing:update", data);
        break;
      case "stats_update":
        this.emit("stats:update", data.stats);
        break;
      case "error":
        this.emit("error", data.error);
        break;
    }
  }

  // API Methods for Function Management
  async toggleFunction(functionName, enabled) {
    try {
      const response = await fetch(
        `${this.apiBase}${this.functions[functionName].endpoint}/toggle`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        }
      );

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const result = await response.json();
      this.emit("function:toggled", {
        function: functionName,
        enabled,
        result,
      });
      return result;
    } catch (error) {
      console.error(`❌ Failed to toggle ${functionName}:`, error);
      this.emit("error", `Failed to toggle ${functionName}: ${error.message}`);
      throw error;
    }
  }

  // Shelving Methods
  async configureShelving(config) {
    try {
      const response = await fetch(`${this.apiBase}/shelving/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to configure shelving:", error);
      throw error;
    }
  }

  async getShelvingStats() {
    try {
      const response = await fetch(`${this.apiBase}/shelving/stats`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to get shelving stats:", error);
      throw error;
    }
  }

  // Cataloging Methods
  async startCataloging(config) {
    try {
      const response = await fetch(`${this.apiBase}/cataloging/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to start cataloging:", error);
      throw error;
    }
  }

  async getCatalogingProgress() {
    try {
      const response = await fetch(`${this.apiBase}/cataloging/progress`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to get cataloging progress:", error);
      throw error;
    }
  }

  async pauseCataloging() {
    try {
      const response = await fetch(`${this.apiBase}/cataloging/pause`, {
        method: "POST",
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to pause cataloging:", error);
      throw error;
    }
  }

  // Reclassification Methods
  async getAvailableLabels() {
    try {
      const response = await fetch(`${this.apiBase}/reclassification/labels`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to get available labels:", error);
      throw error;
    }
  }

  async startReclassification(config) {
    try {
      const response = await fetch(`${this.apiBase}/reclassification/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to start reclassification:", error);
      throw error;
    }
  }

  async getReclassificationResults(limit = 10) {
    try {
      const response = await fetch(
        `${this.apiBase}/reclassification/results?limit=${limit}`
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to get reclassification results:", error);
      throw error;
    }
  }

  // General Data Methods
  async loadInitialData() {
    try {
      const [stats, labels] = await Promise.all([
        this.getOverallStats(),
        this.getAvailableLabels(),
      ]);

      this.emit("data:loaded", { stats, labels });
      return { stats, labels };
    } catch (error) {
      console.error("❌ Failed to load initial data:", error);
      throw error;
    }
  }

  async getOverallStats() {
    try {
      const response = await fetch(`${this.apiBase}/stats/overall`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to get overall stats:", error);
      throw error;
    }
  }

  async getCategories() {
    try {
      const response = await fetch(`${this.apiBase}/categories`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to get categories:", error);
      throw error;
    }
  }

  // Event System
  on(event, callback) {
    if (!this.eventListeners[event]) {
      this.eventListeners[event] = [];
    }
    this.eventListeners[event].push(callback);
  }

  off(event, callback) {
    if (this.eventListeners[event]) {
      this.eventListeners[event] = this.eventListeners[event].filter(
        (cb) => cb !== callback
      );
    }
  }

  emit(event, data) {
    if (this.eventListeners[event]) {
      this.eventListeners[event].forEach((callback) => callback(data));
    }
  }

  // Utility Methods
  startHeartbeat() {
    setInterval(async () => {
      try {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
          this.websocket.send(JSON.stringify({ type: "ping" }));
        }
      } catch (error) {
        console.error("❌ Heartbeat failed:", error);
      }
    }, 30000); // 30 seconds
  }

  formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return "Just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)} minutes ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`;
    return date.toLocaleDateString();
  }

  formatEmailCount(count) {
    if (count < 1000) return count.toString();
    if (count < 1000000) return `${(count / 1000).toFixed(1)}K`;
    return `${(count / 1000000).toFixed(1)}M`;
  }

  calculateProcessingSpeed(processed, timeInMs) {
    const timeInMinutes = timeInMs / 60000;
    return timeInMinutes > 0 ? Math.round(processed / timeInMinutes) : 0;
  }

  // Error handling
  handleError(error, context = "") {
    console.error(`❌ Error in ${context}:`, error);
    this.emit("error", { error: error.message, context });

    // Show user-friendly error notification
    this.showNotification(`Error: ${error.message}`, "error");
  }

  showNotification(message, type = "info") {
    this.emit("notification", { message, type, timestamp: new Date() });
  }

  // Export functionality for data analysis
  async exportStats(format = "json") {
    try {
      const response = await fetch(
        `${this.apiBase}/export/stats?format=${format}`
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `email_librarian_stats_${
        new Date().toISOString().split("T")[0]
      }.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      this.handleError(error, "export stats");
    }
  }
}

// Enhanced Alpine.js app with controller integration
function enhancedEmailLibrarianApp() {
  return {
    ...emailLibrarianApp(), // Extend the basic app

    controller: null,
    notifications: [],
    isLoading: false,
    connectionStatus: "disconnected",

    async init() {
      this.isLoading = true;

      // Initialize controller
      this.controller = new EmailLibrarianController();
      this.setupControllerListeners();

      try {
        await this.controller.init();
        await this.loadInitialData();
        this.connectionStatus = "connected";
      } catch (error) {
        console.error("❌ Failed to initialize:", error);
        this.connectionStatus = "error";
      } finally {
        this.isLoading = false;
      }
    },

    setupControllerListeners() {
      this.controller.on("websocket:connected", () => {
        this.connectionStatus = "connected";
        this.showNotification("Connected to Email Librarian", "success");
      });

      this.controller.on("function:status_changed", (data) => {
        this.functions[data.function].status = data.status;
      });

      this.controller.on("processing:update", (data) => {
        this.updateProcessingStats(data);
      });

      this.controller.on("stats:update", (data) => {
        this.stats = { ...this.stats, ...data };
      });

      this.controller.on("error", (error) => {
        this.showNotification(error, "error");
      });

      this.controller.on("notification", (notification) => {
        this.notifications.unshift(notification);
        if (this.notifications.length > 10) {
          this.notifications = this.notifications.slice(0, 10);
        }
      });
    },

    async loadInitialData() {
      try {
        const { stats, labels } = await this.controller.loadInitialData();
        this.stats = { ...this.stats, ...stats };
        this.availableLabels = labels;
      } catch (error) {
        console.error("❌ Failed to load initial data:", error);
      }
    },

    async toggleFunction(functionName) {
      try {
        this.isLoading = true;
        const enabled = this.functions[functionName].enabled;
        await this.controller.toggleFunction(functionName, enabled);
        this.saveStates();
      } catch (error) {
        // Revert the toggle on error
        this.functions[functionName].enabled =
          !this.functions[functionName].enabled;
      } finally {
        this.isLoading = false;
      }
    },

    async startCataloging() {
      try {
        this.isLoading = true;
        const config = this.functions.cataloging.config;
        await this.controller.startCataloging(config);

        if (!this.functions.cataloging.enabled) {
          this.functions.cataloging.enabled = true;
          await this.toggleFunction("cataloging");
        }

        this.showNotification("Cataloging started successfully", "success");
      } catch (error) {
        this.showNotification("Failed to start cataloging", "error");
      } finally {
        this.isLoading = false;
      }
    },

    async startReclassification() {
      try {
        this.isLoading = true;
        const config = this.functions.reclassification.config;
        await this.controller.startReclassification(config);

        if (!this.functions.reclassification.enabled) {
          this.functions.reclassification.enabled = true;
          await this.toggleFunction("reclassification");
        }

        this.showNotification(
          "Reclassification started successfully",
          "success"
        );
      } catch (error) {
        this.showNotification("Failed to start reclassification", "error");
      } finally {
        this.isLoading = false;
      }
    },

    updateProcessingStats(data) {
      switch (data.function) {
        case "shelving":
          this.functions.shelving.processedToday = data.processed;
          this.functions.shelving.avgSpeed = data.speed;
          break;
        case "cataloging":
          this.functions.cataloging.progress = data.progress;
          this.functions.cataloging.processed = data.processed;
          this.functions.cataloging.remaining = data.remaining;
          break;
        case "reclassification":
          this.functions.reclassification.reclassifiedCount = data.reclassified;
          break;
      }
    },

    showNotification(message, type = "info") {
      this.notifications.unshift({
        id: Date.now(),
        message,
        type,
        timestamp: new Date(),
      });

      // Auto-remove after 5 seconds
      setTimeout(() => {
        this.notifications = this.notifications.filter(
          (n) => n.id !== this.notifications[0]?.id
        );
      }, 5000);
    },

    dismissNotification(notificationId) {
      this.notifications = this.notifications.filter(
        (n) => n.id !== notificationId
      );
    },

    async exportData() {
      try {
        await this.controller.exportStats("json");
        this.showNotification("Data exported successfully", "success");
      } catch (error) {
        this.showNotification("Failed to export data", "error");
      }
    },
  };
}

// Global initialization
document.addEventListener("DOMContentLoaded", () => {
  console.log("📚 Email Librarian frontend loaded");
});
