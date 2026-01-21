/**
 * Reusable Cesium GeoTIFF viewer with timeline support.
 * 
 * Usage:
 *   const config = {
 *     containerId: 'cesiumContainer',
 *     scenarios: [...],
 *     palette: [...],
 *     labels: [...],
 *     dataRoots: [...],
 *     viewerOptions: {...}
 *   };
 *   const viewer = new CesiumGeoTIFFViewer(config);
 *   viewer.init();
 */

class CesiumGeoTIFFViewer {
    constructor(config) {
        this.config = config;
        this.viewer = null;
        this.scenarios = [];
        
        // DOM elements
        this.statusEl = document.getElementById('status');
        this.scenarioSelect = document.getElementById('scenarioSelect');
        this.legendItemsEl = document.getElementById('legendItems');
        this.activePeriodEl = document.getElementById('activePeriod');
    }

    setStatus(message, isError = false) {
        if (!this.statusEl) return;
        if (!message) {
            this.statusEl.style.display = 'none';
            this.statusEl.textContent = '';
            this.statusEl.classList.remove('error');
            return;
        }
        this.statusEl.textContent = message;
        this.statusEl.style.display = 'block';
        this.statusEl.classList.toggle('error', Boolean(isError));
    }

    hexToRgb(hex) {
        const value = hex.replace('#', '');
        const intVal = parseInt(value, 16);
        return [
            (intVal >> 16) & 255,
            (intVal >> 8) & 255,
            intVal & 255,
        ];
    }

    clamp01(value) {
        return Math.max(0, Math.min(1, value));
    }

    computeAlpha(nowMs, startMs, endMs, fadeMs) {
        const fadeStart = startMs - fadeMs;
        const fadeEnd = endMs + fadeMs;
        if (nowMs <= fadeStart || nowMs >= fadeEnd) {
            return 0;
        }
        if (nowMs < startMs) {
            return this.clamp01((nowMs - fadeStart) / fadeMs);
        }
        if (nowMs > endMs) {
            return this.clamp01((fadeEnd - nowMs) / fadeMs);
        }
        return 1;
    }

    populateLegend() {
        if (!this.legendItemsEl || !this.config.palette || !this.config.labels) return;
        this.legendItemsEl.innerHTML = '';
        this.config.palette.forEach((color, idx) => {
            const li = document.createElement('li');
            const swatch = document.createElement('span');
            swatch.className = 'swatch';
            swatch.style.background = color;
            const text = document.createElement('span');
            text.textContent = this.config.labels[idx] || `Class ${idx + 1}`;
            li.appendChild(swatch);
            li.appendChild(text);
            this.legendItemsEl.appendChild(li);
        });
    }

    populateScenarioSelect(scenarios) {
        if (!this.scenarioSelect) return;
        this.scenarioSelect.innerHTML = '';
        scenarios.forEach((scenario, index) => {
            const option = document.createElement('option');
            option.value = scenario.id;
            option.textContent = scenario.label;
            if (index === 0) {
                option.selected = true;
            }
            this.scenarioSelect.appendChild(option);
        });
    }

    /**
     * Load a file via XMLHttpRequest for file:// protocol compatibility
     */
    async loadFileAsBlob(filePath) {
        return new Promise((resolve, reject) => {
            // Resolve paths properly
            let resolvedPath = filePath;
            
            // If it's already an absolute URL (http:// or https://), use it as-is
            if (filePath.startsWith('http://') || filePath.startsWith('https://')) {
                resolvedPath = filePath;
            } else if (filePath.startsWith('/')) {
                // Absolute path from root - resolve relative to current origin
                resolvedPath = window.location.origin + filePath;
            } else if (filePath.startsWith('../') || filePath.startsWith('./')) {
                // Resolve relative to current HTML file location
                const basePath = window.location.href.substring(0, window.location.href.lastIndexOf('/') + 1);
                resolvedPath = new URL(filePath, basePath).href;
            } else {
                // Relative path without ./ or ../ - resolve relative to current page
                const basePath = window.location.href.substring(0, window.location.href.lastIndexOf('/') + 1);
                resolvedPath = new URL(filePath, basePath).href;
            }
            
            const xhr = new XMLHttpRequest();
            xhr.open('GET', resolvedPath, true);
            xhr.responseType = 'blob';
            
            xhr.onload = function() {
                // Status 0 is common for file:// protocol
                if (xhr.status === 0 || xhr.status === 200) {
                    if (xhr.response instanceof Blob) {
                        resolve(xhr.response);
                    } else {
                        reject(new Error(`Unexpected response type: ${typeof xhr.response}`));
                    }
                } else {
                    reject(new Error(`Failed to load file: ${xhr.status} ${xhr.statusText}`));
                }
            };
            
            xhr.onerror = function() {
                reject(new Error(`Network error loading file: ${resolvedPath}`));
            };
            
            xhr.ontimeout = function() {
                reject(new Error(`Timeout loading file: ${resolvedPath}`));
            };
            
            // Set a reasonable timeout
            xhr.timeout = 30000; // 30 seconds
            
            try {
                xhr.send();
            } catch (error) {
                reject(new Error(`Failed to send request: ${error.message}`));
            }
        });
    }

