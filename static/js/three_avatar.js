// Use importmap for module resolution
// Import map should be defined in HTML before this script loads
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

let scene, camera, renderer, model, mixer;
let clock = new THREE.Clock();

function init() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
        return;
    }
    
    const container = document.getElementById('three-canvas-container');
    if (!container) {
        console.error("❌ Canvas container not found! Looking for element with id 'three-canvas-container'");
        // Show fallback avatar
        const fallback = document.getElementById('simple-avatar-fallback');
        if (fallback) {
            fallback.style.display = 'flex';
        }
        return;
    }
    
    // Ensure container has dimensions
    if (container.clientWidth === 0 || container.clientHeight === 0) {
        console.warn("⚠️ Container has zero dimensions:", container.clientWidth, "x", container.clientHeight);
        console.warn("⚠️ Waiting for layout...");
        // Check if avatar section is visible
        const avatarSection = container.closest('.avatar-section');
        if (avatarSection) {
            const display = window.getComputedStyle(avatarSection).display;
            console.log("📊 Avatar section display:", display);
            if (display === 'none') {
                console.warn("⚠️ Avatar section is hidden (might be on small screen < 992px)");
                // Show fallback avatar
                const fallback = document.getElementById('simple-avatar-fallback');
                if (fallback) {
                    fallback.style.display = 'flex';
                    console.log("✅ Showing fallback avatar");
                }
                return;
            }
        }
        // Retry after a delay
        setTimeout(init, 200);
        return;
    }
    
    console.log("✅ Container has dimensions:", container.clientWidth, "x", container.clientHeight);

    // 1. Setup Scene
    scene = new THREE.Scene();

    // 2. Setup Camera
    const width = container.clientWidth;
    const height = container.clientHeight;
    camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
    // Position camera to see avatar better
    camera.position.set(0, 1.4, 4.5);
    // Make camera look at the avatar (lower to match new position)
    camera.lookAt(0, 0.8, 0);

    // 3. Setup Renderer
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    // Use outputColorSpace for Three.js r150+ (outputEncoding is deprecated)
    if (renderer.outputColorSpace !== undefined) {
        renderer.outputColorSpace = THREE.SRGBColorSpace;
    } else {
        renderer.outputEncoding = THREE.sRGBEncoding; // Fallback for older versions
    }
    container.appendChild(renderer.domElement);

    // 4. Add Lights
    const ambient = new THREE.AmbientLight(0xffffff, 1.1);
    scene.add(ambient);
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.5);
    keyLight.position.set(2, 4, 5);
    scene.add(keyLight);

    // 5. Load Avatar Model
    const avatarPath = '/static/avatars/avatars.glb';
    console.log("🔄 Attempting to load avatar from:", avatarPath);
    console.log("🔄 Full URL would be:", window.location.origin + avatarPath);
    
    const loader = new GLTFLoader();
    loader.load(
        avatarPath,
        (gltf) => {
            console.log("✅ Avatar Loaded Successfully!");
            console.log("📦 Model info:", {
                animations: gltf.animations.length,
                scenes: gltf.scenes.length
            });
            model = gltf.scene;
            
            // Center & Scale
            const box = new THREE.Box3().setFromObject(model);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());

            // Center the model
            model.position.x = -center.x;
            model.position.y = -center.y;
            model.position.z = -center.z;
            
            // Move avatar down (lower position)
            model.position.y -= 0.2; // Move down from center
            
            // Rotate to face the user (camera is at z=4.5 looking at origin)
            // Camera is at positive Z, so avatar should face positive Z direction
            // If avatar is facing right (positive X), rotate -90 degrees
            // If avatar is facing left (negative X), rotate 90 degrees
            // If avatar is facing away (negative Z), rotate 180 degrees
            // Try rotating to face the camera (positive Z direction)
            model.rotation.y = -Math.PI / 2; // -90 degrees to face camera (rotate from right to front)

            // Auto Scale - reduced size
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 2.6 / maxDim; // Smaller scale (reduced from 3.2)
            model.scale.set(scale, scale, scale);

            scene.add(model);

            if (gltf.animations.length > 0) {
                mixer = new THREE.AnimationMixer(model);
                mixer.clipAction(gltf.animations[0]).play();
            }
        },
        (xhr) => {
            console.log((xhr.loaded / xhr.total * 100) + '% loaded');
        },
        (error) => {
            console.error("❌ Error loading avatar model:", error);
            console.error("❌ Error details:", error.message || error);
            console.error("❌ Model path attempted:", avatarPath);
            
            // Show fallback avatar
            const fallback = document.getElementById('simple-avatar-fallback');
            if (fallback) {
                fallback.style.display = 'flex';
                console.log("✅ Showing fallback avatar due to model load error");
            }
            
            // Try alternative paths
            const alternativePaths = [
                '/static/avatars/avatar.glb',
                '/static/avatars/avatar_1.glb',
                '/static/models/avatar.glb'
            ];
            
            console.log("🔄 Trying alternative avatar paths...");
            let pathIndex = 0;
            const tryNextPath = () => {
                if (pathIndex < alternativePaths.length) {
                    const altPath = alternativePaths[pathIndex];
                    console.log(`🔄 Trying alternative path: ${altPath}`);
                    loader.load(
                        altPath,
                        (gltf) => {
                            console.log(`✅ Avatar loaded from alternative path: ${altPath}`);
                            model = gltf.scene;
                            const box = new THREE.Box3().setFromObject(model);
                            const center = box.getCenter(new THREE.Vector3());
                            const size = box.getSize(new THREE.Vector3());
                            // Center the model
                            model.position.x = -center.x;
                            model.position.y = -center.y;
                            model.position.z = -center.z;
                            
                            // Move avatar down (lower position)
                            model.position.y -= 0.2; // Move down from center
                            
                            // Rotate to face the user
                            model.rotation.y = -Math.PI / 2; // -90 degrees to face camera
                            
                            const maxDim = Math.max(size.x, size.y, size.z);
                            const scale = 2.6 / maxDim; // Smaller scale (reduced from 3.2)
                            model.scale.set(scale, scale, scale);
                            scene.add(model);
                            if (gltf.animations.length > 0) {
                                mixer = new THREE.AnimationMixer(model);
                                mixer.clipAction(gltf.animations[0]).play();
                            }
                            if (fallback) fallback.style.display = 'none';
                        },
                        undefined,
                        () => {
                            pathIndex++;
                            tryNextPath();
                        }
                    );
                } else {
                    console.warn("⚠️ All avatar paths failed, showing geometric fallback");
                    // Add a simple geometric shape as fallback so you know 3D is working
                    const geometry = new THREE.BoxGeometry(1, 1, 1);
                    const material = new THREE.MeshBasicMaterial({ color: 0x2563eb });
                    const cube = new THREE.Mesh(geometry, material);
                    cube.position.y = 0.5;
                    scene.add(cube);
                }
            };
            tryNextPath();
        }
    );

    // 6. Events
    window.addEventListener('resize', () => {
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    });

    window.addEventListener('avatarRotate', (e) => {
        if (model) model.rotation.y += e.detail.rotation;
    });

    animate();
}

