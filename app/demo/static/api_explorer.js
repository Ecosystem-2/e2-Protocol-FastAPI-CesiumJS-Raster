// SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
// SPDX-FileCopyrightText: 2025-2026 Yang Zhang
// SPDX-License-Identifier: AGPL-3.0-or-later

/* API Explorer - JavaScript Logic */

// ============================================================================
// Tab Switching
// ============================================================================

function switchTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
  document.getElementById(`tab-${tabName}`).classList.add('active');
  event.target.classList.add('active');
}

// ============================================================================
// Response Panel Helpers
// ============================================================================

function showResponse(panelId, data, isError = false) {
  const panel = document.getElementById(panelId);
  panel.querySelector('pre').textContent = JSON.stringify(data, null, 2);
  panel.classList.add('visible');
  panel.classList.toggle('error', isError);
}

function hideResponse(panelId) {
  document.getElementById(panelId).classList.remove('visible');
}

async function apiCall(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({ detail: response.statusText }));
  if (!response.ok) {
    throw { status: response.status, data };
  }
  return data;
}

// ============================================================================
// ASSETS TAB
// ============================================================================

async function loadAssets() {
  const userId = document.getElementById('assetFilterUserId').value.trim();
  const projectId = document.getElementById('assetFilterProjectId').value.trim();

  let url = `${API_BASE}/assets?limit=50`;
  if (userId) url += `&user_id=${encodeURIComponent(userId)}`;
  if (projectId) url += `&project_id=${encodeURIComponent(projectId)}`;

  try {
    const data = await apiCall(url);
    const assets = data.assets || [];

    document.getElementById('assetListStatus').textContent =
      `${assets.length} of ${data.total} asset(s)`;

    // Render entity list
    const listEl = document.getElementById('assetList');
    if (assets.length === 0) {
      listEl.innerHTML = '<div style="text-align:center;color:#94a3b8;padding:16px;">No assets found</div>';
    } else {
      listEl.innerHTML = assets.map(a => `
        <div class="entity-item" onclick="selectAsset(this, '${a.asset_id}', '${a.raster_id || ''}')">
          <div>
            <div class="entity-title">${a.filename || 'Unnamed'}</div>
            <div class="entity-meta">
              ID: ${a.asset_id} &nbsp;|&nbsp;
              raster_id: ${a.raster_id || '—'} &nbsp;|&nbsp;
              ${a.index_type || '?'} &nbsp;|&nbsp;
              user: ${a.user_id || '—'} &nbsp;|&nbsp;
              project: ${a.project_id || '—'}
            </div>
          </div>
          <div class="entity-actions">
            <button class="btn-sm success" onclick="event.stopPropagation(); fillAssetUpdate('${a.asset_id}')">Edit</button>
            <button class="btn-sm danger" onclick="event.stopPropagation(); fillAssetDelete('${a.asset_id}')">Del</button>
          </div>
        </div>
      `).join('');
    }

    showResponse('assetListResponse', data);
  } catch (err) {
    showResponse('assetListResponse', err.data || { error: err.message }, true);
  }
}

function selectAsset(el, assetId, rasterId) {
  document.querySelectorAll('#assetList .entity-item').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  document.getElementById('assetUpdateId').value = assetId;
  document.getElementById('assetDeleteId').value = assetId;
  if (rasterId) {
    document.getElementById('assetLookupRasterId').value = rasterId;
  }
}

