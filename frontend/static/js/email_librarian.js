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
        config: {
          startDate: "",
          endDate: "",
          batchSize: 50,
        },
      },
      reclassification: {
        name: "Reclassification",
        endpoint: "/reclassification",
        status: "inactive",
        config: {
          startDate: "",
          endDate: "",
          batchSize: 50,
        },
      },
      workflows: {
        name: "Workflows",
        endpoint: "/workflows",
        status: "active",
        activeWorkflows: [
          {
            id: "wf_1",
            name: "Daily Email Summary",
            description: "Creates a daily digest of important emails",
            active: true,
            executions: 24,
            lastRun: "2 hours ago",
            schedule: "Daily at 8:00 AM",
          },
          {
            id: "wf_2",
            name: "Newsletter Categorizer",
            description: "Automatically categorizes newsletter emails",
            active: true,
            executions: 156,
            lastRun: "45 minutes ago",
            schedule: "Every 4 hours",
          },
          {
            id: "wf_3",
            name: "Spam Detector",
            description: "Advanced spam detection using ML",
            active: false,
            executions: 58,
            lastRun: "Yesterday",
            schedule: "Every hour",
          },
        ],
        executionHistory: [
          {
            id: "ex_1",
            workflowName: "Daily Email Summary",
            status: "success",
            timestamp: "2 hours ago",
            details: "Processed 124 emails, created summary report",
            showDetails: false,
          },
          {
            id: "ex_2",
            workflowName: "Newsletter Categorizer",
            status: "success",
            timestamp: "45 minutes ago",
            details: "Categorized 37 newsletters into 8 categories",
            showDetails: false,
          },
          {
            id: "ex_3",
            workflowName: "Spam Detector",
            status: "warning",
            timestamp: "Yesterday",
            details: "Detected 12 spam emails, 2 false positives",
            showDetails: false,
          },
        ],
      },
    };
    this.eventListeners = {};
    // WebSocket connection helpers
    this._wsConnected = false;
    this._wsConnectedPromise = null;
    this._wsConnectedResolve = null;
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
    // Server exposes WebSocket at /ws
    const wsUrl = `${wsProtocol}${window.location.host}/ws`;

    this.websocket = new WebSocket(wsUrl);

    this.websocket.onopen = () => {
      console.log("🔌 WebSocket connected");
      this._wsConnected = true;
      // resolve any waiter
      try {
        if (this._wsConnectedResolve) this._wsConnectedResolve();
      } catch (e) {
        console.warn("Error resolving websocket connected promise:", e);
      }
      this.emit("websocket:connected");

      // Refresh reclassification labels immediately after reconnect
      (async () => {
        try {
          const labels = await this.getAvailableLabels();
          this.emit("labels:updated", labels);
        } catch (e) {
          console.warn("Failed to refresh labels after websocket connect:", e);
        }
      })();
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

      if (!response.ok) {
        // If backend returned an error (404/500), fall through to mock fallback
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      // If server returned an explicit enabled state, honor it
      if (result && Object.prototype.hasOwnProperty.call(result, "enabled")) {
        try {
          this.functions[functionName].enabled = !!result.enabled;
        } catch (e) {
          console.warn("Toggle result: function state not found", functionName);
        }
      }
      // Emit status changed for UI updates
      const statusAfter =
        this.functions[functionName] && this.functions[functionName].enabled
          ? "active"
          : "inactive";
      this.emit("function:status_changed", {
        function: functionName,
        status: statusAfter,
      });
      this.emit("function:toggled", {
        function: functionName,
        enabled,
        result,
      });
      return result;
    } catch (error) {
      // Network or server error — provide a visual mock response so UI can be tested
      console.warn(
        `⚠️ Toggle API unavailable, using mock response for ${functionName}:`,
        error
      );

      // Update local controller state to reflect the toggle (optimistic UI)
      try {
        this.functions[functionName].enabled = !!enabled;
      } catch (e) {
        console.warn(
          "Mock toggle: function not found in controller state",
          functionName
        );
      }

      // Emit events so Alpine UI updates if it's listening for status changes
      const mockResult = { status: "mock", message: "Mock toggle succeeded" };
      this.emit("function:toggled", {
        function: functionName,
        enabled,
        result: mockResult,
      });

      // Also broadcast a status_changed event for UI pieces that listen to it
      const status = enabled ? "active" : "inactive";
      this.emit("function:status_changed", { function: functionName, status });

      // Return a resolved promise with mock result to callers
      return mockResult;
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
      console.log("🎯 CONTROLLER: startCataloging called");
      console.log("🔧 Controller starting cataloging with config:", config);
      console.log("🌐 API Base URL:", this.apiBase);

      // Convert frontend config to API format
      const apiConfig = {
        start_date: config.startDate,
        end_date: config.endDate,
        batch_size: config.batchSize || 50,
      };

      console.log("📡 Converted API config:", apiConfig);
      console.log("🔗 Full URL:", `${this.apiBase}/functions/cataloging/start`);

      const requestData = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(apiConfig),
      };

      console.log("📤 Request details:", requestData);
      console.log("📦 Request body:", JSON.stringify(apiConfig));

      console.log("🚀 Making fetch request...");
      const response = await fetch(
        `${this.apiBase}/functions/cataloging/start`,
        requestData
      );

      console.log("📥 Response received:", {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        headers: Object.fromEntries(response.headers.entries()),
      });

      if (!response.ok) {
        console.log("❌ Response not OK, getting error text...");
        const errorText = await response.text();
        console.error("❌ API Error Response:", errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      console.log("✅ Response OK, parsing JSON...");
      const result = await response.json();
      console.log("🎉 API Result SUCCESS:", result);
      return result;
      return result;
    } catch (error) {
      console.error("❌ Failed to start cataloging:", error);
      throw error;
    }
  }

  async getCatalogingProgress() {
    try {
      const response = await fetch(
        `${this.apiBase}/functions/cataloging/progress`
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to get cataloging progress:", error);
      throw error;
    }
  }

  async pauseCataloging() {
    try {
      const response = await fetch(
        `${this.apiBase}/functions/cataloging/stop`,
        {
          method: "POST",
        }
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("❌ Failed to pause cataloging:", error);
      throw error;
    }
  }

  // Reclassification Methods
  async getAvailableLabels() {
    // Wait for websocket to be connected (short timeout) before trying GET
    try {
      await this.waitForWebSocketConnected(10000);
    } catch (e) {
      console.warn(
        "WebSocket not connected before labels fetch, proceeding anyway:",
        e
      );
    }

    try {
      const url = `${this.apiBase}/labels`;
      const response = await fetch(url);

      if (!response.ok) {
        // If endpoint does not exist (404) or other server error, return empty list
        if (response.status === 404) {
          console.warn(
            `⚠️ Labels endpoint not found (404): ${url} — returning empty labels list`
          );
          return [];
        }
        // For other non-OK responses, throw to allow fallback handling upstream
        throw new Error(`HTTP ${response.status}`);
      }

      const labels = await response.json();
      // Convert any proxied/reactive array into a plain array before caching/logging
      let plainLabels;
      try {
        if (Array.isArray(labels)) {
          // slice() will return a shallow copy and unwrap proxies in most frameworks
          plainLabels = labels.slice();
        } else {
          // Try to coerce any iterable to array, otherwise empty
          plainLabels = Array.from(labels || []);
        }
      } catch (e) {
        plainLabels = [];
      }

      // Short-term in-memory cache: replace on each successful GET
      try {
        this._labelsCache = plainLabels;
      } catch (e) {
        console.warn("⚠️ Unable to set labels cache:", e);
      }

      // Log the plain array so console shows contents instead of Proxy(Array)
      console.log("📥 Reclassification labels received:", plainLabels);
      return this._labelsCache;
    } catch (error) {
      // Network or unexpected error — log and return empty list so UI can continue
      console.warn(
        "⚠️ Failed to get available labels, returning empty list:",
        error
      );
      return [];
    }
  }

  // Wait for websocket ready with timeout (ms)
  waitForWebSocketConnected(timeoutMs = 10000) {
    if (this._wsConnected) return Promise.resolve();
    if (!this._wsConnectedPromise) {
      this._wsConnectedPromise = new Promise((resolve) => {
        this._wsConnectedResolve = resolve;
      });
    }

    // Race with timeout
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error("timeout waiting for websocket connected"));
      }, timeoutMs);

      this._wsConnectedPromise
        .then(() => {
          clearTimeout(timer);
          resolve();
        })
        .catch((e) => {
          clearTimeout(timer);
          reject(e);
        });
    });
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
      // Load persisted UI state (toggles, selected tab, etc.)
      this.loadStates();

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

      this.controller.on("labels:updated", (labels) => {
        try {
          const arr = Array.isArray(labels) ? labels : [];
          const prevCount = Array.isArray(this.availableLabels)
            ? this.availableLabels.length
            : 0;
          this.availableLabels = arr;
          // Log a compact JSON representation for easier debugging
          try {
            console.log(
              "📥 Reclassification labels (json):",
              JSON.stringify(arr)
            );
          } catch (e) {
            console.log("📥 Reclassification labels:", arr);
          }

          // Only show a toast when the count actually changes
          if (arr.length !== prevCount) {
            this.showNotification(`${arr.length} labels available`, "info");
          }
        } catch (e) {
          console.warn("Failed to apply updated labels to UI:", e);
        }
      });

      this.controller.on("function:status_changed", (data) => {
        // Keep both status and enabled state in sync
        if (this.functions[data.function]) {
          this.functions[data.function].status = data.status;
          this.functions[data.function].enabled = data.status === "active";
        }
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
        // The input's x-model already updated the local state before this handler
        // Use the current local state as the desired state to send to the controller
        const desiredEnabled = !!this.functions[functionName].enabled;
        const result = await this.controller.toggleFunction(
          functionName,
          desiredEnabled
        );

        // If server returned an explicit enabled value, honor it
        if (result && Object.prototype.hasOwnProperty.call(result, "enabled")) {
          this.functions[functionName].enabled = !!result.enabled;
        }

        // Persist UI state
        this.saveStates();
        return result;
      } catch (error) {
        // Revert the toggle on error
        this.functions[functionName].enabled =
          !this.functions[functionName].enabled;
        console.error("Toggle failed:", error);
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    async startCataloging() {
      try {
        console.log("� BUTTON PRESSED: Start Cataloging button clicked!");
        console.log("🔍 Current state:", {
          isLoading: this.isLoading,
          functions: this.functions,
          catalogingConfig: this.functions.cataloging?.config,
        });

        this.isLoading = true;
        const config = this.functions.cataloging.config;

        console.log("📋 Cataloging Config:", config);
        console.log("📅 Date validation:", {
          startDate: config.startDate,
          endDate: config.endDate,
          hasStartDate: !!config.startDate,
          hasEndDate: !!config.endDate,
        });

        // Validate config
        if (!config.startDate || !config.endDate) {
          console.log("❌ Validation failed: Missing dates");
          this.showNotification("Please select start and end dates", "error");
          return;
        }

        console.log("✅ Validation passed, calling controller...");
        const result = await this.controller.startCataloging(config);
        console.log("🎉 Controller returned:", result);

        if (!this.functions.cataloging.enabled) {
          console.log("🔧 Enabling cataloging function...");
          this.functions.cataloging.enabled = true;
          await this.toggleFunction("cataloging");
        }

        console.log("✅ Cataloging job started successfully!");
        console.log("📊 Starting progress monitoring...");
        this.startCatalogingProgressMonitoring();

        this.showNotification("Cataloging started successfully", "success");
      } catch (error) {
        console.error("❌ Cataloging error:", error);
        console.error("❌ Error details:", {
          message: error.message,
          stack: error.stack,
          name: error.name,
        });
        this.showNotification(
          `Failed to start cataloging: ${error.message}`,
          "error"
        );
      } finally {
        console.log(
          "🏁 Cataloging function completed, setting isLoading = false"
        );
        this.isLoading = false;
      }
    },

    // Add progress monitoring method for cataloging
    startCatalogingProgressMonitoring() {
      console.log("🔄 Starting cataloging progress monitoring...");

      // Clear any existing interval
      if (this.catalogingProgressInterval) {
        clearInterval(this.catalogingProgressInterval);
      }

      // Poll for progress updates every 10 seconds
      this.catalogingProgressInterval = setInterval(async () => {
        try {
          console.log("📊 Fetching cataloging progress...");
          const response = await fetch("/api/functions/cataloging/progress");

          if (response.ok) {
            const data = await response.json();
            console.log("📈 Progress data received:", data);

            if (data.status === "success") {
              // Update progress data
              this.functions.cataloging.progress =
                data.progress.progress_percentage;
              this.functions.cataloging.processed =
                data.progress.processed_emails;
              this.functions.cataloging.remaining =
                data.progress.remaining_emails;
              this.functions.cataloging.processingRate =
                data.progress.processing_speed;

              // Update historical count
              this.functions.cataloging.historicalCount =
                data.progress.processed_emails + data.progress.remaining_emails;

              // Update API monitoring data
              this.functions.cataloging.apiCalls = data.progress.api_calls || 0;
              this.functions.cataloging.apiCallsPerMinute =
                data.progress.api_calls_per_minute || 0;
              this.functions.cataloging.quotaUsed =
                data.progress.quota_used_percentage || 0;
              this.functions.cataloging.estimatedTime =
                data.progress.estimated_completion || "";
              this.functions.cataloging.categoriesFound =
                data.progress.categories_found || [];

              console.log(
                `📊 Progress: ${data.progress.progress_percentage}% (${
                  data.progress.processed_emails
                }/${
                  data.progress.processed_emails +
                  data.progress.remaining_emails
                })`
              );

              // Stop monitoring if complete
              if (data.progress.progress_percentage >= 100) {
                console.log(
                  "✅ Cataloging completed, stopping progress monitoring"
                );
                this.stopCatalogingProgressMonitoring();
                this.functions.cataloging.enabled = false;
                this.showNotification(
                  "Cataloging completed successfully!",
                  "success"
                );
              }
            }
          } else {
            console.error(
              "❌ Progress fetch failed:",
              response.status,
              response.statusText
            );
          }
        } catch (error) {
          console.error("❌ Failed to fetch cataloging progress:", error);
        }
      }, 10000); // 10 seconds
    },

    stopCatalogingProgressMonitoring() {
      console.log("🛑 Stopping cataloging progress monitoring");
      if (this.catalogingProgressInterval) {
        clearInterval(this.catalogingProgressInterval);
        this.catalogingProgressInterval = null;
      }
    },

    async stopCataloging() {
      try {
        console.log("🛑 Stopping cataloging...");
        this.isLoading = true;

        const result = await this.controller.pauseCataloging();
        console.log("🛑 Cataloging stop result:", result);

        // Stop progress monitoring
        this.stopCatalogingProgressMonitoring();

        // Update state
        this.functions.cataloging.enabled = false;

        this.showNotification("Cataloging stopped successfully", "success");
      } catch (error) {
        console.error("❌ Failed to stop cataloging:", error);
        this.showNotification(
          `Failed to stop cataloging: ${error.message}`,
          "error"
        );
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

    // Helper to toggle cataloging from a single button (start <-> cancel)
    async toggleCatalogingAction() {
      // Prevent double clicks while loading
      if (this.isLoading) return;

      if (this.functions.cataloging && this.functions.cataloging.enabled) {
        // If cataloging is currently enabled, treat the button as 'Cancel'
        await this.stopCataloging();
      } else {
        // Otherwise start cataloging
        await this.startCataloging();
      }
    },

    // Provide a label for the cataloging button depending on state
    catalogingButtonLabel() {
      if (this.functions.cataloging && this.functions.cataloging.enabled) {
        return this.isLoading ? "Cancel Cataloging" : "Cancel Cataloging";
      }
      return "Start Cataloging";
    },

    // Provide tailwind classes for the cataloging button (green for start, red for cancel)
    catalogingButtonClass() {
      if (this.functions.cataloging && this.functions.cataloging.enabled) {
        return "w-full bg-red-600 text-white py-2 px-4 rounded-md hover:bg-red-700 transition-colors";
      }
      return "w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 transition-colors";
    },

    toggleWorkflow(workflowId) {
      console.log(`Toggling workflow ${workflowId}`);
      const workflow = this.functions.workflows.activeWorkflows.find(
        (w) => w.id === workflowId
      );
      if (workflow) {
        workflow.active = !workflow.active;
        // Here you would make API call to n8n to start/stop the workflow
      }
    },

    executeWorkflow(workflowId) {
      console.log(`Executing workflow ${workflowId}`);
      // Here you would make API call to n8n to execute the workflow
      const workflow = this.functions.workflows.activeWorkflows.find(
        (w) => w.id === workflowId
      );
      if (workflow) {
        workflow.lastRun = "just now";
        workflow.executions += 1;

        // Add to execution history
        this.functions.workflows.executionHistory.unshift({
          id: `ex_${Date.now()}`,
          workflowName: workflow.name,
          status: "success",
          timestamp: "just now",
          details: "Manual execution completed successfully",
          showDetails: false,
        });

        // Keep only last 10 executions
        if (this.functions.workflows.executionHistory.length > 10) {
          this.functions.workflows.executionHistory =
            this.functions.workflows.executionHistory.slice(0, 10);
        }
      }
    },

    refreshWorkflows() {
      console.log("Refreshing workflows...");
      // Here you would make API calls to refresh workflow data
    },

    toggleExecutionDetails(executionId) {
      console.log(`Toggling execution details for ${executionId}`);
      const execution = this.functions.workflows.executionHistory.find(
        (e) => e.id === executionId
      );
      if (execution) {
        // Toggle the showDetails property
        execution.showDetails = !execution.showDetails;
      }
    },

    saveStates() {
      try {
        const states = {
          functions: this.functions,
          showTab: this.showTab,
        };
        localStorage.setItem("emailLibrarianStates", JSON.stringify(states));
      } catch (e) {
        console.warn("Failed to save states to localStorage", e);
      }
    },

    loadStates() {
      try {
        const saved = localStorage.getItem("emailLibrarianStates");
        if (saved) {
          const states = JSON.parse(saved);
          this.functions = { ...this.functions, ...states.functions };
          this.showTab = states.showTab || this.showTab || "workflows";
        }
      } catch (e) {
        console.warn("Failed to load states from localStorage", e);
      }
    },
  };
}

// Global initialization
document.addEventListener("DOMContentLoaded", () => {
  console.log("📚 Email Librarian frontend loaded");
});
