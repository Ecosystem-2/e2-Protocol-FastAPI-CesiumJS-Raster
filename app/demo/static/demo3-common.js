/**
 * Demo3 Workflow - Common JavaScript Module
 * Shared state management, API calls, and utilities for polygon selection workflow
 */

// ============================================================================
// Configuration - Centralised settings loaded from backend /config endpoint
// ============================================================================
// Default fallbacks (used if config endpoint fails or during initial load)
let API_BASE = 'http://localhost:8080/api/climate-indices';
let CESIUM_ION_TOKEN = '';

const STORAGE_PREFIX = 'demo3_workflow_';

/**
 * Load configuration from backend /config endpoint.
 * Call this early in page initialisation to ensure config is loaded.
 * @returns {Promise<{api_base: string, cesium_ion_token: string}>}
 */
async function loadConfig() {
  try {
    // Use default API_BASE initially to fetch config
    const configUrl = `${API_BASE}/config`;
    const response = await fetch(configUrl);
    if (response.ok) {
      const config = await response.json();
      API_BASE = config.api_base || API_BASE;
      CESIUM_ION_TOKEN = config.cesium_ion_token || CESIUM_ION_TOKEN;
      // Update window exports
      window.API_BASE = API_BASE;
      window.CESIUM_ION_TOKEN = CESIUM_ION_TOKEN;
      console.log('[Config] Loaded from backend:', { api_base: API_BASE, hasToken: !!CESIUM_ION_TOKEN });
      return config;
    }
  } catch (error) {
    console.warn('[Config] Failed to load from backend, using defaults:', error.message);
  }
  return { api_base: API_BASE, cesium_ion_token: CESIUM_ION_TOKEN };
}

// Auto-load config on script load (non-blocking)
loadConfig();

// Workflow State Manager
const WorkflowState = {
  // Get item from localStorage
  get(key) {
    const stored = localStorage.getItem(STORAGE_PREFIX + key);
    return stored ? JSON.parse(stored) : null;
  },
  
  // Set item in localStorage
  set(key, value) {
    localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(value));
  },
  
  // Remove item from localStorage
  remove(key) {
    localStorage.removeItem(STORAGE_PREFIX + key);
  },
  
  // Clear all workflow data
  clearAll() {
    const keys = Object.keys(localStorage);
    keys.forEach(key => {
      if (key.startsWith(STORAGE_PREFIX)) {
        localStorage.removeItem(key);
      }
    });
  },
  
  // Mark step as completed
  completeStep(stepNumber) {
    const completed = this.get('completed_steps') || [];
    if (!completed.includes(stepNumber)) {
      completed.push(stepNumber);
      this.set('completed_steps', completed);
    }
  },
  
  // Check if step is completed
  isStepCompleted(stepNumber) {
    const completed = this.get('completed_steps') || [];
    return completed.includes(stepNumber);
  },
  
  // Get completion percentage
  getProgress() {
    const completed = this.get('completed_steps') || [];
    return Math.round((completed.length / 5) * 100);  // Changed from 6 to 5 steps
  }
};

