/* Step 1 Upload - JavaScript Logic (Multi-file) */

let uploadedAssets = [];

// Initialise step progress
UI.updateStepProgress(1);

// Update file label and queue when files selected
const fileLabel = document.getElementById('fileLabel');
const fileInput = document.getElementById('fileInput');

fileInput.addEventListener('change', (e) => {
  const files = e.target.files;
  if (files.length > 0) {
    fileLabel.classList.add('has-file');
    if (files.length === 1) {
      fileLabel.querySelector('.file-text').textContent = `✓ ${files[0].name} (${formatFileSize(files[0].size)})`;
    } else {
      fileLabel.querySelector('.file-text').textContent = `✓ ${files.length} files selected`;
    }
    renderFileQueue(files);
    // Toggle single-file fields vs multi-file note
    const isMulti = files.length > 1;
    document.getElementById('singleFileFields').style.display = isMulti ? 'none' : '';
    document.getElementById('multiFileNote').style.display = isMulti ? 'block' : 'none';
  } else {
    fileLabel.classList.remove('has-file');
    fileLabel.querySelector('.file-text').textContent = 'Click to select .tif files (multiple allowed)';
    document.getElementById('fileQueue').style.display = 'none';
    document.getElementById('singleFileFields').style.display = '';
    document.getElementById('multiFileNote').style.display = 'none';
  }
});

function _parseYearRangeFromFilename(filename) {
  const match = filename.match(/(\d{4})-(\d{4})/);
  if (match) {
    return { start: `${match[1]}-01-01T00:00`, end: `${match[2]}-12-31T23:59` };
  }
  return { start: '', end: '' };
}

function renderFileQueue(files) {
  const queue = document.getElementById('fileQueue');
  queue.style.display = 'block';
  const isMulti = files.length > 1;

  queue.innerHTML = Array.from(files).map((f, i) => {
    const parsed = isMulti ? _parseYearRangeFromFilename(f.name) : { start: '', end: '' };
    const metaHtml = isMulti ? `
      <div class="file-queue-meta">
        <div class="file-meta-row">
          <label>Start</label>
          <input type="datetime-local" id="fileTimeStart-${i}" value="${parsed.start}" />
        </div>
        <div class="file-meta-row">
          <label>End</label>
          <input type="datetime-local" id="fileTimeEnd-${i}" value="${parsed.end}" />
        </div>
        <div class="file-meta-row">
          <label>Units</label>
          <input type="text" id="fileUnits-${i}" placeholder="e.g., °C, mm" />
        </div>
      </div>
      <div class="file-queue-meta">
        <div class="file-meta-row" style="flex: 1;">
          <label>UUID</label>
          <input type="text" id="fileRasterId-${i}" value="${_generateUUID()}" placeholder="raster_id" />
        </div>
      </div>` : '';

    return `
    <div class="file-queue-item" id="fileQueueItem-${i}">
      <div class="file-queue-header">
        <span class="file-queue-name">${f.name}</span>
        <span class="file-queue-size">${formatFileSize(f.size)}</span>
        <span class="file-queue-status" id="fileStatus-${i}">⏳ Pending</span>
      </div>
      ${metaHtml}
    </div>`;
  }).join('');
}

function generateAllRasterIds() {
  const files = document.getElementById('fileInput').files;
  for (let i = 0; i < files.length; i++) {
    const el = document.getElementById(`fileRasterId-${i}`);
    if (el) el.value = _generateUUID();
  }
  UI.showSuccess('✓ New raster_ids generated for all files');
}

function _updateFileStatus(index, status, isError) {
  const el = document.getElementById(`fileStatus-${index}`);
  if (!el) return;
  el.textContent = status;
  const item = document.getElementById(`fileQueueItem-${index}`);
  if (item) {
    item.classList.remove('uploading', 'success', 'failed');
    if (isError) item.classList.add('failed');
    else if (status.startsWith('✓')) item.classList.add('success');
    else item.classList.add('uploading');
  }
}

function _generateUUID() {
  return (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
      });
}

