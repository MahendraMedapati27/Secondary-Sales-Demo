// THREE.js Enhanced Natural Human Avatar System
console.log('[NATURAL-AVATAR] Module initializing...');

// Import THREE.js from CDN
import * as THREE from "https://cdn.skypack.dev/three@0.129.0/build/three.module.js";
import { OrbitControls } from "https://cdn.skypack.dev/three@0.129.0/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "https://cdn.skypack.dev/three@0.129.0/examples/jsm/loaders/GLTFLoader.js";

console.log('[NATURAL-AVATAR] ✅ Imports successful');

// Global variables
let scene, camera, renderer, controls;
let avatarObject = null;
let avatarBones = {};
let avatarSkeleton = null;
let originalArmRotations = { rightArm: null, leftArm: null }; // Store original T-pose rotations
let isAnimating = false;
let avatarLoaded = false;
let baseScaleY = 1.0;
let mixer = null;

// Background scene variables
let backgroundScene, backgroundCamera, backgroundRenderer, backgroundControls;
let backgroundObject = null;
let backgroundSpherical = null; // Global variable for background camera spherical coordinates

// Human-like behavior variables
let mousePosition = { x: 0, y: 0 };
let targetLookPosition = new THREE.Vector3();
let currentLookPosition = new THREE.Vector3();
let isLookingAtMouse = true;
let isSpeaking = false;
let isUserTyping = false;

// Avatar container
let avatarContainer = null;
let fallbackElement = null;

// Dragging variable (for tracking mouse during orbit controls)
let isDragging = false;

console.log('[NATURAL-AVATAR] Initializing natural avatar system...');

// Initialize THREE.js scene
function initThreeScene() {
    console.log('[NATURAL-AVATAR] Creating THREE.js scene...');
    
    avatarContainer = document.getElementById('avatar-container');
    if (!avatarContainer) {
        console.error('[NATURAL-AVATAR] ❌ Avatar container not found');
        return false;
    }
    
    // Create scene
    scene = new THREE.Scene();
    scene.background = null;
    
    const container = avatarContainer;
    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight || 500;
    
    console.log('[NATURAL-AVATAR] Container dimensions:', { width, height });
    
    // Create camera - lower and slightly zoomed out
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0.8, 3.5); // Lower Y (0.8) and slightly zoomed out Z (3.5 instead of 3)
    camera.lookAt(0, 0.5, 0); // Look at lower point
    
    // Create renderer
    renderer = new THREE.WebGLRenderer({ 
        alpha: true, 
        antialias: true,
        powerPreference: "high-performance"
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    
    // FIX COLOR ISSUES: Proper tone mapping with MAXIMUM exposure
    renderer.toneMapping = THREE.ACESFilmicToneMapping;  // Cinematic tone mapping
    renderer.toneMappingExposure = 1.6;  // MAXIMUM exposure for brightness
    renderer.outputEncoding = THREE.sRGBEncoding;  // Correct color space
    console.log('[NATURAL-AVATAR] ✅ Renderer configured: ACESFilmic, exposure=1.6 (MAXIMUM BRIGHT)');
    
    // Add renderer to container
    const canvasContainer = document.getElementById('three-canvas-container');
    if (canvasContainer) {
        canvasContainer.appendChild(renderer.domElement);
        console.log('[NATURAL-AVATAR] ✅ Renderer added to DOM');
    } else {
        console.error('[NATURAL-AVATAR] ❌ Canvas container not found');
        return false;
    }
    
    // Enhanced lighting - MAXIMUM BRIGHTNESS
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);  // MAXIMUM ambient
    scene.add(ambientLight);
    
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.2);  // MAXIMUM key light
    keyLight.position.set(5, 8, 5);
    keyLight.castShadow = true;
    scene.add(keyLight);
    
    const fillLight = new THREE.DirectionalLight(0xb3d9ff, 0.6);  // Increased fill
    fillLight.position.set(-5, 3, -5);
    scene.add(fillLight);
    
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.5);  // Increased rim
    rimLight.position.set(0, 5, -10);
    scene.add(rimLight);
    
    console.log('[NATURAL-AVATAR] ✅ Lighting configured (total intensity: 3.3 - MAXIMUM BRIGHT)');
    
    // Enable orbit controls for zoom and rotation
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enabled = false; // Initially disabled, will be enabled when mouse enters avatar section
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 2;
    controls.maxDistance = 8;
    controls.target.set(0, 0.5, 0); // Look at lower point (avatar center on floor)
    controls.update();
    
    // Track dragging state for head rotation
    controls.addEventListener('start', () => {
        isDragging = true;
        renderer.domElement.style.cursor = 'grabbing';
        // Disable background controls when avatar is being dragged
        if (backgroundControls) {
            backgroundControls.enabled = false;
        }
    });
    
    controls.addEventListener('end', () => {
        isDragging = false;
        renderer.domElement.style.cursor = 'grab';
    });
    
    renderer.domElement.style.cursor = 'grab';
    
    // Enable avatar controls only when mouse is over the actual avatar body
    // Use mousemove to check if mouse is over avatar using raycasting
    const avatarCanvasElement = renderer.domElement;
    let isOverAvatarBody = false;
    
    avatarCanvasElement.addEventListener('mousemove', (e) => {
        const rect = avatarCanvasElement.getBoundingClientRect();
        const x = e.clientX;
        const y = e.clientY;
        
        // Check if mouse is over avatar body using raycasting
        const wasOverAvatar = isOverAvatarBody;
        isOverAvatarBody = getIsOverAvatarBody(x, y);
        
        if (isOverAvatarBody && !wasOverAvatar) {
            // Mouse entered avatar body
            controls.enabled = true;
            if (backgroundControls) {
                backgroundControls.enabled = false;
            }
        } else if (!isOverAvatarBody && wasOverAvatar) {
            // Mouse left avatar body
            controls.enabled = false;
            if (backgroundControls) {
                backgroundControls.enabled = true;
            }
        }
    });
    
    // Helper function to check if mouse is over avatar body (using raycasting)
    const getIsOverAvatarBody = (x, y) => {
        if (!avatarObject || !renderer || !camera || !scene) return false;
        
        const rect = avatarCanvasElement.getBoundingClientRect();
        if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
            return false;
        }
        
        const mouse = new THREE.Vector2();
        mouse.x = ((x - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((y - rect.top) / rect.height) * 2 + 1;
        
        const raycaster = new THREE.Raycaster();
        raycaster.setFromCamera(mouse, camera);
        const intersects = raycaster.intersectObject(avatarObject, true);
        
        return intersects.length > 0;
    };
    
    // Also handle mouse leave from canvas
    avatarCanvasElement.addEventListener('mouseleave', () => {
        isOverAvatarBody = false;
        controls.enabled = false;
        if (backgroundControls) {
            backgroundControls.enabled = true;
        }
    });
    
    console.log('[NATURAL-AVATAR] ✅ Scene initialized');
    return true;
}

