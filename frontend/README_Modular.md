# Email Librarian Frontend - Modular Structure

This directory contains a modular frontend structure that can be easily maintained and potentially migrated to React/Next.js.

## Structure Overview

```
frontend/
├── main.html                          # Main layout file
├── components/                        # HTML Components (current implementation)
│   ├── status-notifications.html     # Connection status & notifications
│   ├── header.html                   # Main header component
│   ├── function-cards.html           # Function cards grid
│   ├── statistics.html               # Statistics overview
│   ├── tab-container.html            # Tab content wrapper
│   └── tabs/                         # Individual tab components
│       ├── shelving-tab.html
│       ├── cataloging-tab.html
│       ├── reclassification-tab.html
│       └── workflows-tab.html
├── js/                               # JavaScript modules
│   ├── core.js                      # Main application logic
│   └── components-loader.js         # Dynamic component loader
├── styles/                          # CSS files
│   └── email_librarian.css          # Main styles
└── react-ready/                     # React/Next.js ready components
    └── components/
        └── WorkflowsTab.jsx         # Example React component

```

## Current Implementation (HTML + Alpine.js)

### How It Works

1. **main.html** - Main layout with container divs
2. **components-loader.js** - Dynamically loads HTML components into containers
3. **core.js** - Contains all application logic using Alpine.js patterns
4. **Individual components** - Separate HTML files for each UI section

### Benefits

- ✅ Easy to work on individual components in isolation
- ✅ Clear separation of concerns
- ✅ Reusable components
- ✅ Maintains current Alpine.js functionality
- ✅ No build process required

### Usage

1. Open `main.html` in a browser
2. Components are automatically loaded via JavaScript
3. Alpine.js handles interactivity

## Migration to React/Next.js

### React-Ready Components

The `react-ready/` directory contains example React components that mirror the HTML structure.

### Migration Steps

1. **Convert HTML components to JSX** - Use the structure from HTML components
2. **Extract state management** - Convert Alpine.js reactive data to React hooks
3. **Convert methods** - Transform Alpine.js methods to React functions
4. **Style conversion** - Keep Tailwind CSS classes as-is

### Example: WorkflowsTab.jsx

```jsx
// Already converted with proper React patterns:
// - Props for data and functions
// - Conditional rendering
// - Event handlers
// - Map functions for lists
// - Tailwind CSS classes preserved
```

## Working on Individual Tabs

### Current Workflow (HTML)

1. Edit the specific tab file in `components/tabs/`
2. Refresh browser to see changes
3. No build process needed

### Future React Workflow

1. Edit the JSX component in `react-ready/components/`
2. Use React dev server for hot reloading
3. Import and use in main application

## File Organization

### Components

- **status-notifications.html** - Connection status indicator, notification system, loading overlay
- **header.html** - Main application header with stats
- **function-cards.html** - Grid of function cards (Shelving, Cataloging, Reclassification, Workflows)
- **statistics.html** - Statistics overview cards
- **tabs/** - Individual tab content for detailed views

### JavaScript

- **core.js** - Main application state and methods
- **components-loader.js** - Handles dynamic HTML loading

### Advantages of This Structure

1. **Modularity** - Each component is in its own file
2. **Maintainability** - Easy to find and edit specific features
3. **Collaboration** - Multiple developers can work on different tabs
4. **Migration Ready** - Clear path to React/Next.js
5. **No Build Complexity** - Current version works without build tools
6. **Reusability** - Components can be reused across different pages

## Next Steps

1. **Immediate**: Work on individual tabs by editing their HTML files
2. **Short-term**: Add more interactive features to existing components
3. **Long-term**: Migrate to React/Next.js using the react-ready components as templates

## API Integration Points

Each tab component is designed to easily integrate with backend APIs:

- **Shelving**: Real-time email processing endpoints
- **Cataloging**: Batch processing APIs
- **Reclassification**: Label management APIs
- **Workflows**: n8n integration endpoints

The modular structure makes it easy to add API calls to individual components without affecting others.