function animate() {
    requestAnimationFrame(animate);
    const delta = clock.getDelta();
    if (mixer) mixer.update(delta);
    renderer.render(scene, camera);
}

// Export functions for external use
window.avatarSpeak = function(duration = 2000) {
    if (model && mixer && mixer._actions.length > 0) {
        // Trigger speaking animation if available
        console.log("🗣️ Avatar speaking for", duration, "ms");
    }
};

// Initialize when script loads
console.log("📦 three_avatar.js module loaded");
console.log("📊 Document ready state:", document.readyState);

function startInit() {
    console.log("🚀 Starting avatar initialization...");
    const container = document.getElementById('three-canvas-container');
    const avatarSection = document.querySelector('.avatar-section');
    
    if (avatarSection) {
        console.log("✅ Avatar section found, display:", window.getComputedStyle(avatarSection).display);
    } else {
        console.warn("⚠️ Avatar section not found");
    }
    
    if (container) {
        console.log("✅ Container found, dimensions:", container.clientWidth, "x", container.clientHeight);
    } else {
        console.warn("⚠️ Container not found");
    }
    
    // Try to initialize
    init();
}

if (document.readyState === 'loading') {
    console.log("⏳ Waiting for DOM to load...");
    document.addEventListener('DOMContentLoaded', () => {
        console.log("✅ DOM loaded, initializing avatar...");
        setTimeout(startInit, 200); // Give time for CSS to apply
    });
} else {
    // DOM already loaded
    console.log("✅ DOM already loaded, initializing avatar...");
    setTimeout(startInit, 200); // Small delay to ensure container is rendered
}