// API Helper Functions
const API = {
  // Upload and persist asset
  async uploadAsset(file, indexType, timeRange) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('index_type', indexType);
    formData.append('time_range', timeRange);
    
    const response = await fetch(`${API_BASE}/ingest/store`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }
    
    return await response.json();
  },
  
  // List all assets
  async listAssets() {
    const response = await fetch(`${API_BASE}/assets?limit=100&skip=0`);
    
    if (!response.ok) {
      throw new Error(`Failed to load assets: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.assets || [];
  },
  
  // Query polygon statistics (single polygon)
  async queryPolygon(assetId, polygonGeojson) {
    const formData = new FormData();
    formData.append('asset_id', assetId);
    formData.append('polygon_geojson', JSON.stringify(polygonGeojson));
    
    const response = await fetch(`${API_BASE}/query/polygon`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`Query failed: ${response.statusText}`);
    }
    
    return await response.json();
  },
  
  // Query multiple polygons across single or multiple assets
  async queryPolygonsBatch(assetIds, polygonGeojsonArray) {
    const formData = new FormData();
    const assetIdString = Array.isArray(assetIds) ? assetIds.join(',') : assetIds;
    formData.append('asset_ids', assetIdString);
    formData.append('polygons_geojson', JSON.stringify(polygonGeojsonArray));
    
    const response = await fetch(`${API_BASE}/query/polygons/stats`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Query failed: ${response.statusText}`);
    }
    
    return await response.json();
  },
  
  // Export pixel data for multiple polygons as CSV
  async exportPixelData(assetIds, polygonGeojsonArray) {
    const formData = new FormData();
    const assetIdString = Array.isArray(assetIds) ? assetIds.join(',') : assetIds;
    formData.append('asset_ids', assetIdString);
    formData.append('polygons_geojson', JSON.stringify(polygonGeojsonArray));
    formData.append('format', 'csv');
    
    const response = await fetch(`${API_BASE}/query/polygons/pixels`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Export failed: ${response.statusText}`);
    }
    
    return await response.text();
  },
  
  // Save polygon selection
  async saveSelection(title, description, tags, geometry, stats, assetId) {
    const formData = new FormData();
    formData.append('title', title);
    formData.append('description', description || '');
    formData.append('tags', tags || '');
    formData.append('geometry', JSON.stringify(geometry));
    
    // Add locale_id (optional for grouping)
    let localeId = WorkflowState.get('locale_id');
    if (!localeId) {
      // Generate a default locale UUID and persist it
      localeId = this.generateUUID();
      WorkflowState.set('locale_id', localeId);
    }
    formData.append('locale_id', localeId);
    
    // Support both single asset and multiple assets
    if (typeof assetId === 'string' && assetId.includes(',')) {
      // Multiple asset IDs
      formData.append('asset_ids', assetId);
    } else {
      // Single asset ID - convert to comma-separated format
      formData.append('asset_ids', assetId);
    }
    
    const response = await fetch(`${API_BASE}/selections/save`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Save failed: ${response.statusText} - ${errorText}`);
    }
    
    return await response.json();
  },
  
  // Helper to generate UUID v4
  generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  },
  
  // List all saved selections
  async listSelections() {
    const response = await fetch(`${API_BASE}/selections`);
    
    if (!response.ok) {
      throw new Error(`Failed to load selections: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.selections || [];
  },

  // List all saved sites from siteData collection
  async listSites(localeId = null) {
    const url = localeId 
      ? `${API_BASE}/sites?locale_id=${localeId}`
      : `${API_BASE}/sites`;
    
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`Failed to load sites: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.sites || [];
  },
  
  // Get selection by ID
  async getSelection(selectionId) {
    const response = await fetch(`${API_BASE}/selections/${selectionId}`);
    
    if (!response.ok) {
      throw new Error(`Failed to load selection: ${response.statusText}`);
    }
    
    return await response.json();
  },
  
  // Export selection as CZML
  async exportCZML(selectionId, visualisationType, colourmapName, valueField) {
    const formData = new FormData();
    formData.append('visualisation_type', visualisationType);
    formData.append('colourmap_name', colourmapName);
    formData.append('value_field', valueField);
    
    const response = await fetch(`${API_BASE}/selections/${selectionId}/export-czml`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`);
    }
    
    return await response.json();
  },
  
  // Export selection as CZML with full options (including polygon parameters)
  async exportCZMLWithOptions(selectionId, options) {
    const formData = new FormData();
    
    // Add all options to form data
    for (const [key, value] of Object.entries(options)) {
      formData.append(key, value);
    }
    
    const response = await fetch(`${API_BASE}/selections/${selectionId}/export-czml`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`);
    }
    
    return await response.json();
  },
  
  // Get list of available colourmaps
  async listColourmaps(category = null) {
    let url = `${API_BASE}/colourmaps`;
    if (category) {
      url += `?category=${encodeURIComponent(category)}`;
    }
    
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch colourmaps: ${response.statusText}`);
    }
    
    return await response.json();
  },

  // Export site as CZML (from siteData collection)
  async exportSiteCZML(siteId, visualisationType, colourmapName, valueField) {
    const formData = new FormData();
    formData.append('visualisation_type', visualisationType);
    formData.append('colourmap_name', colourmapName);
    formData.append('value_field', valueField);
    
    const response = await fetch(`${API_BASE}/sites/${siteId}/export-czml`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`);
    }
    
    return await response.json();
  }
};

// UI Helper Functions
const UI = {
  // Show status message
  showStatus(message, isError = false) {
    const statusEl = document.getElementById('statusMessage');
    if (statusEl) {
      statusEl.textContent = message;
      statusEl.className = `status-message visible ${isError ? 'error' : 'info'}`;
      
      // Auto-hide success messages after 5 seconds
      if (!isError) {
        setTimeout(() => {
          statusEl.classList.remove('visible');
        }, 5000);
      }
    }
  },
  
  // Show success message
  showSuccess(message) {
    const statusEl = document.getElementById('statusMessage');
    if (statusEl) {
      statusEl.textContent = message;
      statusEl.className = 'status-message visible success';
      
      setTimeout(() => {
        statusEl.classList.remove('visible');
      }, 5000);
    }
  },
  
  // Show results in JSON panel
  showResults(title, data) {
    const resultsEl = document.getElementById('resultsPanel');
    if (resultsEl) {
      const titleEl = resultsEl.querySelector('h4');
      const preEl = resultsEl.querySelector('pre');
      
      if (titleEl) titleEl.textContent = title;
      if (preEl) preEl.textContent = JSON.stringify(data, null, 2);
      
      resultsEl.classList.add('visible');
    }
  },
  
  // Hide results panel
  hideResults() {
    const resultsEl = document.getElementById('resultsPanel');
    if (resultsEl) {
      resultsEl.classList.remove('visible');
    }
  },
  
  // Update step progress indicator
  updateStepProgress(currentStep) {
    const steps = document.querySelectorAll('.step-item');
    const completedSteps = WorkflowState.get('completed_steps') || [];
    
    steps.forEach((stepEl, index) => {
      const stepNum = index + 1;
      stepEl.classList.remove('current', 'completed');
      
      if (stepNum === currentStep) {
        stepEl.classList.add('current');
      } else if (completedSteps.includes(stepNum)) {
        stepEl.classList.add('completed');
      }
    });
  },
  
  // Navigate to step
  goToStep(stepNumber) {
    window.location.href = `step${stepNumber}_${this.getStepSlug(stepNumber)}.html`;
  },
  
  // Navigate to index
  goToIndex() {
    window.location.href = 'index.html';
  },
  
  // Get step URL slug
  getStepSlug(stepNumber) {
    const slugs = ['upload', 'tiles', 'draw', 'save', 'export'];
    return slugs[stepNumber - 1] || '';
  }
};

