/**
 * Configuration for the Humid Heat Stress Cesium viewer demo.
 * 
 * Configuration priority (highest to lowest):
 * 1. window.HUMID_HEAT_STRESS_API_BASE_URL - Explicit API base URL (e.g., 'https://api.example.com')
 * 2. window.FASTAPI_BASE_URL - Explicit FastAPI base URL
 * 3. Same origin detection - Use relative paths if served from same origin as API
 * 4. Auto-detect from current origin - Construct URL based on current page location
 */

const getDefaultServerRoot = () => {
    // Priority 1: Explicit API base URL configuration (highest priority)
    if (window.HUMID_HEAT_STRESS_API_BASE_URL) {
        const baseUrl = window.HUMID_HEAT_STRESS_API_BASE_URL.replace(/\/$/, ''); // Remove trailing slash
        return `${baseUrl}/api/demo/humid-heat-stress/assets`;
    }
    
    // Priority 2: Explicit FastAPI base URL
    if (window.FASTAPI_BASE_URL) {
        const baseUrl = window.FASTAPI_BASE_URL.replace(/\/$/, ''); // Remove trailing slash
        return `${baseUrl}/api/demo/humid-heat-stress/assets`;
    }
    
    // Priority 3: If served from same origin, use relative path (works for production deployments)
    // This handles cases where HTML and API are on the same domain/port
    const currentOrigin = window.location.origin;
    const currentPath = window.location.pathname;
    
    // Check if we're accessing via the FastAPI route structure
    // If path contains '/api/demo/humid-heat-stress/', we're likely on the same server
    if (currentPath.includes('/api/demo/humid-heat-stress/')) {
        return '/api/demo/humid-heat-stress/assets';
    }
    
    // Priority 4: Try to construct URL from current origin
    // This handles cross-origin scenarios (e.g., HTML on CDN, API on different server)
    // For same-host different-port scenarios, try common FastAPI ports
    const currentProtocol = window.location.protocol;
    const currentHostname = window.location.hostname;
    const currentPort = window.location.port;
    
    // If we have a port and it's not 80/443, try to infer API port
    // Otherwise, use same origin with API path
    if (currentPort && currentPort !== '80' && currentPort !== '443' && currentPort !== '') {
        // For development: try common FastAPI port (8080) or use configured port
        const apiPort = window.FASTAPI_PORT || '8080';
        // Only use different port if we're on localhost/127.0.0.1 (development scenario)
        if (currentHostname === 'localhost' || currentHostname === '127.0.0.1') {
            return `${currentProtocol}//${currentHostname}:${apiPort}/api/demo/humid-heat-stress/assets`;
        }
    }
    
    // Default: use same origin with API path (works for production same-domain deployments)
    return `${currentOrigin}/api/demo/humid-heat-stress/assets`;
};

const DEFAULT_SERVER_ROOT = getDefaultServerRoot();
const FALLBACK_LOCAL_ROOT = '../../data/humid-heat-stress';

const DATA_ROOTS = (() => {
    const roots = [];
    if (window.HUMID_HEAT_STRESS_DATA_ROOT) {
        roots.push(window.HUMID_HEAT_STRESS_DATA_ROOT);
    }
    if (window.location.protocol !== 'file:') {
        roots.push(DEFAULT_SERVER_ROOT);
    }
    roots.push(FALLBACK_LOCAL_ROOT);
    return [...new Set(roots)];
})();

const HUMID_PALETTE = [
    '#00e676',
    '#ffee58',
    '#ffb347',
    '#ff7043',
    '#2d142c',
];

const HUMID_LABELS = [
    'Low threat',
    'Elevated threat',
    'Moderate threat',
    'High threat',
    'Extreme threat',
];

const HUMID_SCENARIOS = [
    {
        id: 'historic',
        label: 'Historic (1981-2010)',
        start: '1981-01-01',
        end: '2010-12-31',
        fadeYears: 6,
        file: 'Segama_Historic_1981-2010_WBGT-Sun_Max_threat_level.tif',
    },
    {
        id: 'mid-century',
        label: 'Mid-century (2041-2070)',
        start: '2041-01-01',
        end: '2070-12-31',
        fadeYears: 6,
        file: 'Segama_All245_2041-2070_WBGT-Sun_Max_threat_level.tif',
    },
    {
        id: 'late-century',
        label: 'Late-century (2071-2100)',
        start: '2071-01-01',
        end: '2100-12-31',
        fadeYears: 6,
        file: 'Segama_All245_2071-2100_WBGT-Sun_Max_threat_level.tif',
    },
];

// Create config function to ensure Cesium is loaded first
function getHumidHeatStressConfig() {
    return {
        containerId: 'cesiumContainer',
        scenarios: HUMID_SCENARIOS,
        palette: HUMID_PALETTE,
        labels: HUMID_LABELS,
        dataRoots: DATA_ROOTS,
        // imageryProvider: new Cesium.OpenStreetMapImageryProvider({
        //     url: 'https://tile.openstreetmap.org/',
        // }),
        viewerOptions: {},
    };
}

