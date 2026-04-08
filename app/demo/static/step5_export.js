/* Step 5 Export - JavaScript Logic */

let czmlData = null;
let viewer = null;
let selectedSelection = null;

UI.updateStepProgress(5);
loadSelections();
loadColourmaps();

// Pre-fill ownership from Step 1
const _cachedUserId = WorkflowState.get('user_id');
const _cachedProjectId = WorkflowState.get('project_id');
if (_cachedUserId) document.getElementById('userId').value = _cachedUserId;
if (_cachedProjectId) document.getElementById('projectId').value = _cachedProjectId;

/**
 * Load available colourmaps from API and populate dropdown.
 * Groups colourmaps by category with optgroups.
 */
async function loadColourmaps() {
  const colourmapSelect = document.getElementById('colourmapName');
  
  try {
    // Fetch colourmaps organised by category
    const response = await fetch(`${API_BASE}/colourmaps/categories`);
    
    if (!response.ok) {
      console.warn('Failed to load colourmaps, using defaults');
      return; // Keep the hardcoded fallback options
    }
    
    const data = await response.json();
    const categories = data.categories;
    
    // Build grouped options HTML
    let html = '';
    
    // Define preferred order and display names
    const categoryOrder = [
      ['perceptually_uniform', 'Perceptually Uniform'],
      ['sequential', 'Sequential'],
      ['diverging', 'Diverging'],
      ['cyclic', 'Cyclic'],
      ['qualitative', 'Qualitative'],
      ['miscellaneous', 'Miscellaneous']
    ];
    
    for (const [key, displayName] of categoryOrder) {
      if (categories[key] && categories[key].length > 0) {
        html += `<optgroup label="${displayName}">`;
        
        for (const cmap of categories[key]) {
          // Mark viridis as selected (default)
          const selected = cmap === 'viridis' ? ' selected' : '';
          html += `<option value="${cmap}"${selected}>${cmap}</option>`;
        }
        
        html += '</optgroup>';
      }
    }
    
    colourmapSelect.innerHTML = html;
    console.log(`Loaded ${Object.values(categories).flat().length} colourmaps`);
    
  } catch (error) {
    console.warn('Error loading colourmaps:', error);
    // Keep the hardcoded fallback options
  }
}

// Listen for visualisation type change to show/hide type-specific options
document.getElementById('visualisationType').addEventListener('change', function() {
  const polygonOptionsGroup = document.getElementById('polygonOptionsGroup');
  const barOptionsGroup = document.getElementById('barOptionsGroup');
  if (this.value === 'polygon') {
    polygonOptionsGroup.style.display = 'block';
    barOptionsGroup.style.display = 'none';
  } else {
    polygonOptionsGroup.style.display = 'none';
    barOptionsGroup.style.display = 'block';
  }
});

// Show polygon options by default (polygon is now the default type)
document.getElementById('polygonOptionsGroup').style.display = 'block';
document.getElementById('barOptionsGroup').style.display = 'none';

async function loadSelections() {
  try {
    UI.showStatus('Loading saved selections...');
    const selections = await API.listSelections();
    
    if (!selections || selections.length === 0) {
      document.getElementById('selectionsList').innerHTML = `
        <p style="text-align: center; color: #94a3b8; padding: 20px;">
          No saved selections found. Please complete Step 4 to save a selection first.
        </p>
      `;
      UI.showStatus('No selections available', true);
      return;
    }

    // Display selections as clickable cards
    const html = selections.map(sel => {
      const statsCount = sel.statistics_count || 0;
      const createdDate = new Date(sel.created_at).toLocaleDateString();
      return `
      <div class="selection-card" onclick="selectSelection('${sel.id}')" data-id="${sel.id}">
        <div style="display: flex; justify-content: space-between; align-items: start;">
          <div style="flex: 1;">
            <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #e2e8f0;">${sel.title}</h4>
            <p style="margin: 0 0 8px 0; font-size: 12px; color: #94a3b8; line-height: 1.5;">
              ${sel.description || 'No description'}
            </p>
            <div style="font-size: 11px; color: #64748b; font-family: monospace;">
              <div>Selection ID: ${sel.id}</div>
              <div>Created: ${createdDate}</div>
              <div>Statistics: ${statsCount} index(es)</div>
              ${sel.tags && sel.tags.length > 0 ? `<div>Tags: ${sel.tags.join(', ')}</div>` : ''}
            </div>
          </div>
          <div style="min-width: 80px; text-align: right;">
            <span class="selection-badge">Select →</span>
          </div>
        </div>
      </div>
    `;
    }).join('');

    document.getElementById('selectionsList').innerHTML = html;
    UI.showSuccess(`Loaded ${selections.length} selection(s)`);

    // Store selections for reference
    window.allSelections = selections;

    // Auto-select if coming from step 4
    const savedFromStep4 = WorkflowState.get('saved_selection');
    if (savedFromStep4 && (savedFromStep4._id || savedFromStep4.id)) {
      selectSelection(savedFromStep4._id || savedFromStep4.id);
    }

  } catch (error) {
    document.getElementById('selectionsList').innerHTML = `
      <p style="text-align: center; color: #f87171; padding: 20px;">
        Failed to load selections: ${error.message}
      </p>
    `;
    UI.showStatus(`Failed to load selections: ${error.message}`, true);
    console.error('Load error:', error);
  }
}

