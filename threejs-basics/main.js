import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

// SCENE
const scene = new THREE.Scene()

// CAMERA
const camera = new THREE.PerspectiveCamera(
    75,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
)

// RENDERER
const renderer = new THREE.WebGLRenderer()
renderer.setSize(window.innerWidth, window.innerHeight)
document.body.appendChild(renderer.domElement)

// --- LIGHTING SETUP ---
// Added an AmbientLight so the shadows aren't pitch black
const ambientLight = new THREE.AmbientLight(0xffffff, 0.5)
scene.add(ambientLight)

const light = new THREE.DirectionalLight(0xffffff, 1)
light.position.set(1, 1, 1)
scene.add(light)

// --- CYLINDER (YOUR "CUBE") ---
const geometry = new THREE.CylinderGeometry()
const material = new THREE.MeshStandardMaterial({
    color: 0xffffff
})
const cube = new THREE.Mesh(geometry, material)
scene.add(cube)

cube.position.x = -5
cube.rotation.y = -2

// Load the texture (make sure pictures/lufffy.jfif exists!)
const textureLoader = new THREE.TextureLoader()
const texture = textureLoader.load('pictures/lufffy.jfif')
material.map = texture

// --- CAMERA POSITION ---
camera.position.z = 7
camera.position.y = 1
camera.position.x = 1

// --- GLTF MODEL LOADING ---
// 1. Declare a variable OUTSIDE the loader so the animation loop can access it
let loadedModel;

const loader = new GLTFLoader()
loader.load(
    'pictures/model.glb',
    (gltf) => {
        loadedModel = gltf.scene;

        // Move it slightly to the right so it doesn't overlap with the cylinder
        loadedModel.position.x = 2;

        // Optional: Scale it down if the model is too huge (adjust these numbers!)
        loadedModel.scale.set(1, 1, 1);

        scene.add(loadedModel);
        console.log("Model successfully loaded!");
    },
    (xhr) => {
        console.log((xhr.loaded / xhr.total * 100) + '% loaded');
    },
    (error) => {
        console.error('An error happened', error);
    }
)

// --- ANIMATION LOOP ---
function animate() {
    requestAnimationFrame(animate)

    // Spin the cylinder
    cube.rotation.x += 0.01
    cube.rotation.y += 0.01

    // 2. Spin the 3D model IF it has finished loading
    if (loadedModel) {
        loadedModel.rotation.y -= 0.01;
    }

    renderer.render(scene, camera)
}

animate()