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
let isAnimating = false;
let avatarLoaded = false;
let baseScaleY = 1.0;
let mixer = null;

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
    
    // Create camera
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 1, 4);
    camera.lookAt(0, 1, 0);
    
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
    
    // Add renderer to container
    const canvasContainer = document.getElementById('three-canvas-container');
    if (canvasContainer) {
        canvasContainer.appendChild(renderer.domElement);
        console.log('[NATURAL-AVATAR] ✅ Renderer added to DOM');
    } else {
        console.error('[NATURAL-AVATAR] ❌ Canvas container not found');
        return false;
    }
    
    // Enhanced lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.8);
    keyLight.position.set(5, 8, 5);
    keyLight.castShadow = true;
    scene.add(keyLight);
    
    const fillLight = new THREE.DirectionalLight(0xb3d9ff, 0.4);
    fillLight.position.set(-5, 3, -5);
    scene.add(fillLight);
    
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.3);
    rimLight.position.set(0, 5, -10);
    scene.add(rimLight);
    
    // Enable orbit controls for zoom and rotation
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enabled = true;
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 2;
    controls.maxDistance = 8;
    controls.target.set(0, 1, 0); // Look at avatar center
    controls.update();
    
    // Track dragging state for head rotation
    controls.addEventListener('start', () => {
        isDragging = true;
        renderer.domElement.style.cursor = 'grabbing';
    });
    
    controls.addEventListener('end', () => {
        isDragging = false;
        renderer.domElement.style.cursor = 'grab';
    });
    
    renderer.domElement.style.cursor = 'grab';
    
    console.log('[NATURAL-AVATAR] ✅ Scene initialized');
    return true;
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
            
            // Check for skeleton
            avatarObject.traverse((child) => {
                if (child.isSkinnedMesh) {
                    console.log('[NATURAL-AVATAR] Found SkinnedMesh:', child.name);
                    if (child.skeleton && !avatarSkeleton) {
                        avatarSkeleton = child.skeleton;
                        console.log('[NATURAL-AVATAR] Skeleton bones:', child.skeleton.bones.length);
                    }
                }
            });
            
            // Setup animation mixer - but DON'T play any animations (they override our bone rotations)
            if (gltf.animations && gltf.animations.length > 0) {
                mixer = new THREE.AnimationMixer(avatarObject);
                console.log('[NATURAL-AVATAR] Found', gltf.animations.length, 'animations - NOT playing them (they override bone rotations)');
                // DO NOT play animations - they will override our manual bone rotations
            }
            
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
            
            avatarObject.position.x = -center.x * scale;
            avatarObject.position.y = -center.y * scale;
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
    console.log('[NATURAL-AVATAR] Setting natural standing pose...');
    
    // Arms fully down at sides
    // IMPORTANT: Get bones directly from skeleton to ensure we're modifying the actual bones
    let rightArmBone = avatarBones.rightArm;
    let leftArmBone = avatarBones.leftArm;
    
    // Re-assign from skeleton if available to ensure exact reference
    if (avatarSkeleton && rightArmBone) {
        const skeletonBone = avatarSkeleton.bones.find(b => b.name === rightArmBone.name);
        if (skeletonBone) {
            rightArmBone = skeletonBone;
            avatarBones.rightArm = skeletonBone;
            console.log('[NATURAL-AVATAR] Using skeleton bone for right arm:', skeletonBone.name);
        }
    }
    if (avatarSkeleton && leftArmBone) {
        const skeletonBone = avatarSkeleton.bones.find(b => b.name === leftArmBone.name);
        if (skeletonBone) {
            leftArmBone = skeletonBone;
            avatarBones.leftArm = skeletonBone;
            console.log('[NATURAL-AVATAR] Using skeleton bone for left arm:', skeletonBone.name);
        }
    }
    
    if (rightArmBone) {
        const initialRot = {
            x: rightArmBone.rotation.x,
            y: rightArmBone.rotation.y,
            z: rightArmBone.rotation.z
        };
        console.log('[NATURAL-AVATAR] Right arm INITIAL rotation:', initialRot);
        
        // Natural standing pose: arms hanging down naturally (not T-pose)
        // Position arms to hang straight down at the sides like a standing human
        rightArmBone.rotation.order = 'XYZ';
        rightArmBone.rotation.x = 0; // Arms straight down (no forward rotation)
        rightArmBone.rotation.y = 0; // Arms straight at sides (no outward angle)
        rightArmBone.rotation.z = 0;
        
        // IMPORTANT: Disable auto-update to prevent overrides, then manually update
        rightArmBone.matrixAutoUpdate = true;
        
        // Update quaternion and matrix
        const euler = new THREE.Euler(0, 0, 0, 'XYZ');
        rightArmBone.quaternion.setFromEuler(euler);
        rightArmBone.updateMatrix();
        rightArmBone.updateMatrixWorld(true); // Update world matrix recursively
        
        console.log('[NATURAL-AVATAR] Right arm rotation APPLIED:', {
            x: rightArmBone.rotation.x.toFixed(3),
            y: rightArmBone.rotation.y.toFixed(3),
            z: rightArmBone.rotation.z.toFixed(3),
            matrixWorld_set: !!rightArmBone.matrixWorld
        });
    }
    
    if (leftArmBone) {
        const initialRot = {
            x: leftArmBone.rotation.x,
            y: leftArmBone.rotation.y,
            z: leftArmBone.rotation.z
        };
        console.log('[NATURAL-AVATAR] Left arm INITIAL rotation:', initialRot);
        
        // Natural standing pose: arms hanging down naturally (not T-pose)
        leftArmBone.rotation.order = 'XYZ';
        leftArmBone.rotation.x = 0; // Arms straight down (no forward rotation)
        leftArmBone.rotation.y = 0; // Arms straight at sides (no outward angle)
        leftArmBone.rotation.z = 0;
        
        leftArmBone.matrixAutoUpdate = true;
        
        // Update quaternion and matrix
        const euler = new THREE.Euler(0, 0, 0, 'XYZ');
        leftArmBone.quaternion.setFromEuler(euler);
        leftArmBone.updateMatrix();
        leftArmBone.updateMatrixWorld(true); // Update world matrix recursively
        
        console.log('[NATURAL-AVATAR] Left arm rotation APPLIED:', {
            x: leftArmBone.rotation.x.toFixed(3),
            y: leftArmBone.rotation.y.toFixed(3),
            z: leftArmBone.rotation.z.toFixed(3),
            matrixWorld_set: !!leftArmBone.matrixWorld
        });
    }
    
    // Forearms hanging straight down naturally
    if (avatarBones.rightForearm) {
        avatarBones.rightForearm.rotation.order = 'XYZ';
        avatarBones.rightForearm.rotation.x = 0; // Forearms straight down
        avatarBones.rightForearm.rotation.y = 0;
        avatarBones.rightForearm.rotation.z = 0;
        avatarBones.rightForearm.updateMatrix();
    }
    
    if (avatarBones.leftForearm) {
        avatarBones.leftForearm.rotation.order = 'XYZ';
        avatarBones.leftForearm.rotation.x = 0; // Forearms straight down
        avatarBones.leftForearm.rotation.y = 0;
        avatarBones.leftForearm.rotation.z = 0;
        avatarBones.leftForearm.updateMatrix();
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
    
    // Update skeleton immediately
    updateSkeleton();
    
    console.log('[NATURAL-AVATAR] ✅ Natural standing pose set');
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
            // Natural hanging arm position: arms straight down at sides
            rightArmBone.rotation.x = 0; // Arms straight down (no forward rotation)
            rightArmBone.rotation.y = 0; // Arms straight at sides (no outward angle)
            rightArmBone.rotation.z = 0;
            
            // Update quaternion and matrix
            const euler = new THREE.Euler(0, 0, 0, 'XYZ');
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
            // Natural hanging arm position: arms straight down at sides
            leftArmBone.rotation.x = 0; // Arms straight down (no forward rotation)
            leftArmBone.rotation.y = 0; // Arms straight at sides (no outward angle)
            leftArmBone.rotation.z = 0;
            
            // Update quaternion and matrix
            const euler = new THREE.Euler(0, 0, 0, 'XYZ');
            leftArmBone.quaternion.setFromEuler(euler);
            leftArmBone.updateMatrix();
            leftArmBone.updateMatrixWorld(true);
        }
        
        // Keep forearms and hands still in natural position
        if (avatarBones.rightForearm && !isSpeaking) {
            avatarBones.rightForearm.rotation.x = 0; // Natural hanging position
            avatarBones.rightForearm.updateMatrix();
        }
        if (avatarBones.leftForearm && !isSpeaking) {
            avatarBones.leftForearm.rotation.x = 0; // Natural hanging position
            avatarBones.leftForearm.updateMatrix();
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
}

// Reset avatar view
function resetAvatarView() {
    console.log('[NATURAL-AVATAR] Resetting avatar view...');
    
    if (controls && camera) {
        // Reset camera position
        camera.position.set(0, 1, 4);
        camera.lookAt(0, 1, 0);
        
        // Reset orbit controls
        controls.target.set(0, 1, 0);
        controls.update();
    }
    
    // Reset avatar object position (will be recalculated based on center)
    if (avatarObject) {
        const box = new THREE.Box3().setFromObject(avatarObject);
        const center = box.getCenter(new THREE.Vector3());
        const scale = avatarObject.scale.x;
        
        avatarObject.position.x = -center.x * scale;
        avatarObject.position.y = -center.y * scale;
        avatarObject.position.z = -center.z * scale;
        avatarObject.rotation.y = Math.PI;
    }
    
    console.log('[NATURAL-AVATAR] ✅ Avatar view reset');
}

// Set user typing state (called from chat.js)
function setUserTyping(typing) {
    isUserTyping = typing;
    console.log('[NATURAL-AVATAR] User typing:', typing);
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
window.excitementJump = excitementJump;

console.log('[NATURAL-AVATAR] Module loaded successfully!');