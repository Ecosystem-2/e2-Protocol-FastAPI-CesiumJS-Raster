/* Step 5 Export - JavaScript Logic */

let czmlData = null;
let viewer = null;
let climateTileLayer = null;
let czmlDataSource = null;
let selectedSelection = null;
let lastExportOptions = null;  // Cached options from preview, reused on save

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
function updateVisualisationOptions() {
  const visualisationType = document.getElementById('visualisationType').value;
  const polygonOptionsGroup = document.getElementById('polygonOptionsGroup');
  const polygonOptionsGrid = document.getElementById('polygonOptionsGrid');
  const polygonHeightOption = document.getElementById('polygonHeightOption');
  const barOptionsGroup = document.getElementById('barOptionsGroup');
  const circleOptionsGroup = document.getElementById('circleOptionsGroup');
  const isPolygonMode = visualisationType === 'polygon' || visualisationType === 'polygon2d';

  if (isPolygonMode) {
    polygonOptionsGroup.style.display = 'block';
    barOptionsGroup.style.display = 'none';
    if (circleOptionsGroup) circleOptionsGroup.style.display = 'none';
    if (polygonHeightOption) {
      polygonHeightOption.style.display = visualisationType === 'polygon' ? 'block' : 'none';
    }
    if (polygonOptionsGrid) {
      polygonOptionsGrid.style.gridTemplateColumns = visualisationType === 'polygon' ? '1fr 1fr' : '1fr';
    }
  } else if (visualisationType === 'circle2d') {
    polygonOptionsGroup.style.display = 'none';
    barOptionsGroup.style.display = 'none';
    if (circleOptionsGroup) circleOptionsGroup.style.display = 'block';
  } else {
    polygonOptionsGroup.style.display = 'none';
    barOptionsGroup.style.display = 'block';
    if (circleOptionsGroup) circleOptionsGroup.style.display = 'none';
  }
}

document.getElementById('visualisationType').addEventListener('change', updateVisualisationOptions);

