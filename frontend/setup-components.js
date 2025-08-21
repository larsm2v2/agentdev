// Components Symlink/Copy Script
const fs = require("fs");
const path = require("path");

// Paths
const sourceDir = path.join(__dirname, "..", "components");
const targetDir = path.join(__dirname, "..", "static", "components");

// Create target directory if it doesn't exist
if (!fs.existsSync(targetDir)) {
  fs.mkdirSync(targetDir, { recursive: true });
  console.log(`Created directory: ${targetDir}`);
}

// Copy all HTML files from components directory to static/components
fs.readdir(sourceDir, (err, files) => {
  if (err) {
    console.error(`Error reading directory: ${err.message}`);
    return;
  }

  files
    .filter((file) => file.endsWith(".html"))
    .forEach((file) => {
      const sourcePath = path.join(sourceDir, file);
      const targetPath = path.join(targetDir, file);

      fs.copyFile(sourcePath, targetPath, (err) => {
        if (err) {
          console.error(`Error copying ${file}: ${err.message}`);
        } else {
          console.log(`Successfully copied ${file} to static/components`);
        }
      });
    });
});

console.log(
  "Component setup completed. Files are now accessible at /static/components/"
);