function fillAssetUpdate(id) {
  document.getElementById('assetUpdateId').value = id;
  document.getElementById('assetUpdateId').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function fillAssetDelete(id) {
  document.getElementById('assetDeleteId').value = id;
  document.getElementById('assetDeleteId').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function lookupAssetByRasterId() {
  const rasterId = document.getElementById('assetLookupRasterId').value.trim();
  if (!rasterId) return alert('Please enter a raster_id');

  try {
    const data = await apiCall(`${API_BASE}/assets/by-raster-id/${encodeURIComponent(rasterId)}`);
    showResponse('assetLookupResponse', data);
  } catch (err) {
    showResponse('assetLookupResponse', err.data || { error: err.message }, true);
  }
}

async function updateAsset() {
  const id = document.getElementById('assetUpdateId').value.trim();
  if (!id) return alert('Please enter an Asset ID');

  const formData = new FormData();
  const fields = {
    index_type: document.getElementById('assetUpdateIndexType').value.trim(),
    units: document.getElementById('assetUpdateUnits').value.trim(),
    user_id: document.getElementById('assetUpdateUserId').value.trim(),
    project_id: document.getElementById('assetUpdateProjectId').value.trim(),
  };

  let hasField = false;
  for (const [key, val] of Object.entries(fields)) {
    if (val) { formData.append(key, val); hasField = true; }
  }
  if (!hasField) return alert('Please fill in at least one field to update');

  try {
    const data = await apiCall(`${API_BASE}/assets/${id}`, { method: 'PUT', body: formData });
    showResponse('assetUpdateResponse', data);
  } catch (err) {
    showResponse('assetUpdateResponse', err.data || { error: err.message }, true);
  }
}

async function deleteAsset() {
  const id = document.getElementById('assetDeleteId').value.trim();
  if (!id) return alert('Please enter an Asset ID');
  if (!confirm(`Delete asset ${id}? This removes the MongoDB record AND GCS files permanently.`)) return;

  try {
    const data = await apiCall(`${API_BASE}/assets/${id}`, { method: 'DELETE' });
    showResponse('assetDeleteResponse', data);
    loadAssets(); // Refresh list
  } catch (err) {
    showResponse('assetDeleteResponse', err.data || { error: err.message }, true);
  }
}

// ============================================================================
// SELECTIONS TAB
// ============================================================================

async function loadSelections() {
  try {
    const data = await apiCall(`${API_BASE}/selections`);
    const selections = data.selections || [];

    document.getElementById('selectionListStatus').textContent = `${selections.length} selection(s)`;

    const listEl = document.getElementById('selectionList');
    if (selections.length === 0) {
      listEl.innerHTML = '<div style="text-align:center;color:#94a3b8;padding:16px;">No selections found</div>';
    } else {
      listEl.innerHTML = selections.map(s => `
        <div class="entity-item" onclick="selectSelection(this, '${s.id}', '${s.selection_id || ''}')">
          <div>
            <div class="entity-title">${s.title || 'Unnamed'}</div>
            <div class="entity-meta">
              ID: ${s.id} &nbsp;|&nbsp;
              selection_id: ${s.selection_id || '—'} &nbsp;|&nbsp;
              polygons: ${s.polygon_count || 0} &nbsp;|&nbsp;
              stats: ${s.statistics_count || 0}
            </div>
          </div>
          <div class="entity-actions">
            <button class="btn-sm success" onclick="event.stopPropagation(); fillSelectionUpdate('${s.id}')">Edit</button>
            <button class="btn-sm danger" onclick="event.stopPropagation(); fillSelectionDelete('${s.id}')">Del</button>
          </div>
        </div>
      `).join('');
    }

    showResponse('selectionListResponse', data);
  } catch (err) {
    showResponse('selectionListResponse', err.data || { error: err.message }, true);
  }
}

function selectSelection(el, selId, selUUID) {
  document.querySelectorAll('#selectionList .entity-item').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  document.getElementById('selectionUpdateId').value = selId;
  document.getElementById('selectionDeleteId').value = selId;
  document.getElementById('czmlListSelectionId').value = selId;
  if (selUUID) {
    document.getElementById('selectionLookupUUID').value = selUUID;
  }
}

function fillSelectionUpdate(id) {
  document.getElementById('selectionUpdateId').value = id;
  document.getElementById('selectionUpdateId').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function fillSelectionDelete(id) {
  document.getElementById('selectionDeleteId').value = id;
  document.getElementById('selectionDeleteId').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function lookupSelectionByUUID() {
  const uuid = document.getElementById('selectionLookupUUID').value.trim();
  if (!uuid) return alert('Please enter a selection_id UUID');

  try {
    const data = await apiCall(`${API_BASE}/selections/by-selection-id/${encodeURIComponent(uuid)}`);
    showResponse('selectionLookupResponse', data);
  } catch (err) {
    showResponse('selectionLookupResponse', err.data || { error: err.message }, true);
  }
}

async function updateSelection() {
  const id = document.getElementById('selectionUpdateId').value.trim();
  if (!id) return alert('Please enter a Selection ID');

  const formData = new FormData();
  const fields = {
    title: document.getElementById('selectionUpdateTitle').value.trim(),
    description: document.getElementById('selectionUpdateDesc').value.trim(),
    tags: document.getElementById('selectionUpdateTags').value.trim(),
    user_id: document.getElementById('selectionUpdateUserId').value.trim(),
    project_id: document.getElementById('selectionUpdateProjectId').value.trim(),
  };

  let hasField = false;
  for (const [key, val] of Object.entries(fields)) {
    if (val) { formData.append(key, val); hasField = true; }
  }
  if (!hasField) return alert('Please fill in at least one field to update');

  try {
    const data = await apiCall(`${API_BASE}/selections/${id}`, { method: 'PUT', body: formData });
    showResponse('selectionUpdateResponse', data);
  } catch (err) {
    showResponse('selectionUpdateResponse', err.data || { error: err.message }, true);
  }
}

async function deleteSelection() {
  const id = document.getElementById('selectionDeleteId').value.trim();
  if (!id) return alert('Please enter a Selection ID');
  if (!confirm(`Delete selection ${id}? This removes the selection and all its statistics permanently.`)) return;

  try {
    const data = await apiCall(`${API_BASE}/selections/${id}`, { method: 'DELETE' });
    showResponse('selectionDeleteResponse', data);
    loadSelections(); // Refresh list
  } catch (err) {
    showResponse('selectionDeleteResponse', err.data || { error: err.message }, true);
  }
}

// ============================================================================
// CZML TAB
// ============================================================================

async function loadCZMLForSelection() {
  const selectionId = document.getElementById('czmlListSelectionId').value.trim();
  if (!selectionId) return alert('Please enter a Selection ID');

  try {
    const data = await apiCall(`${API_BASE}/selections/${selectionId}/czml`);
    const docs = Array.isArray(data) ? data : [];

    document.getElementById('czmlListStatus').textContent = `${docs.length} document(s)`;

    const listEl = document.getElementById('czmlList');
    if (docs.length === 0) {
      listEl.innerHTML = '<div style="text-align:center;color:#94a3b8;padding:16px;">No CZML documents found for this selection</div>';
    } else {
      listEl.innerHTML = docs.map(c => {
        const czmlObjId = c._id || c.id || '';
        const czmlUUID = c.czml_id || '';
        return `
          <div class="entity-item" onclick="selectCZML(this, '${czmlObjId}', '${czmlUUID}')">
            <div>
              <div class="entity-title">${c.title || 'Unnamed CZML'}</div>
              <div class="entity-meta">
                ID: ${czmlObjId} &nbsp;|&nbsp;
                czml_id: ${czmlUUID || '—'} &nbsp;|&nbsp;
                ${c.index_type || '?'} &nbsp;|&nbsp;
                packets: ${c.packet_count || '?'}
              </div>
            </div>
            <div class="entity-actions">
              <button class="btn-sm success" onclick="event.stopPropagation(); fillCZMLUpdate('${czmlObjId}')">Edit</button>
              <button class="btn-sm danger" onclick="event.stopPropagation(); fillCZMLDelete('${czmlObjId}')">Del</button>
            </div>
          </div>
        `;
      }).join('');
    }

    showResponse('czmlListResponse', data);
  } catch (err) {
    showResponse('czmlListResponse', err.data || { error: err.message }, true);
  }
}

function selectCZML(el, czmlId, czmlUUID) {
  document.querySelectorAll('#czmlList .entity-item').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  document.getElementById('czmlUpdateId').value = czmlId;
  document.getElementById('czmlDeleteId').value = czmlId;
  if (czmlUUID) {
    document.getElementById('czmlLookupUUID').value = czmlUUID;
  }
}

function fillCZMLUpdate(id) {
  document.getElementById('czmlUpdateId').value = id;
  document.getElementById('czmlUpdateId').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function fillCZMLDelete(id) {
  document.getElementById('czmlDeleteId').value = id;
  document.getElementById('czmlDeleteId').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function lookupCZMLByUUID() {
  const uuid = document.getElementById('czmlLookupUUID').value.trim();
  if (!uuid) return alert('Please enter a czml_id UUID');

  try {
    const data = await apiCall(`${API_BASE}/czml/by-czml-id/${encodeURIComponent(uuid)}`);
    showResponse('czmlLookupResponse', data);
  } catch (err) {
    showResponse('czmlLookupResponse', err.data || { error: err.message }, true);
  }
}

async function updateCZML() {
  const id = document.getElementById('czmlUpdateId').value.trim();
  if (!id) return alert('Please enter a CZML ID');

  const formData = new FormData();
  const fields = {
    title: document.getElementById('czmlUpdateTitle').value.trim(),
    description: document.getElementById('czmlUpdateDesc').value.trim(),
    user_id: document.getElementById('czmlUpdateUserId').value.trim(),
    project_id: document.getElementById('czmlUpdateProjectId').value.trim(),
  };

  let hasField = false;
  for (const [key, val] of Object.entries(fields)) {
    if (val) { formData.append(key, val); hasField = true; }
  }
  if (!hasField) return alert('Please fill in at least one field to update');

  try {
    const data = await apiCall(`${API_BASE}/czml/${id}`, { method: 'PUT', body: formData });
    showResponse('czmlUpdateResponse', data);
  } catch (err) {
    showResponse('czmlUpdateResponse', err.data || { error: err.message }, true);
  }
}

async function deleteCZML() {
  const id = document.getElementById('czmlDeleteId').value.trim();
  if (!id) return alert('Please enter a CZML ID');
  if (!confirm(`Delete CZML document ${id}? This action cannot be undone.`)) return;

  try {
    const data = await apiCall(`${API_BASE}/czml/${id}`, { method: 'DELETE' });
    showResponse('czmlDeleteResponse', data);
    // Refresh if possible
    const selId = document.getElementById('czmlListSelectionId').value.trim();
    if (selId) loadCZMLForSelection();
  } catch (err) {
    showResponse('czmlDeleteResponse', err.data || { error: err.message }, true);
  }
}
