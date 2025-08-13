# Tailwind CSS Setup

This project uses Tailwind CSS with a local build process instead of CDN to avoid production warnings.

## Quick Start

### Build CSS for production:
```bash
npm run build-css-prod
```

### Development with auto-rebuild:
```bash
npm run build-css
```

This will watch for changes in `frontend/styles/input.css` and automatically rebuild `frontend/styles/output.css`.

## File Structure

```
frontend/styles/
├── input.css          # Source CSS with Tailwind directives
└── output.css         # Built CSS served to browser
```

## Configuration Files

- `tailwind.config.js` - Tailwind configuration
- `postcss.config.js` - PostCSS configuration  
- `package.json` - Build scripts

## Benefits

✅ **No CDN warnings** - Uses local build instead of CDN
✅ **Smaller bundle** - Only includes used Tailwind classes
✅ **Custom components** - Add your own CSS components
✅ **Production ready** - Minified and optimized
✅ **Offline support** - No external dependencies

## Adding Custom Styles

Edit `frontend/styles/input.css` to add custom components:

```css
@import "tailwindcss";

@layer components {
  .my-custom-class {
    /* Your custom CSS */
  }
}
```

Then run `npm run build-css-prod` to rebuild.

## Troubleshooting

**CSS not updating?**
- Make sure you've run the build command after making changes
- Check that `frontend/styles/output.css` exists and has recent timestamp
- Verify server is serving files from `/static/styles/output.css`

**Missing Tailwind classes?**
- Add the file path to `content` array in `tailwind.config.js`
- Make sure the classes are used in your HTML files