// Cesium Helper Functions
const CesiumHelper = {
  // Initialise Cesium viewer
  initViewer(containerId) {
    // Use centralised token from config
    if (window.CESIUM_ION_TOKEN || CESIUM_ION_TOKEN) {
      Cesium.Ion.defaultAccessToken = window.CESIUM_ION_TOKEN || CESIUM_ION_TOKEN;
    }
    
    const viewer = new Cesium.Viewer(containerId, {
      baseLayerPicker: true,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: true,
      vrButton: false,
      imageryProvider: new Cesium.IonImageryProvider({ assetId: 3845 })
    });
    
    // Set initial camera position (Heart of Borneo - Segama River region)
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(117.8, 5.2, 200000),
      orientation: {
        heading: 0.0,
        pitch: Cesium.Math.toRadians(-45),
        roll: 0.0
      }
    });
    
    return viewer;
  },
  
  // Add tile layer
  addTileLayer(viewer, assetId, colourmapName = 'viridis') {
    const tileUrl = `${API_BASE}/tiles/${assetId}/{z}/{x}/{y}.png?colormap_name=${colourmapName}`;
    
    const layer = viewer.imageryLayers.addImageryProvider(
      new Cesium.UrlTemplateImageryProvider({
        url: tileUrl,
        maximumLevel: 14,
        rectangle: Cesium.Rectangle.fromDegrees(116.5, 4.0, 119.5, 6.5)
      })
    );
    
    return layer;
  },
  
  // Enable polygon drawing
  enablePolygonDrawing(viewer, onComplete) {
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    const positions = [];
    let currentPolygon = null;
    
    handler.setInputAction((click) => {
      const cartesian = viewer.camera.pickEllipsoid(click.position, viewer.scene.globe.ellipsoid);
      if (cartesian) {
        positions.push(cartesian);
        
        // Create or update polygon
        if (!currentPolygon) {
          currentPolygon = viewer.entities.add({
            polygon: {
              hierarchy: new Cesium.CallbackProperty(() => new Cesium.PolygonHierarchy(positions), false),
              material: Cesium.Color.RED.withAlpha(0.3),
              outline: true,
              outlineColor: Cesium.Color.RED,
              outlineWidth: 2
            }
          });
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    
    handler.setInputAction(() => {
      if (positions.length >= 3) {
        handler.destroy();
        
        // Convert to GeoJSON
        const coordinates = positions.map(pos => {
          const cartographic = Cesium.Cartographic.fromCartesian(pos);
          return [
            Cesium.Math.toDegrees(cartographic.longitude),
            Cesium.Math.toDegrees(cartographic.latitude)
          ];
        });
        coordinates.push(coordinates[0]); // Close polygon
        
        const geojson = {
          type: "Polygon",
          coordinates: [coordinates]
        };
        
        if (onComplete) {
          onComplete(geojson);
        }
      }
    }, Cesium.ScreenSpaceEventType.RIGHT_CLICK);
    
    return handler;
  },
  
  // Load CZML
  loadCZML(viewer, czmlData) {
    return viewer.dataSources.add(Cesium.CzmlDataSource.load(czmlData));
  }
};

// Utility Functions
const Utils = {
  // Format date
  formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-GB', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  },
  
  // Format file size
  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  },
  
  // Generate unique ID
  generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
  }
};

// Export for use in individual step pages
window.WorkflowState = WorkflowState;
window.API = API;
window.UI = UI;
window.CesiumHelper = CesiumHelper;
window.Utils = Utils;
window.API_BASE = API_BASE;
window.CESIUM_ION_TOKEN = CESIUM_ION_TOKEN;
window.loadConfig = loadConfig;