async function selectSelection(selectionId) {
  // Fetch full selection details (list endpoint returns summary only)
  try {
    UI.showStatus('Loading selection details...');
    const fullSelection = await API.getSelection(selectionId);
    
    selectedSelection = fullSelection;
    
    // Highlight selected card
    document.querySelectorAll('.selection-card').forEach(card => {
      card.classList.remove('selected');
    });
    document.querySelector(`[data-id="${selectionId}"]`).classList.add('selected');

    // Show export panel
    document.getElementById('exportPanel').style.display = 'block';
    document.getElementById('selectedName').textContent = fullSelection.title;
    document.getElementById('selectedId').textContent = fullSelection.id || fullSelection._id;

    // Populate index types from selection polygons
    populateIndexTypes(fullSelection);

    UI.showSuccess(`Selected: ${fullSelection.title}`);
  } catch (error) {
    UI.showStatus(`Failed to load selection: ${error.message}`, true);
    console.error('Select error:', error);
  }
}

/**
 * Extract unique index types from selection's polygon statistics
 * and populate the indexType dropdown.
 */
function populateIndexTypes(selection) {
  const indexTypeSelect = document.getElementById('indexType');
  
  // Extract unique index types from all polygons' statistics
  const indexTypes = new Set();
  if (selection.polygons && Array.isArray(selection.polygons)) {
    for (const polygon of selection.polygons) {
      if (polygon.statistics && Array.isArray(polygon.statistics)) {
        for (const stat of polygon.statistics) {
          if (stat.index_type) {
            indexTypes.add(stat.index_type);
          }
        }
      }
    }
  }

  // Build options HTML
  if (indexTypes.size === 0) {
    indexTypeSelect.innerHTML = '<option value="">-- No index types found --</option>';
    return;
  }

  const sortedTypes = Array.from(indexTypes).sort();
  indexTypeSelect.innerHTML = sortedTypes.map(type => 
    `<option value="${type}">${type.toUpperCase()}</option>`
  ).join('');
  
  console.log(`Populated ${indexTypes.size} index type(s):`, sortedTypes);
}