// Show polygon options by default (polygon is now the default type)
updateVisualisationOptions();

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
      const createdDate = new Date(sel.createdAt || sel.created_at).toLocaleDateString();
      return `
      <div class="selection-card" onclick="selectSelection('${sel._id || sel.id}')" data-id="${sel._id || sel.id}">
        <div style="display: flex; justify-content: space-between; align-items: start;">
          <div style="flex: 1;">
            <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #e2e8f0;">${sel.title}</h4>
            <p style="margin: 0 0 8px 0; font-size: 12px; color: #94a3b8; line-height: 1.5;">
              ${sel.description || 'No description'}
            </p>
            <div style="font-size: 11px; color: #64748b; font-family: monospace;">
              <div>Selection ID: ${sel._id || sel.id}</div>
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
    if (savedFromStep4 && (savedFromStep4._id || savedFromStep4.id || savedFromStep4.selectionID)) {
      selectSelection(savedFromStep4._id || savedFromStep4.id || savedFromStep4.selectionID);
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
    document.getElementById('selectedId').textContent = fullSelection._id || fullSelection.id;

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
          if (stat.indexType) {
            indexTypes.add(stat.indexType);
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

/**
 * Collect current form values into an export options object.
 * @param {boolean} saveToDb - Whether to save to MongoDB.
 */
function _buildExportOptions(saveToDb) {
  const indexType = document.getElementById('indexType').value;
  const visualisationType = document.getElementById('visualisationType').value;
  const colourmapName = document.getElementById('colourmapName').value;
  const valueField = document.getElementById('valueField').value;
  const interpolationMode = document.getElementById('interpolationMode').value;

  const options = {
    indexType,
    visualisationType,
    colourmapName,
    valueField,
    interpolationMode,
    saveToDb
  };

  // Optional ownership fields (only relevant when saving)
  const czmlId = document.getElementById('czmlId')?.value?.trim();
  const userId = document.getElementById('userId')?.value?.trim();
  const projectId = document.getElementById('projectId')?.value?.trim();
  if (czmlId) options.czmlID = czmlId;
  if (userId) options.userID = userId;
  if (projectId) options.projectID = projectId;

  // Type-specific options
  if (visualisationType === 'polygon' || visualisationType === 'polygon2d') {
    const heightMultiplier = document.getElementById('polygonHeightMultiplier');
    const fillOpacity = document.getElementById('polygonFillOpacity');
    if (visualisationType === 'polygon' && heightMultiplier) {
      options.polygonHeightMultiplier = parseFloat(heightMultiplier.value) || 1000;
    }
    if (fillOpacity) options.polygonFillOpacity = parseFloat(fillOpacity.value) || 0.7;
  } else if (visualisationType === 'circle2d') {
    const circleRadius = document.getElementById('circleRadius');
    const circleFillOpacity = document.getElementById('circleFillOpacity');
    if (circleRadius) options.circleRadius = parseFloat(circleRadius.value) || 1000;
    if (circleFillOpacity) options.polygonFillOpacity = parseFloat(circleFillOpacity.value) || 0.7;
  } else if (visualisationType === 'bar') {
    const barHeight = document.getElementById('barHeightMultiplier');
    const barRadius = document.getElementById('barRadiusMultiplier');
    const barMinRadius = document.getElementById('barMinimumRadius');
    if (barHeight) options.barHeightMultiplier = parseFloat(barHeight.value) || 10000;
    if (barRadius) options.barRadiusMultiplier = parseFloat(barRadius.value) || 10;
    if (barMinRadius) options.barMinimumRadius = parseFloat(barMinRadius.value) || 500;
  }

  return options;
}

function _escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function _periodLabelFromPacket(packet) {
  if (!packet?.availability || typeof packet.availability !== 'string') {
    return '';
  }

  const [start, end] = packet.availability.split('/');
  if (!start) return '';

  const startYear = start.slice(0, 4);
  const endYear = end ? end.slice(0, 4) : '';
  if (startYear && endYear && startYear !== endYear) {
    return `${startYear}-${endYear}`;
  }
  return start.slice(0, 10);
}

function _polygonIndexFromPacket(packet) {
  const id = String(packet?.id || '');
  const match = id.match(/(?:^|_)poly(\d+)(?:_|$)/i);
  return match ? Number.parseInt(match[1], 10) : null;
}

function applyPolygonTitlesToCZML(czml, selection) {
  if (!Array.isArray(czml) || !selection?.polygons) {
    return czml;
  }

  return czml.map(packet => {
    const polyIndex = _polygonIndexFromPacket(packet);
    if (polyIndex === null || !selection.polygons[polyIndex]) {
      return packet;
    }

    const polygonTitle = (selection.polygons[polyIndex].title || '').trim() || `Polygon ${polyIndex + 1}`;
    const periodLabel = _periodLabelFromPacket(packet);
    const displayName = periodLabel ? `${polygonTitle} (${periodLabel})` : polygonTitle;
    const patched = { ...packet, name: displayName };

    if (typeof patched.description === 'string') {
      const escapedTitle = _escapeHtml(polygonTitle);
      if (/<h3\b[^>]*>.*?<\/h3>/is.test(patched.description)) {
        patched.description = patched.description.replace(
          /<h3\b([^>]*)>.*?<\/h3>/is,
          `<h3$1>${escapedTitle}</h3>`
        );
      }
    }

    return patched;
  });
}

/**
 * Preview CZML without saving to the database.
 * Populates czmlData and enables the "Save" button.
 */
async function previewCZML() {
  if (!selectedSelection) {
    UI.showStatus('Please select a selection first', true);
    return;
  }

  const indexType = document.getElementById('indexType').value;
  if (!indexType) {
    UI.showStatus('Please select a climate index type', true);
    return;
  }

  const exportOptions = _buildExportOptions(false);
  lastExportOptions = exportOptions;  // Cache for save step

  try {
    UI.showStatus(`Generating preview for ${indexType.toUpperCase()}...`);

    const selectionId = selectedSelection.id || selectedSelection._id;
    const response = await API.exportCZMLWithOptions(selectionId, exportOptions);

    czmlData = response.czmlDocument || response.czml_document || response;
    if (!czmlData || !Array.isArray(czmlData)) {
      throw new Error('Invalid CZML response format');
    }
    czmlData = applyPolygonTitlesToCZML(czmlData, selectedSelection);

    // Show preview results and enable action buttons
    document.getElementById('czmlDocId').textContent = '(not saved yet)';
    document.getElementById('czmlPackets').textContent = response.packetCount || response.packet_count || czmlData.length;
    document.getElementById('exportSuccess').style.display = 'block';
    document.getElementById('exportSuccessLabel').textContent = '✓ CZML Preview Ready';
    document.getElementById('saveBtn').disabled = false;
    document.getElementById('loadBtn').disabled = false;

    UI.showSuccess(`✓ Preview generated (${czmlData.length} packets). Review below, then click Save.`);
    UI.showResults('CZML Preview (not saved)', czmlData);

  } catch (error) {
    UI.showStatus(`Preview failed: ${error.message}`, true);
    console.error('Preview error:', error);
  }
}

/**
 * Save the previously previewed CZML to MongoDB.
 * Reuses the cached export options so the same document is persisted.
 */
async function saveCZML() {
  if (!czmlData || !lastExportOptions) {
    UI.showStatus('Please preview CZML first', true);
    return;
  }

  const saveOptions = { ...lastExportOptions, saveToDb: true };

  try {
    UI.showStatus('Saving CZML to database...');

    const selectionId = selectedSelection.id || selectedSelection._id;
    const response = await API.exportCZMLWithOptions(selectionId, saveOptions);

    czmlData = response.czmlDocument || response.czml_document || czmlData;
    czmlData = applyPolygonTitlesToCZML(czmlData, selectedSelection);

    WorkflowState.set('czml_data', czmlData);
    WorkflowState.set('czml_id', response.czmlID || response.czml_id);
    WorkflowState.completeStep(5);

    document.getElementById('czmlDocId').textContent = response.czmlID || response.czml_id || czmlData[0]?.id || 'Unknown';
    document.getElementById('czmlPackets').textContent = response.packetCount || response.packet_count || czmlData.length;
    document.getElementById('exportSuccessLabel').textContent = '✓ CZML Saved';
    document.getElementById('saveBtn').disabled = true;  // Prevent double-save

    const savedMsg = response.replaced ? '(replaced existing)' : '(saved new)';
    UI.showSuccess(`✓ CZML saved to database! ${savedMsg}`);
    UI.showResults('CZML Document (saved)', czmlData);

  } catch (error) {
    UI.showStatus(`Save failed: ${error.message}`, true);
    console.error('Save error:', error);
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
      sceneMode: Cesium.SceneMode.SCENE3D,
      scene3DOnly: true,
      geocoder: false,
      homeButton: true,
      sceneModePicker: false,
      navigationHelpButton: false,
      terrainProvider: new Cesium.EllipsoidTerrainProvider()
    });
    viewer.scene.screenSpaceCameraController.enableRotate = true;
    viewer.scene.screenSpaceCameraController.enableTilt = true;
    
    // Ensure base layer is set to OpenStreetMap
    viewer.imageryLayers.removeAll();
    viewer.imageryLayers.addImageryProvider(new Cesium.OpenStreetMapImageryProvider());

    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(117.8, 5.2, 200000),
      orientation: { heading: 0.0, pitch: Cesium.Math.toRadians(-45), roll: 0.0 }
    });
  }

  restoreClimateTileLayer();

  if (czmlDataSource) {
    viewer.dataSources.remove(czmlDataSource, true);
    czmlDataSource = null;
  }

  viewer.dataSources.add(Cesium.CzmlDataSource.load(czmlData))
    .then((dataSource) => {
      czmlDataSource = dataSource;
      viewer.flyTo(dataSource, {
        duration: 1.5,
        offset: new Cesium.HeadingPitchRange(
          Cesium.Math.toRadians(0),
          Cesium.Math.toRadians(-45),
          120000
        )
      });
      UI.showSuccess('✓ CZML loaded in Cesium viewer!');
    })
    .catch(error => {
      UI.showStatus(`Failed to load CZML: ${error.message}`, true);
    });
}

function _normaliseTileBounds(rect) {
  if (!rect) {
    return { left: 116.5, bottom: 4.0, right: 119.5, top: 6.5 };
  }

  // Step 2 stores degrees; older in-memory Cesium rectangles may carry radians.
  if (typeof rect.left === 'number') {
    return rect;
  }

  if (
    typeof rect.west === 'number' &&
    typeof rect.south === 'number' &&
    typeof rect.east === 'number' &&
    typeof rect.north === 'number'
  ) {
    const looksLikeRadians = Math.abs(rect.west) <= Math.PI && Math.abs(rect.east) <= Math.PI;
    const factor = looksLikeRadians ? 180 / Math.PI : 1;
    return {
      left: rect.west * factor,
      bottom: rect.south * factor,
      right: rect.east * factor,
      top: rect.north * factor
    };
  }

  return { left: 116.5, bottom: 4.0, right: 119.5, top: 6.5 };
}

function restoreClimateTileLayer() {
  const currentSlice = WorkflowState.get('current_slice');
  if (!viewer || !currentSlice || !currentSlice.assetId) {
    return;
  }

  if (climateTileLayer) {
    viewer.imageryLayers.remove(climateTileLayer, false);
    climateTileLayer = null;
  }

  const colourmap = currentSlice.colourmap || 'viridis';
  const scaleMin = currentSlice.scaleMin ?? 0;
  const scaleMax = currentSlice.scaleMax ?? 1;
  const params = `colormap_name=${encodeURIComponent(colourmap)}&scale_min=${scaleMin}&scale_max=${scaleMax}`;
  const tileUrl = `${API_BASE}/tiles/${currentSlice.assetId}/{z}/{x}/{y}.png?${params}`;
  const bounds = _normaliseTileBounds(currentSlice.rect);
  const rectangle = Cesium.Rectangle.fromDegrees(bounds.left, bounds.bottom, bounds.right, bounds.top);

  climateTileLayer = viewer.imageryLayers.addImageryProvider(
    new Cesium.UrlTemplateImageryProvider({
      url: tileUrl,
      maximumLevel: 14,
      rectangle,
      credit: 'Climate tiles'
    })
  );
  climateTileLayer.alpha = 0.85;
  climateTileLayer.show = true;

  viewer.camera.flyTo({ destination: rectangle, duration: 1.0 });
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
