/* Step 1 Upload - JavaScript Logic */

let uploadedAsset = null;

// Initialise step progress
UI.updateStepProgress(1);

// Update file label when file selected
const fileLabel = document.getElementById('fileLabel');
const fileInput = document.getElementById('fileInput');

fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) {
    fileLabel.classList.add('has-file');
    fileLabel.querySelector('.file-text').textContent = `✓ ${file.name} (${formatFileSize(file.size)})`;
  } else {
    fileLabel.classList.remove('has-file');
    fileLabel.querySelector('.file-text').textContent = 'Click to select .tif file';
  }
});

async function handleUpload() {
  const fileInput = document.getElementById('fileInput');
  const indexType = document.getElementById('indexType').value;
  const timeStart = document.getElementById('timeStart').value;
  const timeEnd = document.getElementById('timeEnd').value;
  const units = document.getElementById('units').value;

  // Validation
  if (!fileInput.files[0]) {
    UI.showStatus('Please select a GeoTIFF file', true);
    return;
  }
  if (!indexType) {
    UI.showStatus('Please select an index type', true);
    return;
  }
  if (!timeStart || !timeEnd) {
    UI.showStatus('Please enter both start and end times', true);
    return;
  }

  const uploadBtn = document.getElementById('uploadBtn');
  uploadBtn.disabled = true;
  uploadBtn.textContent = '⏳ Uploading...';

  try {
    UI.showStatus('Uploading and processing GeoTIFF...');

    // Build FormData
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('index_type', indexType);
    formData.append('time_start', convertToISOString(timeStart));
    formData.append('time_end', convertToISOString(timeEnd));
    if (units) formData.append('units', units);

    const response = await fetch(`${API_BASE}/ingest`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    uploadedAsset = data;

    // Store in workflow state
    WorkflowState.set('uploaded_asset', data);
    WorkflowState.set('current_asset_id', data.asset_id);
    WorkflowState.set('current_asset', data.asset);
    WorkflowState.completeStep(1);

    // Show success
    UI.showSuccess('✓ Asset uploaded and stored successfully!');
    UI.showResults('Upload Response', data);

    // Update summary
    displayUploadSummary(data);
    document.getElementById('nextBtn').disabled = false;

  } catch (error) {
    UI.showStatus(`Upload failed: ${error.message}`, true);
    console.error('Upload error:', error);
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = '📤 Upload & Store';
  }
}

function displayUploadSummary(data) {
  document.getElementById('uploadSummary').style.display = 'block';
  document.getElementById('assetIdValue').textContent = data.asset_id || 'N/A';
  document.getElementById('filenameValue').textContent = data.asset?.filename || 'N/A';
  document.getElementById('indexTypeValue').textContent = data.asset?.index_type || 'N/A';
  document.getElementById('crsValue').textContent = data.raster?.epsg ? `EPSG:${data.raster.epsg}` : 'N/A';
  
  // Use raster sizes (pixels) instead of bounds (degrees)
  const sizes = data.raster?.sizes;
  if (sizes?.x && sizes?.y) {
    document.getElementById('dimensionsValue').textContent = `${sizes.x} × ${sizes.y} px`;
  } else {
    document.getElementById('dimensionsValue').textContent = 'N/A';
  }
  
  const timeRange = data.asset?.time_range;
  if (timeRange?.start && timeRange?.end) {
    const start = new Date(timeRange.start).toLocaleDateString();
    const end = new Date(timeRange.end).toLocaleDateString();
    document.getElementById('timeRangeValue').textContent = `${start} – ${end}`;
  } else {
    document.getElementById('timeRangeValue').textContent = 'N/A';
  }
  
  // Show if asset was replaced
  const replacedEl = document.getElementById('replacedValue');
  if (data.replaced === true) {
    replacedEl.textContent = '✓ Yes';
    replacedEl.style.color = 'var(--workflow-warning)';
  } else {
    replacedEl.textContent = '✗ No (New)';
    replacedEl.style.color = 'var(--workflow-success)';
  }
}

function proceedToStep2() {
  if (uploadedAsset) {
    UI.goToStep(2);
  }
}

function convertToISOString(datetimeLocal) {
  if (!datetimeLocal) return '';
  const date = new Date(datetimeLocal);
  return date.toISOString();
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDatetimeLocal(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// Set default time values (current year range)
window.addEventListener('DOMContentLoaded', () => {
  const now = new Date();
  const startOfYear = new Date(now.getFullYear(), 0, 1);
  const endOfYear = new Date(now.getFullYear(), 11, 31, 23, 59, 59);
  
  document.getElementById('timeStart').value = formatDatetimeLocal(startOfYear);
  document.getElementById('timeEnd').value = formatDatetimeLocal(endOfYear);

  // Load previous upload if exists
  const savedAsset = WorkflowState.get('uploaded_asset');
  if (savedAsset) {
    uploadedAsset = savedAsset;
    displayUploadSummary(savedAsset);
    document.getElementById('nextBtn').disabled = false;
    UI.showSuccess('Previous upload loaded from session');
  }
});