    /**
     * Load GeoTIFF from URL, with file:// protocol fallback
     */
    async loadGeoTIFF(url, isFileProtocol) {
        // Try loading as blob first for better compatibility (works for both file:// and http/https)
        try {
            const blob = await this.loadFileAsBlob(url);
            const arrayBuffer = await blob.arrayBuffer();
            return await GeoTIFF.fromArrayBuffer(arrayBuffer);
        } catch (blobError) {
            try {
                return await GeoTIFF.fromUrl(url);
            } catch (urlError) {
                throw new Error(`Failed to load GeoTIFF from ${url}: ${urlError.message}`);
            }
        }
    }

    async loadScenarioLayer(viewer, scenario, paletteColors) {
        this.setStatus(`Loading ${scenario.label} GeoTIFF...`);
        let tiff = null;
        let resolvedUrl = null;
        let lastError = null;
        const isFileProtocol = window.location.protocol === 'file:';
        
        for (const url of scenario.assetUrls) {
            try {
                tiff = await this.loadGeoTIFF(url, isFileProtocol);
                resolvedUrl = url;
                break;
            } catch (error) {
                lastError = error;
                continue;
            }
        }
        if (!tiff) {
            const locations = scenario.assetUrls.join(', ');
            throw new Error(`Failed to load ${scenario.file}. Tried: ${locations}`);
        }
        
        const image = await tiff.getImage();
        const bbox = image.getBoundingBox();
        const width = image.getWidth();
        const height = image.getHeight();
        const rasterData = await image.readRasters({ samples: [0], interleave: true });
        const data = Array.isArray(rasterData) ? rasterData[0] : rasterData;
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        const imageData = ctx.createImageData(width, height);
        for (let i = 0; i < data.length; i += 1) {
            const value = data[i];
            const classValue = Number.isFinite(value) ? Math.round(value) : NaN;
            const offset = i * 4;
            if (classValue >= 1 && classValue <= paletteColors.length) {
                const color = paletteColors[classValue - 1];
                imageData.data[offset] = color[0];
                imageData.data[offset + 1] = color[1];
                imageData.data[offset + 2] = color[2];
                imageData.data[offset + 3] = 255;
            } else {
                imageData.data[offset + 3] = 0;
            }
        }
        ctx.putImageData(imageData, 0, 0);
        const dataUrl = canvas.toDataURL('image/png');
        // GeoTIFF bbox is [minX, minY, maxX, maxY] = [west, south, east, north]
        const rectangle = Cesium.Rectangle.fromDegrees(bbox[0], bbox[1], bbox[2], bbox[3]);
        const imageryLayer = viewer.imageryLayers.addImageryProvider(
            new Cesium.SingleTileImageryProvider({ url: dataUrl, rectangle }),
        );
        imageryLayer.alpha = 0.0;
        // Ensure the layer doesn't block the base layer when transparent
        imageryLayer.show = true;
        scenario.imageryLayer = imageryLayer;
        scenario.bounds = bbox;
        scenario.rectangle = rectangle;
        scenario.resolvedUrl = resolvedUrl;
    }

    configureClock(viewer, scenarios) {
        const startMs = Math.min(...scenarios.map((s) => Date.parse(`${s.start}T00:00:00Z`)));
        const endMs = Math.max(...scenarios.map((s) => Date.parse(`${s.end}T23:59:59Z`)));
        scenarios.forEach((scenario) => {
            scenario.startMs = Date.parse(`${scenario.start}T00:00:00Z`);
            scenario.endMs = Date.parse(`${scenario.end}T23:59:59Z`);
            scenario.fadeMs = scenario.fadeYears * 365.25 * 24 * 3600 * 1000;
        });
        const startJulian = Cesium.JulianDate.fromDate(new Date(startMs));
        const endJulian = Cesium.JulianDate.fromDate(new Date(endMs));
        viewer.clock.startTime = startJulian;
        viewer.clock.stopTime = endJulian;
        viewer.clock.currentTime = startJulian;
        viewer.clock.clockRange = Cesium.ClockRange.CLAMPED;
        viewer.clock.multiplier = 86400 * 90;
        viewer.clock.shouldAnimate = false; // Don't auto-play - wait for user to press play
        viewer.timeline.zoomTo(startJulian, endJulian);
    }