async function exportCZML() {
  if (!selectedSelection) {
    UI.showStatus('Please select a selection first', true);
    return;
  }

  const indexType = document.getElementById('indexType').value;
  if (!indexType) {
    UI.showStatus('Please select a climate index type', true);
    return;
  }

  const visualisationType = document.getElementById('visualisationType').value;
  const colourmapName = document.getElementById('colourmapName').value;
  const valueField = document.getElementById('valueField').value;
  const interpolationMode = document.getElementById('interpolationMode').value;
  
  // Build export options
  const exportOptions = {
    index_type: indexType,
    visualisation_type: visualisationType,
    colourmap_name: colourmapName,
    value_field: valueField,
    interpolation_mode: interpolationMode,
    save_to_db: true
  };

  // Optional ownership fields
  const czmlId = document.getElementById('czmlId')?.value?.trim();
  const userId = document.getElementById('userId')?.value?.trim();
  const projectId = document.getElementById('projectId')?.value?.trim();
  if (czmlId) exportOptions.czml_id = czmlId;
  if (userId) exportOptions.user_id = userId;
  if (projectId) exportOptions.project_id = projectId;
  
  // Add type-specific options
  if (visualisationType === 'polygon') {
    const heightMultiplier = document.getElementById('polygonHeightMultiplier');
    const fillOpacity = document.getElementById('polygonFillOpacity');
    if (heightMultiplier) {
      exportOptions.polygon_height_multiplier = parseFloat(heightMultiplier.value) || 1000;
    }
    if (fillOpacity) {
      exportOptions.polygon_fill_opacity = parseFloat(fillOpacity.value) || 0.7;
    }
  } else if (visualisationType === 'bar') {
    const barHeight = document.getElementById('barHeightMultiplier');
    const barRadius = document.getElementById('barRadiusMultiplier');
    const barMinRadius = document.getElementById('barMinimumRadius');
    if (barHeight) {
      exportOptions.bar_height_multiplier = parseFloat(barHeight.value) || 10000;
    }
    if (barRadius) {
      exportOptions.bar_radius_multiplier = parseFloat(barRadius.value) || 10;
    }
    if (barMinRadius) {
      exportOptions.bar_minimum_radius = parseFloat(barMinRadius.value) || 500;
    }
  }

  try {
    UI.showStatus(`Exporting CZML for ${indexType.toUpperCase()} (${interpolationMode})...`);

    const selectionId = selectedSelection.id || selectedSelection._id;
    const response = await API.exportCZMLWithOptions(selectionId, exportOptions);

    // New response format includes czml_id and czml_document
    czmlData = response.czml_document || response;
    
    if (!czmlData || !Array.isArray(czmlData)) {
      throw new Error('Invalid CZML response format');
    }
    
    WorkflowState.set('czml_data', czmlData);
    WorkflowState.set('czml_id', response.czml_id);
    WorkflowState.completeStep(5);

    document.getElementById('czmlDocId').textContent = response.czml_id || czmlData[0]?.id || 'Unknown';
    document.getElementById('czmlPackets').textContent = response.packet_count || czmlData.length;
    document.getElementById('exportSuccess').style.display = 'block';
    document.getElementById('loadBtn').disabled = false;

    const savedMsg = response.replaced ? '(replaced existing)' : '(saved new)';
    UI.showSuccess(`✓ CZML document exported successfully! ${savedMsg}`);
    UI.showResults('CZML Document', czmlData);

  } catch (error) {
    UI.showStatus(`Export failed: ${error.message}`, true);
    console.error('Export error:', error);
  }
}

function loadCZMLInViewer() {
  if (!czmlData) {
    UI.showStatus('Please export CZML first', true);
    return;
  }

  const container = document.getElementById('cesiumContainer');
  container.style.display = 'block';

  if (!viewer) {
    // Use centralised token from config (loaded by demo3-common.js)
    if (window.CESIUM_ION_TOKEN) {
      Cesium.Ion.defaultAccessToken = window.CESIUM_ION_TOKEN;
    }
    
    viewer = new Cesium.Viewer('cesiumContainer', {
      animation: true,
      timeline: true,
      baseLayerPicker: true,
      geocoder: false,
      homeButton: true,
      sceneModePicker: false,
      navigationHelpButton: false,
      terrainProvider: new Cesium.EllipsoidTerrainProvider()
    });
    
    // Ensure base layer is set to OpenStreetMap
    viewer.imageryLayers.removeAll();
    viewer.imageryLayers.addImageryProvider(new Cesium.OpenStreetMapImageryProvider());

    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(117.8, 5.2, 200000),
      orientation: { heading: 0.0, pitch: Cesium.Math.toRadians(-45), roll: 0.0 }
    });
  }

  viewer.dataSources.add(Cesium.CzmlDataSource.load(czmlData))
    .then(() => {
      viewer.zoomTo(viewer.dataSources.get(viewer.dataSources.length - 1));
      UI.showSuccess('✓ CZML loaded in Cesium viewer!');
    })
    .catch(error => {
      UI.showStatus(`Failed to load CZML: ${error.message}`, true);
    });
}

function downloadCZML() {
  if (!czmlData) return;

  const blob = new Blob([JSON.stringify(czmlData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `site_${selectedSelection.site_id}_${Date.now()}.czml`;
  a.click();
  URL.revokeObjectURL(url);
  UI.showSuccess('CZML file downloaded!');
}

function completeWorkflow() {
  UI.showSuccess('🎉 Workflow completed successfully!');
  setTimeout(() => UI.goToIndex(), 2000);
}
