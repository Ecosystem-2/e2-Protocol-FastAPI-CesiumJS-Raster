/* Step 5 Export - JavaScript Logic */

let czmlData = null;
let viewer = null;
let selectedSelection = null;

UI.updateStepProgress(5);
loadSelections();

async function loadSelections() {
  try {
    UI.showStatus('Loading saved sites...');
    const sites = await API.listSites();
    
    if (!sites || sites.length === 0) {
      document.getElementById('selectionsList').innerHTML = `
        <p style="text-align: center; color: #94a3b8; padding: 20px;">
          No saved sites found. Please complete Step 4 to save a selection first.
        </p>
      `;
      UI.showStatus('No sites available', true);
      return;
    }

    // Display sites as clickable cards
    const html = sites.map(site => {
      const statsCount = site.location?.statistics?.length || 0;
      return `
      <div class="selection-card" onclick="selectSelection('${site.site_id}')" data-id="${site.site_id}">
        <div style="display: flex; justify-content: space-between; align-items: start;">
          <div style="flex: 1;">
            <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #e2e8f0;">${site.title}</h4>
            <p style="margin: 0 0 8px 0; font-size: 12px; color: #94a3b8; line-height: 1.5;">
              ${site.desc || 'No description'}
            </p>
            <div style="font-size: 11px; color: #64748b; font-family: monospace;">
              <div>Site ID: ${site.site_id}</div>
              <div>Created: ${new Date(site.creation_date_time).toLocaleDateString()}</div>
              <div>Statistics: ${statsCount} index(es)</div>
              ${site.tags && site.tags.length > 0 ? `<div>Tags: ${site.tags.join(', ')}</div>` : ''}
              ${site.category && site.category.length > 0 ? `<div>Category: ${site.category.join(', ')}</div>` : ''}
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
    UI.showSuccess(`Loaded ${sites.length} site(s)`);

    // Store sites for reference
    window.allSelections = sites;

    // Auto-select if coming from step 4
    const savedFromStep4 = WorkflowState.get('saved_selection');
    if (savedFromStep4 && savedFromStep4.siteID) {
      selectSelection(savedFromStep4.siteID);
    }

  } catch (error) {
    document.getElementById('selectionsList').innerHTML = `
      <p style="text-align: center; color: #f87171; padding: 20px;">
        Failed to load sites: ${error.message}
      </p>
    `;
    UI.showStatus(`Failed to load sites: ${error.message}`, true);
    console.error('Load error:', error);
  }
}

function selectSelection(siteId) {
  const site = window.allSelections.find(s => s.site_id === siteId);
  if (!site) return;

  selectedSelection = site;

  // Highlight selected card
  document.querySelectorAll('.selection-card').forEach(card => {
    card.classList.remove('selected');
  });
  document.querySelector(`[data-id="${siteId}"]`).classList.add('selected');

  // Show export panel
  document.getElementById('exportPanel').style.display = 'block';
  document.getElementById('selectedName').textContent = site.title;
  document.getElementById('selectedId').textContent = site.site_id;

  UI.showSuccess(`Selected: ${site.title}`);
}

async function exportCZML() {
  if (!selectedSelection) {
    UI.showStatus('Please select a selection first', true);
    return;
  }

  const visualisationType = document.getElementById('visualisationType').value;
  const colourmapName = document.getElementById('colourmapName').value;
  const valueField = document.getElementById('valueField').value;

  try {
    UI.showStatus('Exporting CZML document...');

    const response = await API.exportSiteCZML(selectedSelection.site_id, visualisationType, colourmapName, valueField);

    // Response is the CZML array directly, not wrapped
    czmlData = Array.isArray(response) ? response : response.czml;
    
    if (!czmlData || !Array.isArray(czmlData)) {
      throw new Error('Invalid CZML response format');
    }
    
    WorkflowState.set('czml_data', czmlData);
    WorkflowState.completeStep(5);

    document.getElementById('czmlDocId').textContent = czmlData[0]?.id || 'Unknown';
    document.getElementById('czmlPackets').textContent = czmlData.length;
    document.getElementById('exportSuccess').style.display = 'block';
    document.getElementById('loadBtn').disabled = false;

    UI.showSuccess('✓ CZML document exported successfully!');
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
    Cesium.Ion.defaultAccessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJlYWE1OWUxNy1mMWZiLTQzYjYtYTQ0OS1kMWFjYmFkNjc5YzYiLCJpZCI6NTc3MzMsImlhdCI6MTYyNzg0NTE4Mn0.XcKpgANiY19MC4bdFUXMVEBToBmqS8kuYpUlxJHYZxk";
    
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
