/**
 * HTMX Values Configuration
 * Consolidated from inline hx-vals attributes across templates
 */

// Dynamic values populated at runtime via data-hx-vals attributes
let CONFIG = {};

// Extract and populate config from data-hx-vals attributes
document.addEventListener('DOMContentLoaded', () => {
  const elements = document.querySelectorAll('[data-hx-vals]');
  elements.forEach(el => {
    if (el.dataset.hxVals) {
      try {
        const config = JSON.parse(el.dataset.hxVals);
        // Merge with existing config
        CONFIG = { ...CONFIG, ...config };
      } catch (e) {
        console.error('Failed to parse data-hx-vals:', e, el);
      }
    }
  });
});

// Export for use in templates
export const getHTMXConfig = () => ({
  worldActions: CONFIG.worldActions || {},
  filters: CONFIG.filters || {},
  settings: CONFIG.settings || {}
});

export default CONFIG;