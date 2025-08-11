/**
 * Gmail AI Suite Dashboard - Additional JavaScript Utilities
 * Extends the main Alpine.js application with utility functions
 */

// Global configuration
window.GmailAI = {
  config: {
    apiBaseUrl: "http://localhost:8000",
    refreshInterval: 30000, // 30 seconds
    chartColors: {
      primary: "#3B82F6",
      success: "#10B981",
      warning: "#F59E0B",
      danger: "#EF4444",
      purple: "#8B5CF6",
      cyan: "#06B6D4",
      lime: "#84CC16",
      orange: "#F97316",
    },
  },

  // Utility functions
  utils: {
    /**
     * Format timestamp to human readable format
     */
    formatTimestamp(timestamp) {
      if (!timestamp) return "N/A";
      const date = new Date(timestamp);
      const now = new Date();
      const diff = now - date;

      // Less than 1 minute
      if (diff < 60000) {
        return "Just now";
      }

      // Less than 1 hour
      if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes} minute${minutes > 1 ? "s" : ""} ago`;
      }

      // Less than 1 day
      if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours > 1 ? "s" : ""} ago`;
      }

      // More than 1 day
      return date.toLocaleDateString() + " " + date.toLocaleTimeString();
    },

    /**
     * Format file size to human readable format
     */
    formatFileSize(bytes) {
      if (bytes === 0) return "0 Bytes";
      const k = 1024;
      const sizes = ["Bytes", "KB", "MB", "GB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    },

    /**
     * Generate random ID
     */
    generateId() {
      return Date.now().toString(36) + Math.random().toString(36).substr(2);
    },

    /**
     * Debounce function calls
     */
    debounce(func, wait) {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          clearTimeout(timeout);
          func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
      };
    },

    /**
     * Deep clone object
     */
    deepClone(obj) {
      return JSON.parse(JSON.stringify(obj));
    },

    /**
     * Validate email address
     */
    isValidEmail(email) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return emailRegex.test(email);
    },

    /**
     * Truncate text to specified length
     */
    truncateText(text, maxLength = 100) {
      if (!text || text.length <= maxLength) return text;
      return text.substring(0, maxLength) + "...";
    },

    /**
     * Generate color based on category name
     */
    getCategoryColor(categoryName) {
      const colors = Object.values(this.config.chartColors);
      const hash = categoryName.split("").reduce((a, b) => {
        a = (a << 5) - a + b.charCodeAt(0);
        return a & a;
      }, 0);
      return colors[Math.abs(hash) % colors.length];
    },
  },

  // API helpers
  api: {
    /**
     * Make API request with error handling
     */
    async request(endpoint, options = {}) {
      const url = `${window.GmailAI.config.apiBaseUrl}${endpoint}`;
      const defaultOptions = {
        headers: {
          "Content-Type": "application/json",
        },
      };

      try {
        const response = await fetch(url, { ...defaultOptions, ...options });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
      } catch (error) {
        console.error("API request failed:", error);
        throw error;
      }
    },

    /**
     * Get server health status
     */
    async getHealth() {
      return this.request("/health");
    },

    /**
     * Classify email
     */
    async classifyEmail(emailData) {
      return this.request("/api/classify-email-with-categories", {
        method: "POST",
        body: JSON.stringify(emailData),
      });
    },

    /**
     * Get email analytics
     */
    async getAnalytics(daysBack = 7) {
      return this.request(`/api/email-analytics?days_back=${daysBack}`);
    },

    /**
     * Configure webhook
     */
    async configureWebhook(webhookData) {
      return this.request("/webhooks/configure", {
        method: "POST",
        body: JSON.stringify(webhookData),
      });
    },

    /**
     * List webhooks
     */
    async listWebhooks() {
      return this.request("/webhooks/list");
    },

    /**
     * Delete webhook
     */
    async deleteWebhook(webhookId) {
      return this.request(`/webhooks/${webhookId}`, {
        method: "DELETE",
      });
    },
  },

  // Chart utilities
  charts: {
    /**
     * Create doughnut chart
     */
    createDoughnutChart(canvas, data, options = {}) {
      const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        aspectRatio: 1.2,
        layout: {
          padding: {
            top: 10,
            bottom: 10,
            left: 10,
            right: 10,
          },
        },
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              padding: 15,
              usePointStyle: true,
              font: {
                size: 12,
              },
              boxWidth: 12,
              boxHeight: 12,
            },
          },
          tooltip: {
            backgroundColor: "rgba(0, 0, 0, 0.8)",
            titleColor: "white",
            bodyColor: "white",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1,
          },
        },
      };

      return new Chart(canvas, {
        type: "doughnut",
        data: data,
        options: { ...defaultOptions, ...options },
      });
    },

    /**
     * Create line chart
     */
    createLineChart(canvas, data, options = {}) {
      const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        aspectRatio: 1.5,
        layout: {
          padding: {
            top: 10,
            bottom: 10,
            left: 5,
            right: 5,
          },
        },
        plugins: {
          legend: {
            position: "top",
            labels: {
              padding: 15,
              font: {
                size: 12,
              },
              boxWidth: 12,
              boxHeight: 12,
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: {
              color: "rgba(0, 0, 0, 0.1)",
            },
            ticks: {
              font: {
                size: 11,
              },
            },
          },
          x: {
            grid: {
              color: "rgba(0, 0, 0, 0.1)",
            },
            ticks: {
              font: {
                size: 11,
              },
            },
          },
        },
      };

      return new Chart(canvas, {
        type: "line",
        data: data,
        options: { ...defaultOptions, ...options },
      });
    },

    /**
     * Create bar chart
     */
    createBarChart(canvas, data, options = {}) {
      const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        aspectRatio: 1.5,
        layout: {
          padding: {
            top: 10,
            bottom: 10,
            left: 5,
            right: 5,
          },
        },
        plugins: {
          legend: {
            display: false,
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: {
              color: "rgba(0, 0, 0, 0.1)",
            },
            ticks: {
              font: {
                size: 11,
              },
            },
          },
          x: {
            grid: {
              display: false,
            },
            ticks: {
              font: {
                size: 11,
              },
            },
          },
        },
      };

      return new Chart(canvas, {
        type: "bar",
        data: data,
        options: { ...defaultOptions, ...options },
      });
    },
  },

  // Local storage helpers
  storage: {
    /**
     * Save data to localStorage
     */
    save(key, data) {
      try {
        localStorage.setItem(`gmailai_${key}`, JSON.stringify(data));
        return true;
      } catch (error) {
        console.error("Failed to save to localStorage:", error);
        return false;
      }
    },

    /**
     * Load data from localStorage
     */
    load(key, defaultValue = null) {
      try {
        const item = localStorage.getItem(`gmailai_${key}`);
        return item ? JSON.parse(item) : defaultValue;
      } catch (error) {
        console.error("Failed to load from localStorage:", error);
        return defaultValue;
      }
    },

    /**
     * Remove data from localStorage
     */
    remove(key) {
      try {
        localStorage.removeItem(`gmailai_${key}`);
        return true;
      } catch (error) {
        console.error("Failed to remove from localStorage:", error);
        return false;
      }
    },

    /**
     * Clear all Gmail AI data from localStorage
     */
    clear() {
      try {
        const keys = Object.keys(localStorage).filter((key) =>
          key.startsWith("gmailai_")
        );
        keys.forEach((key) => localStorage.removeItem(key));
        return true;
      } catch (error) {
        console.error("Failed to clear localStorage:", error);
        return false;
      }
    },
  },

  // Notification system
  notifications: {
    /**
     * Show success notification
     */
    success(title, message, duration = 5000) {
      this.show("success", title, message, duration);
    },

    /**
     * Show error notification
     */
    error(title, message, duration = 8000) {
      this.show("error", title, message, duration);
    },

    /**
     * Show warning notification
     */
    warning(title, message, duration = 6000) {
      this.show("warning", title, message, duration);
    },

    /**
     * Show info notification
     */
    info(title, message, duration = 4000) {
      this.show("info", title, message, duration);
    },

    /**
     * Show notification (internal)
     */
    show(type, title, message, duration) {
      // This will be called from Alpine.js context
      if (window.dashboardApp && window.dashboardApp.showNotification) {
        window.dashboardApp.showNotification(type, title, message);

        if (duration > 0) {
          setTimeout(() => {
            if (window.dashboardApp.notification) {
              window.dashboardApp.notification.show = false;
            }
          }, duration);
        }
      }
    },
  },

  // Theme management
  theme: {
    /**
     * Toggle dark mode
     */
    toggleDarkMode() {
      const body = document.body;
      body.classList.toggle("dark-mode");
      const isDark = body.classList.contains("dark-mode");
      this.save("darkMode", isDark);
      return isDark;
    },

    /**
     * Apply saved theme
     */
    applySavedTheme() {
      const isDark = window.GmailAI.storage.load("darkMode", false);
      if (isDark) {
        document.body.classList.add("dark-mode");
      }
    },

    /**
     * Get current theme
     */
    getCurrentTheme() {
      return document.body.classList.contains("dark-mode") ? "dark" : "light";
    },
  },
};

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Apply saved theme
  window.GmailAI.theme.applySavedTheme();

  // Set up global error handler
  window.addEventListener("error", function (event) {
    console.error("Global error:", event.error);
    if (window.GmailAI.notifications) {
      window.GmailAI.notifications.error(
        "Application Error",
        "An unexpected error occurred. Please refresh the page."
      );
    }
  });

  // Set up unhandled promise rejection handler
  window.addEventListener("unhandledrejection", function (event) {
    console.error("Unhandled promise rejection:", event.reason);
    if (window.GmailAI.notifications) {
      window.GmailAI.notifications.error(
        "Network Error",
        "Failed to communicate with the server. Please check your connection."
      );
    }
  });

  console.log("Gmail AI Suite Dashboard initialized");
});

// Export for module usage
if (typeof module !== "undefined" && module.exports) {
  module.exports = window.GmailAI;
}