    updateActivePeriod(nowMs, scenarios) {
        let activeScenario = null;
        let maxAlpha = 0;
        scenarios.forEach((scenario) => {
            if (!scenario.imageryLayer) {
                return;
            }
            const alpha = this.computeAlpha(nowMs, scenario.startMs, scenario.endMs, scenario.fadeMs);
            scenario.imageryLayer.alpha = alpha;
            if (alpha > maxAlpha) {
                activeScenario = scenario;
                maxAlpha = alpha;
            }
        });
        if (activeScenario && this.activePeriodEl) {
            this.activePeriodEl.textContent = `${activeScenario.label}`;
            if (this.scenarioSelect) {
                this.scenarioSelect.value = activeScenario.id;
            }
        } else if (this.activePeriodEl) {
            this.activePeriodEl.textContent = 'No scenario active';
        }
    }

    hookScenarioSelect(viewer, scenarios) {
        if (!this.scenarioSelect) return;
        this.scenarioSelect.addEventListener('change', (event) => {
            const selected = scenarios.find((s) => s.id === event.target.value);
            if (!selected) {
                return;
            }
            const midpoint = new Date((selected.startMs + selected.endMs) / 2);
            viewer.clock.currentTime = Cesium.JulianDate.fromDate(midpoint);
        });
    }

    async init() {
        if (!window.Cesium || !window.GeoTIFF) {
            const missing = [];
            if (!window.Cesium) missing.push('CesiumJS');
            if (!window.GeoTIFF) missing.push('geotiff.js');
            this.setStatus(`Missing required libraries: ${missing.join(', ')}`, true);
            return;
        }

        const paletteColors = this.config.palette.map((hex) => this.hexToRgb(hex));
        this.populateLegend();
        
        // Prepare scenarios with asset URLs
        this.scenarios = this.config.scenarios.map((scenario) => ({
            ...scenario,
            assetUrls: this.config.dataRoots.map((root) => `${root}/geotif/${scenario.file}`),
        }));
        
        this.populateScenarioSelect(this.scenarios);
        
        const ionToken = window.CESIUM_ION_TOKEN || '';
        if (ionToken) {
            Cesium.Ion.defaultAccessToken = ionToken;
        }
        
        const viewerOptions = {
            baseLayerPicker: true,
            geocoder: false,
            animation: true,
            timeline: true,
            sceneModePicker: false,
            navigationHelpButton: false,
            fullscreenButton: false,
            infoBox: true,
            ...this.config.viewerOptions,
        };
        
        this.viewer = new Cesium.Viewer(this.config.containerId, viewerOptions);

        this.viewer.scene.globe.enableLighting = true;
        
        if (this.viewer.imageryLayers.length > 0) {
            const baseLayer = this.viewer.imageryLayers.get(0);
            baseLayer.alpha = 1.0;
            baseLayer.show = true;
        }
        
        this.configureClock(this.viewer, this.scenarios);
        
        for (const scenario of this.scenarios) {
            try {
                await this.loadScenarioLayer(this.viewer, scenario, paletteColors);
            } catch (error) {
                this.setStatus(error.message, true);
                return;
            }
        }
        
        if (this.viewer.imageryLayers.length > 1) {
            const baseLayer = this.viewer.imageryLayers.get(0);
            baseLayer.alpha = 1.0;
            baseLayer.show = true;
        }
        
        this.setStatus('');
        this.hookScenarioSelect(this.viewer, this.scenarios);
        
        this.viewer.clock.onTick.addEventListener(() => {
            const nowMs = Cesium.JulianDate.toDate(this.viewer.clock.currentTime).getTime();
            this.updateActivePeriod(nowMs, this.scenarios);
        });
        
        // Zoom camera to the bounds of all loaded scenarios
        const allRectangles = this.scenarios
            .filter((s) => s.rectangle)
            .map((s) => s.rectangle);
        if (allRectangles.length > 0) {
            // Combine all rectangles to get the full extent
            let combinedRectangle = allRectangles[0];
            for (let i = 1; i < allRectangles.length; i++) {
                combinedRectangle = Cesium.Rectangle.union(combinedRectangle, allRectangles[i]);
            }
            
            // Use setView to position camera at the bounds
            this.viewer.camera.setView({
                destination: combinedRectangle,
            });
        }
        
        // Update active period and ensure visibility
        this.updateActivePeriod(
            Cesium.JulianDate.toDate(this.viewer.clock.currentTime).getTime(),
            this.scenarios,
        );
        
        // If no scenario is active (alpha = 0), make the first one visible
        const firstScenario = this.scenarios[0];
        if (firstScenario.imageryLayer && firstScenario.imageryLayer.alpha === 0) {
            firstScenario.imageryLayer.alpha = 1.0;
        }
    }
}