async function handleUpload() {
  const fileInput = document.getElementById('fileInput');
  const indexType = document.getElementById('indexType').value;

  const files = fileInput.files;
  const total = files.length;
  const isMulti = total > 1;

  // Validation
  if (!total) {
    UI.showStatus('Please select at least one GeoTIFF file', true);
    return;
  }
  if (!indexType) {
    UI.showStatus('Please select an index type', true);
    return;
  }

  // Validate time ranges — per-file when multi, global when single
  if (isMulti) {
    for (let i = 0; i < total; i++) {
      const start = document.getElementById(`fileTimeStart-${i}`)?.value;
      const end = document.getElementById(`fileTimeEnd-${i}`)?.value;
      if (!start || !end) {
        UI.showStatus(`Please enter time range for file: ${files[i].name}`, true);
        return;
      }
    }
  } else {
    const timeStart = document.getElementById('timeStart').value;
    const timeEnd = document.getElementById('timeEnd').value;
    if (!timeStart || !timeEnd) {
      UI.showStatus('Please enter both start and end times', true);
      return;
    }
  }

  const uploadBtn = document.getElementById('uploadBtn');
  uploadBtn.disabled = true;
  uploadBtn.textContent = '⏳ Uploading...';

  // Phase 1-3: Read shared ownership fields
  const userRasterId = document.getElementById('rasterId')?.value?.trim();
  const userId = document.getElementById('userId')?.value?.trim();
  const projectId = document.getElementById('projectId')?.value?.trim();

  // Show progress
  const progressPanel = document.getElementById('uploadProgress');
  const progressBar = document.getElementById('uploadProgressBar');
  const progressText = document.getElementById('uploadProgressText');
  progressPanel.style.display = 'block';
  document.getElementById('uploadResults').style.display = 'none';

  uploadedAssets = [];
  const results = [];

  for (let i = 0; i < total; i++) {
    const file = files[i];
    const pct = Math.round(((i) / total) * 100);
    progressBar.style.width = `${pct}%`;
    progressText.textContent = `Uploading ${i + 1} of ${total}: ${file.name}`;
    _updateFileStatus(i, '⬆️ Uploading...', false);

    // Read per-file or global time/units
    let timeStart, timeEnd, units;
    if (isMulti) {
      timeStart = document.getElementById(`fileTimeStart-${i}`)?.value;
      timeEnd = document.getElementById(`fileTimeEnd-${i}`)?.value;
      units = document.getElementById(`fileUnits-${i}`)?.value;
    } else {
      timeStart = document.getElementById('timeStart').value;
      timeEnd = document.getElementById('timeEnd').value;
      units = document.getElementById('units').value;
    }

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('indexType', indexType);
      formData.append('timeStart', convertToISOString(timeStart));
      formData.append('timeEnd', convertToISOString(timeEnd));
      if (units) formData.append('units', units);

      // Read raster_id: per-file field when multi, global field when single
      if (isMulti) {
        const fileRasterId = document.getElementById(`fileRasterId-${i}`)?.value?.trim();
        if (fileRasterId) formData.append('rasterID', fileRasterId);
      } else if (userRasterId) {
        formData.append('rasterID', userRasterId);
      }

      if (userId) formData.append('userID', userId);
      if (projectId) formData.append('projectID', projectId);

      const response = await fetch(`${API_BASE}/ingest`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        let detail = error.detail;
        if (Array.isArray(detail)) {
          // FastAPI validation errors: [{loc: [...], msg: "...", type: "..."}, ...]
          detail = detail.map(e => {
            const loc = Array.isArray(e.loc) ? e.loc.join(' → ') : '';
            return loc ? `${loc}: ${e.msg}` : e.msg;
          }).join('; ');
        } else if (detail && typeof detail === 'object') {
          detail = JSON.stringify(detail);
        }
        throw new Error(detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      results.push({ file: file.name, success: true, data });
      uploadedAssets.push(data);
      _updateFileStatus(i, '✓ Success', false);

    } catch (error) {
      results.push({ file: file.name, success: false, error: error.message });
      _updateFileStatus(i, `✗ ${error.message}`, true);
    }
  }

  // Complete progress bar
  progressBar.style.width = '100%';
  const successCount = results.filter(r => r.success).length;
  const failCount = results.filter(r => !r.success).length;
  progressText.textContent = `Done: ${successCount} succeeded, ${failCount} failed out of ${total}`;

  // Store results in workflow state
  if (uploadedAssets.length > 0) {
    const lastAsset = uploadedAssets[uploadedAssets.length - 1];
    WorkflowState.set('uploaded_asset', lastAsset);
    WorkflowState.set('current_asset_id', lastAsset.assetID || lastAsset.asset_id);
    WorkflowState.set('current_asset', lastAsset.asset);
    WorkflowState.set('uploaded_assets', uploadedAssets);
    // Persist ownership fields for downstream steps
    if (userId) WorkflowState.set('user_id', userId);
    if (projectId) WorkflowState.set('project_id', projectId);
    WorkflowState.completeStep(1);
    document.getElementById('nextBtn').disabled = false;
  }

  // Show summary
  if (failCount === 0) {
    UI.showSuccess(`✓ All ${total} file(s) uploaded successfully!`);
  } else if (successCount > 0) {
    UI.showStatus(`⚠ ${successCount} of ${total} uploaded. ${failCount} failed.`, true);
  } else {
    UI.showStatus(`✗ All ${total} uploads failed.`, true);
  }

  displayUploadResults(results);

  uploadBtn.disabled = false;
  uploadBtn.textContent = '📤 Upload & Store';
}

function displayUploadResults(results) {
  const container = document.getElementById('uploadResults');
  container.style.display = 'block';

  const cards = results.map((r, i) => {
    if (r.success) {
      const d = r.data;
      const sizes = d.raster?.sizes;
      const dims = (sizes?.x && sizes?.y) ? `${sizes.x} × ${sizes.y} px` : 'N/A';
      const tr = d.asset?.timeRange || d.asset?.time_range;
      const timeStr = (tr?.start && tr?.end)
        ? `${new Date(tr.start).toLocaleDateString()} – ${new Date(tr.end).toLocaleDateString()}`
        : 'N/A';
      const replacedHtml = d.replaced
        ? '<span style="color: var(--workflow-warning);">✓ Replaced</span>'
        : '<span style="color: var(--workflow-success);">New</span>';

      return `
        <div class="upload-result-card success">
          <div class="upload-result-header">
            <span class="upload-result-icon">✓</span>
            <strong>${r.file}</strong>
            ${replacedHtml}
          </div>
          <div class="upload-result-details">
            <div><span class="detail-label">Asset ID:</span> <span class="detail-value">${d.assetID || d.asset_id || 'N/A'}</span></div>
            <div><span class="detail-label">raster_id:</span> <span class="detail-value">${d.rasterID || d.raster_id || '—'}</span></div>
            <div><span class="detail-label">Index:</span> <span class="detail-value">${d.asset?.indexType || d.asset?.index_type || 'N/A'}</span></div>
            <div><span class="detail-label">CRS:</span> <span class="detail-value">${d.raster?.epsg ? 'EPSG:' + d.raster.epsg : 'N/A'}</span></div>
            <div><span class="detail-label">Size:</span> <span class="detail-value">${dims}</span></div>
            <div><span class="detail-label">Time:</span> <span class="detail-value">${timeStr}</span></div>
          </div>
        </div>`;
    } else {
      return `
        <div class="upload-result-card failed">
          <div class="upload-result-header">
            <span class="upload-result-icon">✗</span>
            <strong>${r.file}</strong>
            <span style="color: var(--workflow-danger);">Failed</span>
          </div>
          <div class="upload-result-details">
            <div style="color: var(--workflow-danger);">${r.error}</div>
          </div>
        </div>`;
    }
  }).join('');

  container.innerHTML = `
    <h3 style="color: #60a5fa; margin: 0 0 15px 0;">📋 Upload Results (${results.filter(r=>r.success).length}/${results.length})</h3>
    ${cards}
  `;
}

function generateRasterId() {
  document.getElementById('rasterId').value = _generateUUID();
}

function proceedToStep2() {
  if (uploadedAssets.length > 0) {
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