// Initialize background scene for office
function initBackgroundScene() {
    console.log('[NATURAL-AVATAR] Creating background scene...');
    
    const backgroundContainer = document.getElementById('background-canvas-container');
    if (!backgroundContainer) {
        console.warn('[NATURAL-AVATAR] ⚠️ Background container not found');
        return false;
    }
    
    // Create background scene
    backgroundScene = new THREE.Scene();
    backgroundScene.background = null;
    
    const width = window.innerWidth;
    const height = window.innerHeight;
    
    // Create background camera (wider FOV to cover entire viewport)
    backgroundCamera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    backgroundCamera.position.set(0, 1, 5);
    backgroundCamera.lookAt(0, 1, 0);
    
    // Create background renderer
    backgroundRenderer = new THREE.WebGLRenderer({ 
        alpha: true, 
        antialias: true,
        powerPreference: "high-performance"
    });
    backgroundRenderer.setSize(width, height);
    backgroundRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    
    // Add renderer to background container
    backgroundContainer.appendChild(backgroundRenderer.domElement);
    
    // Add lighting to background scene
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    backgroundScene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.6);
    directionalLight.position.set(5, 10, 5);
    backgroundScene.add(directionalLight);
    
    // Create a transparent overlay for background controls - positioned above everything
    const backgroundControlElement = document.createElement('div');
    backgroundControlElement.id = 'background-control-overlay';
    backgroundControlElement.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 999;
        pointer-events: none;
        background: transparent;
    `;
    document.body.appendChild(backgroundControlElement);
    
    // Enable orbit controls for background - attach to the dummy element
    backgroundControls = new OrbitControls(backgroundCamera, backgroundControlElement);
    backgroundControls.enabled = false; // Will be manually controlled
    backgroundControls.enableDamping = true;
    backgroundControls.dampingFactor = 0.05;
    backgroundControls.minDistance = 3;
    backgroundControls.maxDistance = 20;
    backgroundControls.target.set(0, 1, 0);
    backgroundControls.update();
    
    // Enable pointer events on background canvas (for rendering only)
    backgroundRenderer.domElement.style.pointerEvents = 'none';
    
    // Manual mouse event handling for background controls
    let isBackgroundDragging = false;
    let lastMouseX = 0;
    let lastMouseY = 0;
    let backgroundMouseDown = false;
    let backgroundMouseStartX = 0;
    let backgroundMouseStartY = 0;
    
    // Initialize spherical coordinates from initial camera position (use global variable)
    backgroundSpherical = new THREE.Spherical();
    const initialOffset = new THREE.Vector3().subVectors(backgroundCamera.position, backgroundControls.target);
    backgroundSpherical.setFromVector3(initialOffset);
    
    // Use raycasting to detect if mouse is over the actual avatar 3D object
    const getIsOverAvatar = (x, y) => {
        if (!avatarObject || !renderer || !camera || !scene) return false;
        
        // Get the avatar canvas element
        const avatarCanvas = renderer.domElement;
        const rect = avatarCanvas.getBoundingClientRect();
        
        // Check if mouse is within the avatar canvas bounds
        if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
            return false;
        }
        
        // Convert mouse position to normalized device coordinates
        const mouse = new THREE.Vector2();
        mouse.x = ((x - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((y - rect.top) / rect.height) * 2 + 1;
        
        // Perform raycasting
        const raycaster = new THREE.Raycaster();
        raycaster.setFromCamera(mouse, camera);
        
        // Check intersection with avatar object
        const intersects = raycaster.intersectObject(avatarObject, true);
        
        // Return true if ray hits the avatar
        return intersects.length > 0;
    };
    
    const getIsOverInteractiveChatElement = (x, y) => {
        // Check if mouse is over interactive chat elements (buttons, inputs, etc.)
        const element = document.elementFromPoint(x, y);
        if (!element) return false;
        
        // Check if it's a scrollable element (chat messages area)
        const chatMessages = element.closest('.chat-messages');
        if (chatMessages) {
            // Check if the element is scrollable and has scroll content
            const hasScroll = chatMessages.scrollHeight > chatMessages.clientHeight;
            if (hasScroll) {
                // Check if mouse is over the scrollbar or scrollable content
                const rect = chatMessages.getBoundingClientRect();
                const scrollbarWidth = chatMessages.offsetWidth - chatMessages.clientWidth;
                const isOverScrollbar = x > rect.right - scrollbarWidth - 10; // 10px tolerance
                
                // If over scrollable content (not scrollbar), allow scrolling
                if (!isOverScrollbar) {
                    return true; // Block background zoom when scrolling chat
                }
            }
        }
        
        // Only block if it's actually an interactive element that needs clicking
        const interactiveSelectors = [
            'input', 'button', 'textarea', 'select', 'a',
            '.btn', '.form-control', '[onclick]', '[role="button"]',
            '.chat-messages', '.message-bubble'
        ];
        
        // Check if element or its parent is interactive
        let current = element;
        while (current && current !== document.body) {
            for (const selector of interactiveSelectors) {
                if (current.matches && current.matches(selector)) {
                    return true;
                }
            }
            // Check if it has click handlers
            if (current.onclick || current.getAttribute('onclick')) {
                return true;
            }
            current = current.parentElement;
        }
        
        return false;
    };
    
    // Background is now static - disable all movement controls
    // Manual camera control for background - DISABLED (background is static)
    document.addEventListener('mousedown', (e) => {
        // Background is static, so we don't handle background dragging anymore
        // Only check for avatar or chat interactions
        if (getIsOverAvatar(e.clientX, e.clientY)) {
            return; // Let avatar handle it
        }
        
        if (getIsOverInteractiveChatElement(e.clientX, e.clientY)) {
            return; // Let chat handle it
        }
        
        // Background is static - no dragging
    });
    
    document.addEventListener('mousemove', (e) => {
        // Background is static - no dragging
        // Only update cursor based on position
        if (getIsOverAvatar(e.clientX, e.clientY)) {
            document.body.style.cursor = '';
            return;
        }
        
        if (getIsOverInteractiveChatElement(e.clientX, e.clientY)) {
            document.body.style.cursor = '';
            return;
        }
        
        const element = document.elementFromPoint(e.clientX, e.clientY);
        if (element) {
            const chatSection = element.closest('.chat-section');
            const avatarSection = element.closest('.avatar-section');
            
            if (chatSection || avatarSection) {
                document.body.style.cursor = '';
                return;
            }
        }
        
        // Over empty space - default cursor (background is static)
        document.body.style.cursor = '';
    });
    
    document.addEventListener('mouseup', (e) => {
        // Background is static - no dragging to stop
        // Just update cursor
        if (getIsOverAvatar(e.clientX, e.clientY)) {
            document.body.style.cursor = '';
        } else if (getIsOverInteractiveChatElement(e.clientX, e.clientY)) {
            document.body.style.cursor = '';
        } else {
            document.body.style.cursor = '';
        }
    });
    
    // Handle wheel for zooming - DISABLED (background is static)
    document.addEventListener('wheel', (e) => {
        // Background is static - no zooming
        // Only check if over avatar for avatar zoom
        if (getIsOverAvatar(e.clientX, e.clientY)) {
            return; // Let avatar handle it
        }
        
        // Check if over chat interface - allow scrolling
        const element = document.elementFromPoint(e.clientX, e.clientY);
        if (element) {
            const chatSection = element.closest('.chat-section');
            const chatMessages = element.closest('.chat-messages');
            
            if (chatSection || chatMessages) {
                if (chatMessages) {
                    const hasScroll = chatMessages.scrollHeight > chatMessages.clientHeight;
                    if (hasScroll) {
                        // Allow scrolling in chat
                        return;
                    }
                }
                return;
            }
        }
        
        // Background is static - do nothing
    });
    
    
    console.log('[NATURAL-AVATAR] ✅ Background scene initialized with controls');
    return true;
}

// Load office background
function loadOfficeBackground() {
    console.log('[NATURAL-AVATAR] Loading office background...');
    
    // Initialize background scene if not already done
    if (!backgroundScene) {
        if (!initBackgroundScene()) {
            console.warn('[NATURAL-AVATAR] ⚠️ Could not initialize background scene');
            return;
        }
    }
    
    const loader = new GLTFLoader();
    const backgroundPath = '/static/avatars/modern_office.glb';
    
    loader.load(
        backgroundPath,
        function (gltf) {
            console.log('[NATURAL-AVATAR] ✅ Office background loaded successfully!');
            
            backgroundObject = gltf.scene;
            
            // Scale and position the background appropriately
            const box = new THREE.Box3().setFromObject(backgroundObject);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            
            // Scale to fit nicely in the background
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 15 / maxDim; // Adjust scale as needed
            backgroundObject.scale.multiplyScalar(scale);
            
            // Position the background - center it and rotate to face forward
            backgroundObject.position.x = -center.x * scale;
            backgroundObject.position.y = -center.y * scale;
            backgroundObject.position.z = -center.z * scale - 3; // Move back
            
            // Rotate background 270 degrees in XZ plane (around Y-axis) - 90 + 90 + 90
            backgroundObject.rotation.y = (3 * Math.PI) / 2; // 270 degrees in radians
            
            // Add to background scene
            backgroundScene.add(backgroundObject);
            
            // Position camera to view the background correctly - lower and zoomed out more
            backgroundCamera.position.set(0, 0.8, 7); // Lower Y (0.8) and zoomed out more Z (7 instead of 5.5)
            backgroundCamera.lookAt(0, 0.5, 0); // Look at lower point
            backgroundControls.target.set(0, 0.5, 0); // Target lower point
            backgroundControls.update();
            
            // Update spherical coordinates (only if backgroundSpherical is initialized)
            if (backgroundSpherical) {
                const initialOffset = new THREE.Vector3().subVectors(backgroundCamera.position, backgroundControls.target);
                backgroundSpherical.setFromVector3(initialOffset);
            }
            
            console.log('[NATURAL-AVATAR] Office background positioned');
            
            // Start rendering background
            if (!isAnimating) {
                animate();
            }
        },
        function (xhr) {
            const progress = (xhr.loaded / xhr.total) * 100;
            console.log('[NATURAL-AVATAR] Loading office background...', progress.toFixed(0) + '%');
        },
        function (error) {
            console.warn('[NATURAL-AVATAR] ⚠️ Could not load office background:', error);
            // Don't show error to user, just continue without background
        }
    );
}

// Load GLTF avatar
function loadAvatar() {
    console.log('[NATURAL-AVATAR] Loading avatar...');
    
    const loader = new GLTFLoader();
    const avatarPath = '/static/avatars/avatar.glb';
    
    loader.load(
        avatarPath,
        function (gltf) {
            console.log('[NATURAL-AVATAR] ✅ Avatar loaded successfully!');
            
            avatarObject = gltf.scene;
            scene.add(avatarObject);
            
            // FIX MATERIALS: Prevent bright white artifacts
            avatarObject.traverse((child) => {
                if (child.isMesh) {
                    console.log('[NATURAL-AVATAR] Processing material for:', child.name);
                    
                    // Fix material properties to prevent overexposure
                    if (child.material) {
                        // Handle array of materials
                        const materials = Array.isArray(child.material) ? child.material : [child.material];
                        
                        materials.forEach(mat => {
                            // Reset emissive to prevent glow/brightness
                            if (mat.emissive) {
                                mat.emissive.setHex(0x000000);
                                mat.emissiveIntensity = 0;
                            }
                            
                            // Normalize roughness and metalness
                            if (mat.roughness !== undefined) mat.roughness = Math.min(mat.roughness, 0.9);
                            if (mat.metalness !== undefined) mat.metalness = Math.min(mat.metalness, 0.1);
                            
                            // Ensure proper color rendering
                            if (mat.color) {
                                // Clamp color values to prevent overexposure
                                mat.color.r = Math.min(mat.color.r, 1.0);
                                mat.color.g = Math.min(mat.color.g, 1.0);
                                mat.color.b = Math.min(mat.color.b, 1.0);
                            }
                            
                            // Force material update
                            mat.needsUpdate = true;
                        });
                        
                        console.log('[NATURAL-AVATAR] ✅ Fixed material for:', child.name);
                    }
                }
                
                // Check for skeleton
                if (child.isSkinnedMesh) {
                    console.log('[NATURAL-AVATAR] Found SkinnedMesh:', child.name);
                    if (child.skeleton && !avatarSkeleton) {
                        avatarSkeleton = child.skeleton;
                        console.log('[NATURAL-AVATAR] Skeleton bones:', child.skeleton.bones.length);
                    }
                }
            });
            
            // Setup animation mixer - COMPLETELY DISABLED
            if (gltf.animations && gltf.animations.length > 0) {
                console.log('[NATURAL-AVATAR] Found', gltf.animations.length, 'animations - COMPLETELY DISABLED');
                gltf.animations = []; // Clear all animations
            }
            mixer = null; // Ensure no mixer
            
            // Find bones
            findAvatarBones(avatarObject);
            
            // Set to natural standing pose
            setNaturalStandingPose();
            
            // Center and scale
            const box = new THREE.Box3().setFromObject(avatarObject);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 3 / maxDim;
            avatarObject.scale.multiplyScalar(scale);
            
            baseScaleY = avatarObject.scale.y;
            
            // Calculate floor level (minimum Y of bounding box after scaling)
            const floorLevel = box.min.y * scale;
            avatarObject.position.x = -center.x * scale;
            avatarObject.position.y = -floorLevel; // Stand on floor (Y=0)
            avatarObject.position.z = -center.z * scale;
            
            // Face forward
            avatarObject.rotation.y = Math.PI;
            
            console.log('[NATURAL-AVATAR] Avatar positioned');
            
            avatarLoaded = true;
            
            // Hide fallback avatar completely (the circle with eyes)
            if (fallbackElement) {
                fallbackElement.style.display = 'none';
                fallbackElement.style.visibility = 'hidden';
                fallbackElement.style.opacity = '0';
                fallbackElement.style.pointerEvents = 'none';
            }
            
            if (renderer && renderer.domElement) {
                renderer.domElement.style.display = 'block';
            }
            
            updateStatus('Avatar ready!');
            
            if (!isAnimating) {
                animate();
            }
            
            // Setup mouse tracking
            setupMouseTracking();
            
            // Start limited idle behaviors
            startLimitedIdleBehaviors();
            
            window.dispatchEvent(new CustomEvent('avatarLoaded'));
        },
        function (xhr) {
            const progress = (xhr.loaded / xhr.total) * 100;
            updateStatus(`Loading avatar... ${progress.toFixed(0)}%`);
        },
        function (error) {
            console.error('[NATURAL-AVATAR] ❌ Error:', error);
            updateStatus('Error loading avatar');
            if (fallbackElement) fallbackElement.style.display = 'flex';
        }
    );
}

// Set natural standing pose - arms down
function setNaturalStandingPose() {
    console.log('[T-POSE-FIX] 🎯 Applying VRM A-SHAPE POSE (Official VRM Pose Data)...');
    
    // CRITICAL: List ALL bones to find the exact arm bone names
    if (avatarSkeleton) {
        console.log('[T-POSE-FIX] 📋 ALL SKELETON BONES:');
        avatarSkeleton.bones.forEach((bone, index) => {
            const isArmBone = bone.name.toLowerCase().includes('arm') || 
                              bone.name.toLowerCase().includes('shoulder') ||
                              bone.name.toLowerCase().includes('clavicle');
            if (isArmBone) {
                console.log(`[T-POSE-FIX]   ${index}: ${bone.name} ⭐ (ARM-RELATED)`);
            }
        });
    }
    
    // STRATEGY: Use exact VRM A-shape pose quaternions from official VRM pose library
    // This is the standard "arms down" pose for VRM avatars
    
    if (avatarBones.rightArm) {
        console.log('[T-POSE-FIX] 🔍 Right arm bone name:', avatarBones.rightArm.name);
        console.log('[T-POSE-FIX] Right arm BEFORE:', {
            x: avatarBones.rightArm.rotation.x.toFixed(3),
            y: avatarBones.rightArm.rotation.y.toFixed(3),
            z: avatarBones.rightArm.rotation.z.toFixed(3)
        });
        
        // Store original for reference
        originalArmRotations.rightArm = avatarBones.rightArm.rotation.x;
        
        // VRM A-SHAPE POSE: Use exact quaternion from VRM A-shape pose data
        // rightUpperArm: [x, y, z, w] = [0, 0, -0.4235327838350045, 0.905880776381181]
        const quatRight = new THREE.Quaternion(
            0,                      // x
            0,                      // y
            -0.4235327838350045,    // z (negative for right arm)
            0.905880776381181       // w
        );
        avatarBones.rightArm.quaternion.copy(quatRight);
        
        // Force update
        avatarBones.rightArm.updateMatrix();
        avatarBones.rightArm.updateMatrixWorld(true);
        
        // CRITICAL: Force skeleton update immediately
        updateSkeleton();
        
        console.log('[T-POSE-FIX] Right arm AFTER (VRM A-shape quaternion):', {
            x: avatarBones.rightArm.rotation.x.toFixed(3),
            y: avatarBones.rightArm.rotation.y.toFixed(3),
            z: avatarBones.rightArm.rotation.z.toFixed(3)
        });
        console.log('[T-POSE-FIX] ✅ Right arm VRM A-shape applied & skeleton updated');
    } else {
        console.error('[T-POSE-FIX] ❌ Right arm bone NOT FOUND!');
    }
    
    if (avatarBones.leftArm) {
        console.log('[T-POSE-FIX] 🔍 Left arm bone name:', avatarBones.leftArm.name);
        console.log('[T-POSE-FIX] Left arm BEFORE:', {
            x: avatarBones.leftArm.rotation.x.toFixed(3),
            y: avatarBones.leftArm.rotation.y.toFixed(3),
            z: avatarBones.leftArm.rotation.z.toFixed(3)
        });
        
        // Store original for reference
        originalArmRotations.leftArm = avatarBones.leftArm.rotation.x;
        
        // VRM A-SHAPE POSE: Use exact quaternion from VRM A-shape pose data
        // leftUpperArm: [x, y, z, w] = [0, 0, 0.42669474387529654, 0.904395707392066]
        const quatLeft = new THREE.Quaternion(
            0,                      // x
            0,                      // y
            0.42669474387529654,    // z (positive for left arm)
            0.904395707392066       // w
        );
        avatarBones.leftArm.quaternion.copy(quatLeft);
        
        // Force update
        avatarBones.leftArm.updateMatrix();
        avatarBones.leftArm.updateMatrixWorld(true);
        
        // CRITICAL: Force skeleton update immediately
        updateSkeleton();
        
        console.log('[T-POSE-FIX] Left arm AFTER (VRM A-shape quaternion):', {
            x: avatarBones.leftArm.rotation.x.toFixed(3),
            y: avatarBones.leftArm.rotation.y.toFixed(3),
            z: avatarBones.leftArm.rotation.z.toFixed(3)
        });
        console.log('[T-POSE-FIX] ✅ Left arm VRM A-shape applied & skeleton updated');
    } else {
        console.error('[T-POSE-FIX] ❌ Left arm bone NOT FOUND!');
    }
    
    // Shoulders - VRM A-shape pose quaternions
    if (avatarBones.rightShoulder) {
        // rightShoulder: [x, y, z, w] = [0, 0, -0.08027473717361218, 0.9967727757978284]
        const quatRightShoulder = new THREE.Quaternion(
            0,
            0,
            -0.08027473717361218,
            0.9967727757978284
        );
        avatarBones.rightShoulder.quaternion.copy(quatRightShoulder);
        avatarBones.rightShoulder.updateMatrix();
        avatarBones.rightShoulder.updateMatrixWorld(true);
        console.log('[T-POSE-FIX] ✅ Right shoulder VRM A-shape applied');
    }
    
    if (avatarBones.leftShoulder) {
        // leftShoulder: [x, y, z, w] = [0, 0, 0.08532541830751879, 0.9963531366893201]
        const quatLeftShoulder = new THREE.Quaternion(
            0,
            0,
            0.08532541830751879,
            0.9963531366893201
        );
        avatarBones.leftShoulder.quaternion.copy(quatLeftShoulder);
        avatarBones.leftShoulder.updateMatrix();
        avatarBones.leftShoulder.updateMatrixWorld(true);
        console.log('[T-POSE-FIX] ✅ Left shoulder VRM A-shape applied');
    }
    
    // Forearms - slight bend for natural look
    if (avatarBones.rightForearm) {
        avatarBones.rightForearm.rotation.order = 'XYZ';
        avatarBones.rightForearm.rotation.x = -0.1;  // Slight bend
        avatarBones.rightForearm.rotation.y = 0;
        avatarBones.rightForearm.rotation.z = 0;
        avatarBones.rightForearm.updateMatrix();
        avatarBones.rightForearm.updateMatrixWorld(true);
    }
    
    if (avatarBones.leftForearm) {
        avatarBones.leftForearm.rotation.order = 'XYZ';
        avatarBones.leftForearm.rotation.x = -0.1;   // Slight bend
        avatarBones.leftForearm.rotation.y = 0;
        avatarBones.leftForearm.rotation.z = 0;
        avatarBones.leftForearm.updateMatrix();
        avatarBones.leftForearm.updateMatrixWorld(true);
    }
    
    // Relaxed hands
    if (avatarBones.rightHand) {
        avatarBones.rightHand.rotation.order = 'XYZ';
        avatarBones.rightHand.rotation.x = 0;
        avatarBones.rightHand.rotation.y = 0;
        avatarBones.rightHand.rotation.z = 0;
        avatarBones.rightHand.updateMatrix();
    }
    
    if (avatarBones.leftHand) {
        avatarBones.leftHand.rotation.order = 'XYZ';
        avatarBones.leftHand.rotation.x = 0;
        avatarBones.leftHand.rotation.y = 0;
        avatarBones.leftHand.rotation.z = 0;
        avatarBones.leftHand.updateMatrix();
    }
    
    // FINAL UPDATE: Force complete skeleton update for ALL bones
    console.log('[T-POSE-FIX] 🔄 Forcing FINAL skeleton update for all meshes...');
    updateSkeleton();
    
    // Extra: Force render update
    if (renderer && scene && camera) {
        renderer.render(scene, camera);
        console.log('[T-POSE-FIX] 🎨 Forced render update');
    }
    
    console.log('[T-POSE-FIX] ✅ VRM A-SHAPE POSE APPLIED - Arms should be down naturally!');
}

// Find avatar bones
function findAvatarBones(object) {
    console.log('[NATURAL-AVATAR] Scanning for bones...');
    
    let skeletonBones = [];
    object.traverse((child) => {
        if (child.isSkinnedMesh && child.skeleton) {
            skeletonBones = child.skeleton.bones;
        }
    });
    
    function processBone(bone) {
        const name = bone.name.toLowerCase();
        
        if (name.includes('head') || name.includes('neck')) {
            avatarBones.head = bone;
        }
        if (name.includes('spine') && !avatarBones.spine) {
            avatarBones.spine = bone;
        }
        // VRoid/VRM naming: J_Bip_L_UpperArm, J_Bip_L_LowerArm, etc.
        if (name.includes('l_upperarm') || name.includes('leftarm') || name.includes('j_bip_l_upperarm')) {
            avatarBones.leftArm = bone;
        }
        if (name.includes('l_lowerarm') || name.includes('l_forearm') || name.includes('leftforearm') || name.includes('j_bip_l_lowerarm')) {
            avatarBones.leftForearm = bone;
        }
        if (name.includes('l_hand') || name.includes('lefthand') || name.includes('j_bip_l_hand')) {
            avatarBones.leftHand = bone;
        }
        if (name.includes('l_shoulder') || name.includes('leftshoulder') || name.includes('j_bip_l_shoulder') || name.includes('j_bip_l_clavicle')) {
            avatarBones.leftShoulder = bone;
        }
        // VRoid/VRM naming: J_Bip_R_UpperArm, J_Bip_R_LowerArm, etc.
        if (name.includes('r_upperarm') || name.includes('rightarm') || name.includes('j_bip_r_upperarm')) {
            avatarBones.rightArm = bone;
        }
        if (name.includes('r_lowerarm') || name.includes('r_forearm') || name.includes('rightforearm') || name.includes('j_bip_r_lowerarm')) {
            avatarBones.rightForearm = bone;
        }
        if (name.includes('r_hand') || name.includes('righthand') || name.includes('j_bip_r_hand')) {
            avatarBones.rightHand = bone;
        }
        if (name.includes('r_shoulder') || name.includes('rightshoulder') || name.includes('j_bip_r_shoulder') || name.includes('j_bip_r_clavicle')) {
            avatarBones.rightShoulder = bone;
        }
    }
    
    // IMPORTANT: Use bones directly from skeleton array to ensure we modify the actual bones
    if (skeletonBones.length > 0) {
        skeletonBones.forEach(processBone);
        
        // Verify bones are actually from skeleton and re-assign if needed
        if (avatarSkeleton) {
            const skeletonBoneNames = avatarSkeleton.bones.map(b => b.name);
            
            // Re-assign bones from skeleton to ensure exact references
            if (avatarBones.rightArm) {
                const skeletonBone = avatarSkeleton.bones.find(b => b.name === avatarBones.rightArm.name);
                if (skeletonBone && skeletonBone !== avatarBones.rightArm) {
                    console.log('[NATURAL-AVATAR] Re-assigning right arm bone from skeleton');
                    avatarBones.rightArm = skeletonBone;
                }
            }
            if (avatarBones.leftArm) {
                const skeletonBone = avatarSkeleton.bones.find(b => b.name === avatarBones.leftArm.name);
                if (skeletonBone && skeletonBone !== avatarBones.leftArm) {
                    console.log('[NATURAL-AVATAR] Re-assigning left arm bone from skeleton');
                    avatarBones.leftArm = skeletonBone;
                }
            }
        }
    } else {
        object.traverse((child) => {
            if (child.isBone || child.type === 'Bone') {
                processBone(child);
            }
        });
    }
    
    console.log('[NATURAL-AVATAR] Bones found:', {
        head: !!avatarBones.head,
        spine: !!avatarBones.spine,
        rightArm: !!avatarBones.rightArm,
        leftArm: !!avatarBones.leftArm,
        rightForearm: !!avatarBones.rightForearm,
        leftForearm: !!avatarBones.leftForearm,
        rightHand: !!avatarBones.rightHand,
        leftHand: !!avatarBones.leftHand
    });
    
    // Debug: Log actual bone names found
    if (avatarBones.rightArm) {
        console.log('[NATURAL-AVATAR] Right arm bone name:', avatarBones.rightArm.name);
        console.log('[NATURAL-AVATAR] Right arm bone parent:', avatarBones.rightArm.parent ? avatarBones.rightArm.parent.name : 'none');
        console.log('[NATURAL-AVATAR] Right arm initial rotation:', {
            x: avatarBones.rightArm.rotation.x,
            y: avatarBones.rightArm.rotation.y,
            z: avatarBones.rightArm.rotation.z
        });
    }
    if (avatarBones.leftArm) {
        console.log('[NATURAL-AVATAR] Left arm bone name:', avatarBones.leftArm.name);
        console.log('[NATURAL-AVATAR] Left arm initial rotation:', {
            x: avatarBones.leftArm.rotation.x,
            y: avatarBones.leftArm.rotation.y,
            z: avatarBones.leftArm.rotation.z
        });
    }
}

// Setup mouse tracking
function setupMouseTracking() {
    renderer.domElement.addEventListener('mousemove', (event) => {
        if (!isDragging) {
            const rect = renderer.domElement.getBoundingClientRect();
            mousePosition.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            mousePosition.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        }
    });
    
    console.log('[NATURAL-AVATAR] ✅ Mouse tracking enabled');
}

// Start limited idle behaviors - only 2-3 actions
function startLimitedIdleBehaviors() {
    // Action 1: Subtle nod (every 8-12 seconds)
    setInterval(() => {
        if (!isSpeaking && Math.random() > 0.5) {
            subtleNod();
        }
    }, 8000 + Math.random() * 4000);
    
    // Action 2: Slight head tilt (every 10-15 seconds)
    setInterval(() => {
        if (!isSpeaking && Math.random() > 0.4) {
            subtleHeadTilt();
        }
    }, 10000 + Math.random() * 5000);
    
    // Action 3: Gentle wave (every 15-20 seconds)
    setInterval(() => {
        if (!isSpeaking && Math.random() > 0.6) {
            gentleWave();
        }
    }, 15000 + Math.random() * 5000);
    
    // Face Expression 1: Blink (every 3-5 seconds)
    setInterval(() => {
        if (!isSpeaking) {
            blinkExpression();
        }
    }, 3000 + Math.random() * 2000);
    
    // Face Expression 2: Smile (every 12-18 seconds)
    setInterval(() => {
        if (!isSpeaking && Math.random() > 0.5) {
            smileExpression();
        }
    }, 12000 + Math.random() * 6000);
    
    console.log('[NATURAL-AVATAR] ✅ Limited idle behaviors started');
}

// Action 1: Subtle nod
function subtleNod() {
    if (!avatarBones.head) return;
    
    const originalX = avatarBones.head.rotation.x;
    animateProperty(avatarBones.head.rotation, 'x', originalX, originalX - 0.15, 300, () => {
        animateProperty(avatarBones.head.rotation, 'x', originalX - 0.15, originalX, 300);
    });
}

// Action 2: Subtle head tilt
function subtleHeadTilt() {
    if (!avatarBones.head) return;
    
    const originalZ = avatarBones.head.rotation.z;
    const tiltAmount = (Math.random() - 0.5) * 0.2;
    animateProperty(avatarBones.head.rotation, 'z', originalZ, originalZ + tiltAmount, 600, () => {
        setTimeout(() => {
            animateProperty(avatarBones.head.rotation, 'z', avatarBones.head.rotation.z, originalZ, 600);
        }, 1500);
    });
}

// Action 3: Gentle wave
function gentleWave() {
    if (!avatarBones.rightArm) return;
    
    const arm = avatarBones.rightArm;
    const originalX = arm.rotation.x;
    
    // Raise arm slightly
    animateProperty(arm.rotation, 'x', originalX, -0.5, 400, () => {
        // Small wave motion
        let waveCount = 0;
        const waveInterval = setInterval(() => {
            waveCount++;
            const direction = waveCount % 2 === 0 ? 1 : -1;
            animateProperty(arm.rotation, 'z', arm.rotation.z, arm.rotation.z + direction * 0.3, 200);
            
            if (waveCount >= 2) {
                clearInterval(waveInterval);
                setTimeout(() => {
                    animateProperty(arm.rotation, 'x', arm.rotation.x, originalX, 400);
                    animateProperty(arm.rotation, 'z', arm.rotation.z, 0, 400);
                }, 300);
            }
        }, 350);
    });
}

// Face Expression 1: Blink
function blinkExpression() {
    avatarObject.traverse((child) => {
        if (child.isMesh && child.morphTargetDictionary) {
            const eyeTargets = ['eyeClose', 'EyeClose', 'Blink', 'blink'];
            for (const targetName of eyeTargets) {
                const index = child.morphTargetDictionary[targetName];
                if (index !== undefined) {
                    animateProperty(child.morphTargetInfluences, index, 0, 1, 80, () => {
                        animateProperty(child.morphTargetInfluences, index, 1, 0, 80);
                    });
                    return;
                }
            }
        }
    });
}

// Face Expression 2: Smile
function smileExpression() {
    avatarObject.traverse((child) => {
        if (child.isMesh && child.morphTargetDictionary) {
            const smileTargets = ['smile', 'Smile', 'happy', 'Happy'];
            for (const targetName of smileTargets) {
                const index = child.morphTargetDictionary[targetName];
                if (index !== undefined) {
                    animateProperty(child.morphTargetInfluences, index, 0, 0.6, 400, () => {
                        setTimeout(() => {
                            animateProperty(child.morphTargetInfluences, index, 0.6, 0, 400);
                        }, 1500);
                    });
                    return;
                }
            }
        }
    });
}

// Smooth animation helper
function animateProperty(object, property, from, to, duration, onComplete) {
    const startTime = Date.now();
    
    function update() {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const eased = progress < 0.5
            ? 2 * progress * progress
            : -1 + (4 - 2 * progress) * progress;
        
        object[property] = from + (to - from) * eased;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else if (onComplete) {
            onComplete();
        }
    }
    
    update();
}

// Update skeleton - CRITICAL for bone transformations to be visible
function updateSkeleton() {
    if (!avatarSkeleton) {
        console.warn('[NATURAL-AVATAR] ⚠️ No skeleton to update');
        return;
    }
    
    // First, update all bone local matrices
    avatarSkeleton.bones.forEach(bone => {
        bone.updateMatrix();
    });
    
    // Find root bone (usually named "Root" or first bone without bone parent)
    let rootBone = avatarSkeleton.bones.find(b => 
        b.name === 'Root' || 
        !b.parent || 
        (!b.parent.isBone && b.parent.type !== 'Bone')
    );
    
    if (!rootBone && avatarSkeleton.bones.length > 0) {
        rootBone = avatarSkeleton.bones[0];
    }
    
    // Update world matrices from root (updates entire hierarchy)
    if (rootBone) {
        rootBone.updateMatrixWorld(true); // true = recursively update children
    } else {
        // Fallback: update all bones
        avatarSkeleton.bones.forEach(bone => {
            bone.updateMatrixWorld(true);
        });
    }
    
    // CRITICAL: Update skeleton for all SkinnedMeshes
    // This copies bone.matrixWorld to skeleton.boneMatrices array used by GPU shaders
    let updated = false;
    avatarObject.traverse((child) => {
        if (child.isSkinnedMesh && child.skeleton) {
            // Force update all bone world matrices before skeleton update
            child.skeleton.bones.forEach(bone => {
                bone.updateMatrixWorld(true);
            });
            // Update skeleton - this copies bone.matrixWorld to GPU shader uniforms
            child.skeleton.update(); // This is what makes the changes visible!
            updated = true;
        }
    });
    
    if (!updated) {
        console.warn('[NATURAL-AVATAR] ⚠️ No SkinnedMesh found to update skeleton!');
    }
}

// Main animation loop
function animate() {
    if (!isAnimating) {
        isAnimating = true;
        console.log('[NATURAL-AVATAR] Animation loop started');
    }
    
    requestAnimationFrame(animate);
    
    const time = Date.now() * 0.001;
    
    // Update orbit controls
    if (controls) {
        controls.update();
    }
    
    // DO NOT update mixer - it will play animations that override our bone rotations
    // if (mixer) {
    //     mixer.update(0.016);
    // }
    
    if (avatarObject && avatarLoaded) {
        // CONTINUOUS T-POSE FIX: Enforce VRM A-shape pose every frame
        let armUpdated = false;
        if (avatarBones.rightArm) {
            // VRM A-shape quaternion for right arm
            const quatRight = new THREE.Quaternion(0, 0, -0.4235327838350045, 0.905880776381181);
            avatarBones.rightArm.quaternion.copy(quatRight);
            avatarBones.rightArm.updateMatrix();
            avatarBones.rightArm.updateMatrixWorld(true);
            armUpdated = true;
        }
        if (avatarBones.leftArm) {
            // VRM A-shape quaternion for left arm
            const quatLeft = new THREE.Quaternion(0, 0, 0.42669474387529654, 0.904395707392066);
            avatarBones.leftArm.quaternion.copy(quatLeft);
            avatarBones.leftArm.updateMatrix();
            avatarBones.leftArm.updateMatrixWorld(true);
            armUpdated = true;
        }
        
        // Also enforce shoulder positions
        if (avatarBones.rightShoulder) {
            const quatRightShoulder = new THREE.Quaternion(0, 0, -0.08027473717361218, 0.9967727757978284);
            avatarBones.rightShoulder.quaternion.copy(quatRightShoulder);
            avatarBones.rightShoulder.updateMatrix();
            avatarBones.rightShoulder.updateMatrixWorld(true);
            armUpdated = true;
        }
        if (avatarBones.leftShoulder) {
            const quatLeftShoulder = new THREE.Quaternion(0, 0, 0.08532541830751879, 0.9963531366893201);
            avatarBones.leftShoulder.quaternion.copy(quatLeftShoulder);
            avatarBones.leftShoulder.updateMatrix();
            avatarBones.leftShoulder.updateMatrixWorld(true);
            armUpdated = true;
        }
        
        // CRITICAL: Update skeleton every frame to reflect VRM A-shape pose
        if (armUpdated) {
            updateSkeleton();
        }
        
        // Breathing - faster when typing (excited)
        const breathingSpeed = isUserTyping ? 1.5 : 1.0;
        const breathingIntensity = isUserTyping ? 0.025 : 0.015;
        avatarObject.scale.y = baseScaleY * (1.0 + Math.sin(time * breathingSpeed) * breathingIntensity);
        
        // Head movement priority: typing (look at input) > speaking > cursor
        if (avatarBones.head) {
            if (isUserTyping) {
                // Look at input box with excited expression
                targetLookPosition.x = 0.3; // Look slightly to the right (where input box is)
                targetLookPosition.y = -0.15; // Look down toward input
                
                currentLookPosition.lerp(targetLookPosition, 0.12);
                
                avatarBones.head.rotation.y = currentLookPosition.x;
                avatarBones.head.rotation.x = -currentLookPosition.y;
                avatarBones.head.updateMatrix();
            } else if (isLookingAtMouse && avatarBones.head && !isSpeaking) {
                // Head follows cursor
                targetLookPosition.x = mousePosition.x * 0.4;
                targetLookPosition.y = mousePosition.y * 0.25;
                
                currentLookPosition.lerp(targetLookPosition, 0.08);
                
                avatarBones.head.rotation.y = currentLookPosition.x;
                avatarBones.head.rotation.x = -currentLookPosition.y;
                avatarBones.head.updateMatrix();
            }
        }
        
        // Keep arms down naturally - enforce natural standing pose (arms hanging down, not T-pose)
        if (avatarBones.rightArm && !isSpeaking) {
            // Re-get bone from skeleton to ensure we're modifying the actual bone
            let rightArmBone = avatarBones.rightArm;
            if (avatarSkeleton) {
                const skeletonBone = avatarSkeleton.bones.find(b => b.name === rightArmBone.name);
                if (skeletonBone) rightArmBone = skeletonBone;
            }
            
            rightArmBone.rotation.order = 'XYZ';
            // Natural hanging arm position: arms hanging down (not T-pose)
            // Use stored original T-pose rotation to calculate the correct offset
            const originalRot = originalArmRotations.rightArm !== null ? originalArmRotations.rightArm : Math.PI / 2;
            const tPoseOffset = originalRot > 0.5 ? originalRot : Math.PI / 2; // Assume T-pose if rotation is large
            const targetX = originalRot - tPoseOffset + 0.1; // Bring to 0 (arms down), then add slight forward tilt
            rightArmBone.rotation.x = targetX;
            rightArmBone.rotation.y = -0.15; // Slight inward rotation for natural arm position
            rightArmBone.rotation.z = 0.1; // Slight rotation for natural arm position
            
            // Update quaternion and matrix
            const euler = new THREE.Euler(targetX, -0.15, 0.1, 'XYZ');
            rightArmBone.quaternion.setFromEuler(euler);
            rightArmBone.updateMatrix();
            rightArmBone.updateMatrixWorld(true);
        }
        
        if (avatarBones.leftArm && !isSpeaking) {
            let leftArmBone = avatarBones.leftArm;
            if (avatarSkeleton) {
                const skeletonBone = avatarSkeleton.bones.find(b => b.name === leftArmBone.name);
                if (skeletonBone) leftArmBone = skeletonBone;
            }
            
            leftArmBone.rotation.order = 'XYZ';
            // Natural hanging arm position: arms hanging down (not T-pose)
            // Use stored original T-pose rotation to calculate the correct offset
            const originalRot = originalArmRotations.leftArm !== null ? originalArmRotations.leftArm : Math.PI / 2;
            const tPoseOffset = originalRot > 0.5 ? originalRot : Math.PI / 2; // Assume T-pose if rotation is large
            const targetX = originalRot - tPoseOffset + 0.1; // Bring to 0 (arms down), then add slight forward tilt
            leftArmBone.rotation.x = targetX;
            leftArmBone.rotation.y = 0.15; // Slight inward rotation for natural arm position
            leftArmBone.rotation.z = -0.1; // Slight rotation for natural arm position
            
            // Update quaternion and matrix
            const euler = new THREE.Euler(targetX, 0.15, -0.1, 'XYZ');
            leftArmBone.quaternion.setFromEuler(euler);
            leftArmBone.updateMatrix();
            leftArmBone.updateMatrixWorld(true);
        }
        
        // Keep forearms and hands still in natural position
        if (avatarBones.rightForearm && !isSpeaking) {
            avatarBones.rightForearm.rotation.x = 0.15; // Slight forward bend for natural arm position
            avatarBones.rightForearm.updateMatrix();
            avatarBones.rightForearm.updateMatrixWorld(true);
        }
        if (avatarBones.leftForearm && !isSpeaking) {
            avatarBones.leftForearm.rotation.x = 0.15; // Slight forward bend for natural arm position
            avatarBones.leftForearm.updateMatrix();
            avatarBones.leftForearm.updateMatrixWorld(true);
        }
        if (avatarBones.rightHand && !isSpeaking) {
            avatarBones.rightHand.rotation.x = 0;
            avatarBones.rightHand.rotation.y = 0;
            avatarBones.rightHand.rotation.z = 0;
            avatarBones.rightHand.updateMatrix();
        }
        if (avatarBones.leftHand && !isSpeaking) {
            avatarBones.leftHand.rotation.x = 0;
            avatarBones.leftHand.rotation.y = 0;
            avatarBones.leftHand.rotation.z = 0;
            avatarBones.leftHand.updateMatrix();
        }
        
        // Very subtle body sway
        if (avatarBones.spine) {
            const sway = Math.sin(time * 0.6) * 0.02;
            avatarBones.spine.rotation.y = sway;
            avatarBones.spine.updateMatrix();
        }
        
        // CRITICAL: Update skeleton every frame to make bone changes visible
        updateSkeleton();
    }
    
    renderer.render(scene, camera);
    
    // Render background scene if it exists
    if (backgroundScene && backgroundRenderer && backgroundCamera) {
        // Update background controls
        if (backgroundControls) {
            backgroundControls.update();
        }
        backgroundRenderer.render(backgroundScene, backgroundCamera);
    }
}

// Update status
function updateStatus(text) {
    const statusElement = document.getElementById('status-text');
    if (statusElement) {
        statusElement.textContent = text;
    }
}

// Handle resize
function handleResize() {
    if (!avatarContainer || !camera || !renderer) return;
    
    const width = avatarContainer.clientWidth;
    const height = avatarContainer.clientHeight || 500;
    
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
    
    // Resize background renderer
    if (backgroundRenderer && backgroundCamera) {
        const bgWidth = window.innerWidth;
        const bgHeight = window.innerHeight;
        
        backgroundCamera.aspect = bgWidth / bgHeight;
        backgroundCamera.updateProjectionMatrix();
        backgroundRenderer.setSize(bgWidth, bgHeight);
    }
}

// Reset avatar view
function resetAvatarView() {
    console.log('[NATURAL-AVATAR] Resetting avatar view...');
    
    if (controls && camera) {
        // Reset camera position
        camera.position.set(0, 0.8, 3.5); // Lower Y and slightly zoomed out
        camera.lookAt(0, 0.5, 0); // Look at lower point
        
        // Reset orbit controls - target lower point
        controls.target.set(0, 0.5, 0);
        controls.update();
    }
    
    // Reset avatar object position (will be recalculated based on center)
    if (avatarObject) {
        const box = new THREE.Box3().setFromObject(avatarObject);
        const center = box.getCenter(new THREE.Vector3());
        const scale = avatarObject.scale.x;
        
        // Calculate floor level (minimum Y of bounding box)
        const floorLevel = box.min.y * scale;
        avatarObject.position.x = -center.x * scale;
        avatarObject.position.y = -floorLevel; // Stand on floor
        avatarObject.position.z = -center.z * scale;
        avatarObject.rotation.y = Math.PI;
    }
    
    // Reset background view as well - lower and zoomed in
    if (backgroundControls && backgroundCamera) {
        backgroundCamera.position.set(0, 0.8, 7); // Lower Y and zoomed out more
        backgroundCamera.lookAt(0, 0.5, 0); // Look at lower point
        backgroundControls.target.set(0, 0.5, 0); // Target lower point
        backgroundControls.update();
    }
    
    console.log('[NATURAL-AVATAR] ✅ Avatar view reset');
}

// Set user typing state (called from chat.js)
function setUserTyping(typing) {
    isUserTyping = typing;
    console.log('[NATURAL-AVATAR] User typing:', typing);
}

// Set avatar speaking state (called from chat.js for voice)
function setAvatarSpeaking(speaking) {
    isSpeaking = speaking;
    console.log('[NATURAL-AVATAR] Avatar speaking:', speaking);
    
    if (speaking) {
        // Start speaking animation (subtle mouth movement, head movements)
        startSpeakingAnimation();
    } else {
        // Stop speaking animation
        stopSpeakingAnimation();
    }
}

// Start speaking animation
function startSpeakingAnimation() {
    if (!avatarObject || !avatarLoaded) return;
    
    // Subtle head movements while speaking
    if (avatarBones.head) {
        // Slight head nod and subtle movements
        const headAnimation = setInterval(() => {
            if (!isSpeaking) {
                clearInterval(headAnimation);
                return;
            }
            
            // Subtle head movements
            const randomX = (Math.random() - 0.5) * 0.05;
            const randomY = (Math.random() - 0.5) * 0.05;
            animateProperty(avatarBones.head.rotation, 'x', avatarBones.head.rotation.x, avatarBones.head.rotation.x + randomX, 200);
            animateProperty(avatarBones.head.rotation, 'y', avatarBones.head.rotation.y, avatarBones.head.rotation.y + randomY, 200);
        }, 500);
        
        // Store interval for cleanup
        if (!window.speakingAnimationInterval) {
            window.speakingAnimationInterval = headAnimation;
        }
    }
    
    // Mouth/lip sync animation (if morph targets available)
    avatarObject.traverse((child) => {
        if (child.isMesh && child.morphTargetDictionary) {
            const mouthTargets = ['mouthOpen', 'MouthOpen', 'Aa', 'aa', 'vocal', 'Vocal'];
            for (const targetName of mouthTargets) {
                const index = child.morphTargetDictionary[targetName];
                if (index !== undefined) {
                    // Subtle mouth opening animation
                    const mouthAnimation = setInterval(() => {
                        if (!isSpeaking) {
                            clearInterval(mouthAnimation);
                            animateProperty(child.morphTargetInfluences, index, child.morphTargetInfluences[index], 0, 200);
                            return;
                        }
                        
                        // Oscillate mouth opening
                        const target = 0.2 + Math.sin(Date.now() / 200) * 0.1;
                        animateProperty(child.morphTargetInfluences, index, child.morphTargetInfluences[index], target, 100);
                    }, 100);
                    
                    // Store interval for cleanup
                    if (!window.mouthAnimationInterval) {
                        window.mouthAnimationInterval = mouthAnimation;
                    }
                    return;
                }
            }
        }
    });
}

// Stop speaking animation
function stopSpeakingAnimation() {
    // Clear intervals
    if (window.speakingAnimationInterval) {
        clearInterval(window.speakingAnimationInterval);
        window.speakingAnimationInterval = null;
    }
    
    if (window.mouthAnimationInterval) {
        clearInterval(window.mouthAnimationInterval);
        window.mouthAnimationInterval = null;
    }
    
    // Reset head rotation to neutral
    if (avatarBones.head) {
        animateProperty(avatarBones.head.rotation, 'x', avatarBones.head.rotation.x, 0, 300);
        animateProperty(avatarBones.head.rotation, 'y', avatarBones.head.rotation.y, 0, 300);
        animateProperty(avatarBones.head.rotation, 'z', avatarBones.head.rotation.z, 0, 300);
    }
    
    // Reset mouth morph targets
    if (avatarObject) {
        avatarObject.traverse((child) => {
            if (child.isMesh && child.morphTargetDictionary) {
                const mouthTargets = ['mouthOpen', 'MouthOpen', 'Aa', 'aa', 'vocal', 'Vocal'];
                for (const targetName of mouthTargets) {
                    const index = child.morphTargetDictionary[targetName];
                    if (index !== undefined && child.morphTargetInfluences[index] > 0) {
                        animateProperty(child.morphTargetInfluences, index, child.morphTargetInfluences[index], 0, 200);
                    }
                }
            }
        });
    }
}

// Avatar speak function (for backward compatibility)
function avatarSpeak(duration) {
    if (!avatarObject || !avatarLoaded) return;
    
    isSpeaking = true;
    setAvatarSpeaking(true);
    
    // Stop speaking after duration
    setTimeout(() => {
        isSpeaking = false;
        setAvatarSpeaking(false);
    }, duration);
}

// Excitement jump animation when user sends message - small, subtle jump with hands down
function excitementJump() {
    if (!avatarObject || !avatarLoaded) return;
    
    console.log('[NATURAL-AVATAR] Performing subtle excitement jump!');
    
    // Get current Y position
    const originalY = avatarObject.position.y;
    
    // Small, subtle jump up (reduced from 0.8 to 0.15)
    animateProperty(avatarObject.position, 'y', originalY, originalY + 0.15, 150, () => {
        // Come back down smoothly
        animateProperty(avatarObject.position, 'y', originalY + 0.15, originalY, 150);
    });
    
    // Subtle head nod instead of shake
    if (avatarBones.head) {
        const originalHeadY = avatarBones.head.rotation.y;
        setTimeout(() => {
            // Small nod forward
            animateProperty(avatarBones.head.rotation, 'x', 0, 0.1, 100, () => {
                animateProperty(avatarBones.head.rotation, 'x', 0.1, 0, 100);
            });
        }, 75);
    }
    
    // Ensure hands stay down during jump
    if (avatarBones.rightArm) {
        // Keep arms straight down at sides
        avatarBones.rightArm.rotation.x = 0; // Arms straight down
        avatarBones.rightArm.rotation.y = 0;
        avatarBones.rightArm.rotation.z = 0;
        avatarBones.rightArm.updateMatrix();
    }
    if (avatarBones.leftArm) {
        avatarBones.leftArm.rotation.x = 0; // Arms straight down
        avatarBones.leftArm.rotation.y = 0;
        avatarBones.leftArm.rotation.z = 0;
        avatarBones.leftArm.updateMatrix();
    }
    
    // Subtle smile expression
    avatarObject.traverse((child) => {
        if (child.isMesh && child.morphTargetDictionary) {
            const smileTargets = ['smile', 'Smile', 'happy', 'Happy', 'joy', 'Joy'];
            for (const targetName of smileTargets) {
                const index = child.morphTargetDictionary[targetName];
                if (index !== undefined) {
                    // Subtle smile (reduced from 0.8 to 0.3)
                    animateProperty(child.morphTargetInfluences, index, 0, 0.3, 100, () => {
                        setTimeout(() => {
                            animateProperty(child.morphTargetInfluences, index, 0.3, 0, 150);
                        }, 100);
                    });
                    return;
                }
            }
        }
    });
}

// Initialize
function initializeAvatar() {
    console.log('[NATURAL-AVATAR] Initializing...');
    
    avatarContainer = document.getElementById('avatar-container');
    fallbackElement = document.getElementById('simple-avatar-fallback');
    
    if (!avatarContainer) {
        console.error('[NATURAL-AVATAR] ❌ Container not found');
        if (fallbackElement) fallbackElement.style.display = 'flex';
        return;
    }
    
    if (fallbackElement) {
        fallbackElement.style.display = 'flex';
    }
    
    updateStatus('Loading avatar...');
    
    if (initThreeScene()) {
        loadAvatar();
        loadOfficeBackground(); // Load background after avatar scene is ready
        window.addEventListener('resize', handleResize);
    } else {
        console.error('[NATURAL-AVATAR] Scene init failed');
        if (fallbackElement) fallbackElement.style.display = 'flex';
    }
}

// Start
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAvatar);
} else {
    initializeAvatar();
}

// Export functions
window.updateStatus = updateStatus;
window.resetAvatarView = resetAvatarView;
window.setUserTyping = setUserTyping;
window.setAvatarSpeaking = setAvatarSpeaking;
window.avatarSpeak = avatarSpeak;
window.excitementJump = excitementJump;

console.log('[NATURAL-AVATAR] Module loaded successfully!');