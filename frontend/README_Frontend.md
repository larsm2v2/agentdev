# Email Librarian Frontend 📚

## Overview

The **Email Librarian** is a modern, AI-powered email organization system with three primary functions:

1. **Shelving** - Realtime organization of incoming emails
2. **Cataloging** - Email library organization for historical emails
3. **Reclassification** - Email specific label changes and reorganization

## Features

### 🏗️ **Architecture**

- **Modern Alpine.js Framework** - Reactive, lightweight frontend
- **WebSocket Integration** - Real-time updates and status monitoring
- **Modular Design** - Clean separation of concerns
- **Responsive Layout** - Works on desktop and mobile devices

### 🎛️ **Function Management**

- **Toggle Controls** - Easy on/off switches for each function
- **Persistent State** - Settings saved to localStorage
- **Real-time Status** - Live updates on function activity
- **Detailed Configuration** - Customizable settings for each function

### 📊 **Statistics & Monitoring**

- **Live Statistics** - Real-time processing metrics
- **Progress Tracking** - Visual progress bars for long-running tasks
- **Activity Feeds** - Recent activity logs for each function
- **Performance Metrics** - Speed, accuracy, and efficiency tracking

### 🎨 **User Experience**

- **Modern UI Design** - Clean, professional interface
- **Smooth Animations** - Engaging transitions and effects
- **Notification System** - Toast notifications for important events
- **Loading States** - Clear feedback during processing
- **Connection Status** - Real-time connection monitoring

## File Structure

```
frontend/
├── email_librarian.html          # Main HTML interface
├── email_librarian.js            # Advanced JavaScript controller
├── email_librarian.css           # Enhanced styling and animations
└── README_Frontend.md            # This documentation
```

## Getting Started

### 1. **Setup**

```bash
# Navigate to frontend directory
cd frontend

# Serve the files (using Python's built-in server)
python -m http.server 8080

# Or use any static file server
# The interface will be available at http://localhost:8080/email_librarian.html
```

### 2. **Development**

- The frontend expects API endpoints at `/api/*`
- WebSocket connection at `/ws`
- All configurations are automatically saved to localStorage

### 3. **Integration**

The frontend integrates with the Email Librarian backend through:

- RESTful API calls for configuration and control
- WebSocket connections for real-time updates
- Local storage for persistent user preferences

## Function Details

### 🗂️ **Shelving (Realtime Organization)**

- **Purpose**: Automatically organize incoming emails as they arrive
- **Configuration**:
  - Processing interval (1-30 minutes)
  - Batch size (1-100 emails)
  - Auto-archive options
- **Features**:
  - Real-time processing stats
  - Activity timeline
  - Performance monitoring

### 📚 **Cataloging (Email Library Organization)**

- **Purpose**: Process and organize historical emails (older than 1 day)
- **Configuration**:
  - Date range selection
  - Batch processing size (10-500 emails)
  - Progress tracking
- **Features**:
  - Visual progress bars
  - Detailed processing metrics
  - Pause/resume capability

### 🏷️ **Reclassification (Email Specific Label Changes)**

- **Purpose**: Reorganize groups of emails based on existing labels
- **Configuration**:
  - Source label selection
  - Target category mapping
  - Batch processing options
- **Features**:
  - Label management interface
  - Results tracking
  - Category selection tools

## API Integration

### Expected Endpoints

```javascript
// Function Management
POST /api/shelving/toggle          // Enable/disable shelving
POST /api/cataloging/toggle        // Enable/disable cataloging
POST /api/reclassification/toggle  // Enable/disable reclassification

// Configuration
POST /api/shelving/configure       // Configure shelving settings
POST /api/cataloging/start         // Start cataloging process
POST /api/reclassification/start   // Start reclassification

// Status & Data
GET  /api/stats/overall           // Overall system statistics
GET  /api/shelving/stats          // Shelving-specific stats
GET  /api/cataloging/progress     // Cataloging progress
GET  /api/reclassification/results // Reclassification results
GET  /api/categories              // Available categories
GET  /api/reclassification/labels // Available labels

// Export
GET  /api/export/stats            // Export statistics data
```

### WebSocket Events

```javascript
// Incoming Events
{
  "type": "function_status",
  "function": "shelving",
  "status": "active"
}

{
  "type": "processing_update",
  "function": "cataloging",
  "progress": 75,
  "processed": 150,
  "remaining": 50
}

{
  "type": "stats_update",
  "stats": {
    "totalProcessed": 3240,
    "avgSpeed": 25
  }
}
```

## Customization

### 🎨 **Styling**

- Modify `email_librarian.css` to customize appearance
- Built with Tailwind CSS classes for easy theming
- Supports dark mode with CSS media queries
- Custom gradients and animations included

### 🔧 **Functionality**

- Extend `EmailLibrarianController` class for new features
- Add custom API endpoints by modifying the controller
- Create new function types by extending the Alpine.js app
- Add custom event handlers through the event system

### 📱 **Responsive Design**

- Mobile-first approach with responsive breakpoints
- Touch-friendly interface elements
- Adaptive layouts for different screen sizes
- Optimized performance on mobile devices

## Technical Details

### **Dependencies**

- **Alpine.js 3.x** - Reactive framework
- **Tailwind CSS** - Utility-first CSS framework
- **Font Awesome 6.4** - Icon library
- **Chart.js** - Data visualization (if needed)

### **Browser Support**

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

### **Performance**

- Lightweight footprint (~50KB total)
- Efficient DOM updates through Alpine.js
- Optimized WebSocket handling
- Smart caching of API responses

## Troubleshooting

### Common Issues

1. **Connection Problems**

   - Check if backend server is running
   - Verify WebSocket endpoint is available
   - Check browser console for errors

2. **State Not Persisting**

   - Ensure localStorage is enabled
   - Check browser privacy settings
   - Clear cache if experiencing issues

3. **UI Not Updating**
   - Check WebSocket connection status
   - Verify API endpoints are responding
   - Look for JavaScript errors in console

### Debug Mode

```javascript
// Enable debug mode in browser console
window.emailLibrarianDebug = true;
```

## Future Enhancements

- [ ] Drag-and-drop email management
- [ ] Advanced filtering and search
- [ ] Email preview functionality
- [ ] Bulk operations interface
- [ ] Custom dashboard widgets
- [ ] Integration with external services
- [ ] Advanced analytics and reporting
- [ ] Multi-user support
- [ ] Email template management
- [ ] Automated rule creation

## Contributing

To contribute to the Email Librarian frontend:

1. Follow the existing code structure
2. Use consistent naming conventions
3. Add appropriate comments for complex logic
4. Test on multiple browsers and devices
5. Update documentation for new features

---

**Email Librarian Frontend** - Making email organization intelligent and effortless! 📚✨
