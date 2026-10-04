import React, { useState, useEffect, useRef, useMemo } from "react";
import * as THREE from "three";
import {
  Waves,
  Zap,
  Activity,
  Flame,
  Layers,
  Sparkles,
  Sliders,
  AlertTriangle,
  CheckCircle2,
  Download,
  Copy,
  Check,
  RefreshCw,
  Play,
  RotateCcw,
  Compass,
  Info,
  Maximize2,
  Terminal,
  Eye,
  Filter,
  Shield,
} from "lucide-react";
import {
  pythonComputationService,
  PythonMarangoniPoreResult,
  VoxelHeatmapDatum,
  TrappedPoreDatum,
} from "../../services/pythonComputationService";
import { useLpbfBuildJobStore } from "../../store/useLpbfBuildJobStore";
import { useMaterialSpecimenStore } from "../../store/useMaterialSpecimenStore";

export interface MarangoniLabProps {
  initialPower_W?: number;
  initialSpeed_mms?: number;
  initialBeamDiameter_um?: number;
  initialPreheat_C?: number;
  initialMaterial?: string;
  onApplyParameters?: (p: { power_W: number; speed_mms: number; preheat_C: number }) => void;
}

export const MARANGONI_ALLOYS = [
  {
    id: "in718",
    name: "Inconel 718",
    category: "Nickel Superalloy",
    surfaceTension_N_m: 1.78,
    d_gamma_dT_pure: -0.00042,
    critical_Ma: 4500,
    viscosity_Pa_s: 0.0055,
    density_kg_m3: 7450,
    liquidus_C: 1336,
    solidus_C: 1260,
    recPower_W: 285,
    recSpeed_mms: 960,
    defaultSulfur_ppm: 15,
  },
  {
    id: "ti64",
    name: "Ti-6Al-4V",
    category: "Titanium Alloy",
    surfaceTension_N_m: 1.55,
    d_gamma_dT_pure: -0.00028,
    critical_Ma: 3800,
    viscosity_Pa_s: 0.0042,
    density_kg_m3: 3950,
    liquidus_C: 1660,
    solidus_C: 1604,
    recPower_W: 250,
    recSpeed_mms: 1200,
    defaultSulfur_ppm: 8,
  },
  {
    id: "ss316l",
    name: "316L Stainless Steel",
    category: "Austenitic Stainless Steel",
    surfaceTension_N_m: 1.70,
    d_gamma_dT_pure: -0.00045,
    critical_Ma: 4200,
    viscosity_Pa_s: 0.0060,
    density_kg_m3: 6980,
    liquidus_C: 1400,
    solidus_C: 1375,
    recPower_W: 200,
    recSpeed_mms: 800,
    defaultSulfur_ppm: 25, // Higher sulfur in austenitic steel -> high propensity for flow reversal
  },
  {
    id: "alsi10mg",
    name: "AlSi10Mg",
    category: "Aluminum Alloy",
    surfaceTension_N_m: 0.86,
    d_gamma_dT_pure: -0.00018,
    critical_Ma: 3200,
    viscosity_Pa_s: 0.0013,
    density_kg_m3: 2350,
    liquidus_C: 595,
    solidus_C: 557,
    recPower_W: 370,
    recSpeed_mms: 1300,
    defaultSulfur_ppm: 5,
  },
  {
    id: "scalmalloy",
    name: "Scalmalloy® (Al-Mg-Sc-Zr)",
    category: "Aluminum-Scandium",
    surfaceTension_N_m: 0.88,
    d_gamma_dT_pure: -0.00020,
    critical_Ma: 3400,
    viscosity_Pa_s: 0.0015,
    density_kg_m3: 2340,
    liquidus_C: 650,
    solidus_C: 580,
    recPower_W: 400,
    recSpeed_mms: 1600,
    defaultSulfur_ppm: 5,
  },
];

export const MarangoniPoreInstabilityLab: React.FC<MarangoniLabProps> = ({
  initialPower_W = 285,
  initialSpeed_mms = 960,
  initialBeamDiameter_um = 90,
  initialPreheat_C = 200,
  initialMaterial = "Inconel 718",
  onApplyParameters,
}) => {
  // Process and physics parameters
  const [selectedMaterial, setSelectedMaterial] = useState<string>(initialMaterial);
  const [laserPower_W, setLaserPower_W] = useState<number>(initialPower_W);
  const [scanSpeed_mms, setScanSpeed_mms] = useState<number>(initialSpeed_mms);
  const [beamDiameter_um, setBeamDiameter_um] = useState<number>(initialBeamDiameter_um);
  const [preheatTemp_C, setPreheatTemp_C] = useState<number>(initialPreheat_C);
  const [surfactantSulfur_ppm, setSurfactantSulfur_ppm] = useState<number>(15);
  const [shieldingGas, setShieldingGas] = useState<string>("Argon (Ar)");

  useEffect(() => {
    setLaserPower_W(initialPower_W);
    setScanSpeed_mms(initialSpeed_mms);
    setBeamDiameter_um(initialBeamDiameter_um);
    setPreheatTemp_C(initialPreheat_C);
    setSelectedMaterial(initialMaterial);
  }, [initialPower_W, initialSpeed_mms, initialBeamDiameter_um, initialPreheat_C, initialMaterial]);

  // Visualization View Modes
  const [displayScalar, setDisplayScalar] = useState<
    "pore-prob" | "temperature" | "velocity" | "downward-drag" | "vorticity"
  >("pore-prob");
  const [minProbThreshold, setMinProbThreshold] = useState<number>(20); // Filter voxels below this %
  const [slicePlane, setSlicePlane] = useState<"none" | "xy-top" | "xz-longitudinal" | "yz-transverse">("none");
  const [sliceOffset_pct, setSliceOffset_pct] = useState<number>(0);
  const [showStreamlines, setShowStreamlines] = useState<boolean>(true);
  const [showPoreSpheres, setShowPoreSpheres] = useState<boolean>(true);
  const [showMeltHull, setShowMeltHull] = useState<boolean>(true);
  const [hoveredVoxel, setHoveredVoxel] = useState<VoxelHeatmapDatum | null>(null);
  const [selectedPore, setSelectedPore] = useState<TrappedPoreDatum | null>(null);

  // Simulation execution state
  const [isRunningSim, setIsRunningSim] = useState<boolean>(false);
  const [simResult, setSimResult] = useState<PythonMarangoniPoreResult | null>(null);
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const [activeCodeTab, setActiveCodeTab] = useState<"viewer" | "python-source">("viewer");
  const [isCopied, setIsCopied] = useState<boolean>(false);

  // 3D Canvas Mounting Ref
  const mountRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // Active alloy metadata
  const currentAlloy = useMemo(() => {
    return (
      MARANGONI_ALLOYS.find((a) => a.name.toLowerCase().includes(selectedMaterial.toLowerCase().slice(0, 4))) ||
      MARANGONI_ALLOYS[0]
    );
  }, [selectedMaterial]);

  // Execute Simulation Trigger
  const runSimulation = async () => {
    setIsRunningSim(true);
    const startT = performance.now();
    const timestamp = new Date().toLocaleTimeString();

    const newLogs = [
      `[${timestamp}] [INIT] Starting 3D Marangoni Flow Instability & Gas Entrapment Solver...`,
      `[${timestamp}] [ALLOY] Material: ${selectedMaterial} | Liquidus: ${currentAlloy.liquidus_C}°C | Solidus: ${currentAlloy.solidus_C}°C`,
      `[${timestamp}] [SURFACTANT] Sulfur activity: ${surfactantSulfur_ppm} ppm | Base dγ/dT: ${currentAlloy.d_gamma_dT_pure} N/m·K`,
      `[${timestamp}] [LASER] Power: ${laserPower_W} W | Speed: ${scanSpeed_mms} mm/s | 2r₀: ${beamDiameter_um} µm | Gas: ${shieldingGas}`,
      `[${timestamp}] [SOLVER] Discretizing 3D Navier-Stokes & Thermocapillary vorticity transport mesh...`,
    ];

    try {
      const buildJob = useLpbfBuildJobStore.getState().job;
      const processSeed = useMaterialSpecimenStore.getState().activeSpecimen.lpbf.processSeed ?? 42;
      const thermalGeom = buildJob?.thermal?.meltPoolGeometry;
      const thermalPeak = buildJob?.thermal?.hydrodynamicsAndRecoil?.peakTemperature_C;
      const result = await pythonComputationService.solveMarangoniPoreInstability({
        material: selectedMaterial,
        laserPower_W,
        scanSpeed_mm_s: scanSpeed_mms,
        beamDiameter_um,
        preheatTemp_C,
        surfactant_sulfur_ppm: surfactantSulfur_ppm,
        shieldingGas,
        processSeed,
        meltPoolWidth_um: thermalGeom?.width_um,
        meltPoolDepth_um: thermalGeom?.depth_um,
        meltPoolLength_um: thermalGeom?.length_um,
        peakTemperature_C: thermalPeak,
      });

      const elapsed = performance.now() - startT;
      newLogs.push(
        `[${timestamp}] [CONVERGED] 3D Hydrodynamic fields resolved in ${elapsed.toFixed(1)} ms (${result.engine}).`,
        `[${timestamp}] [HYDRODYNAMICS] Marangoni Number Ma = ${result.marangoniHydrodynamics.marangoniNumber_Ma.toLocaleString()} (Crit: ${result.marangoniHydrodynamics.criticalMarangoni_Ma_crit.toLocaleString()}) | Instability Ratio: ${result.marangoniHydrodynamics.instabilityRatio}x`,
        `[${timestamp}] [FLOW REGIME] ${result.marangoniHydrodynamics.flowRegime} | Peak u_Ma = ${result.marangoniHydrodynamics.peakVelocity_m_s} m/s`,
        `[${timestamp}] [POROSITY] Predicted Relative Density: ${result.porosityPrediction.relativeDensity_pct}% | Trapped Pores: ${result.porosityPrediction.predictedPoresCount} | Mean Ø: ${result.porosityPrediction.meanPoreDiameter_um} µm`,
        `[${timestamp}] [SUCCESS] 3D Heatmap mesh (${result.heatmap3D.gridResolution.totalVoxels} voxels) mapped to WebGL viewport.`
      );

      setSimResult(result);
      setConsoleLogs(newLogs);
    } catch (err: any) {
      newLogs.push(`[${timestamp}] [ERROR] Simulation failed: ${err?.message || err}`);
      setConsoleLogs(newLogs);
    } finally {
      setIsRunningSim(false);
    }
  };

  // Run on mount or when key parameters change
  useEffect(() => {
    runSimulation();
  }, [selectedMaterial, laserPower_W, scanSpeed_mms, beamDiameter_um, preheatTemp_C, surfactantSulfur_ppm, shieldingGas]);

  // Color mapping helper for 3D scalar fields
  const getScalarColor = (
    voxel: VoxelHeatmapDatum,
    scalar: "pore-prob" | "temperature" | "velocity" | "downward-drag" | "vorticity",
    result: PythonMarangoniPoreResult
  ): THREE.Color => {
    let t = 0; // Normalized 0 to 1

    if (scalar === "pore-prob") {
      t = Math.min(1, Math.max(0, voxel.prob_pct / 100));
    } else if (scalar === "temperature") {
      const tMin = result.inputSummary.preheatTemp_C;
      const tMax = result.meltPoolGeometry.peakTemp_C;
      t = Math.min(1, Math.max(0, (voxel.temp_C - tMin) / Math.max(100, tMax - tMin)));
    } else if (scalar === "velocity") {
      const uMax = result.marangoniHydrodynamics.peakVelocity_m_s;
      t = Math.min(1, Math.max(0, voxel.u_mag_m_s / Math.max(0.1, uMax)));
    } else if (scalar === "downward-drag") {
      // Downward velocity (uz < 0)
      const maxDownward = result.marangoniHydrodynamics.peakVelocity_m_s * 0.8;
      t = Math.min(1, Math.max(0, Math.abs(Math.min(0, voxel.uz_m_s)) / Math.max(0.1, maxDownward)));
    } else if (scalar === "vorticity") {
      t = Math.min(1, Math.max(0, voxel.vorticity_s / 50000));
    }

    // High-contrast colormap (Turbo / Jet inspired): Blue -> Cyan -> Green -> Yellow -> Red
    const color = new THREE.Color();
    if (t < 0.25) {
      const f = t / 0.25;
      color.setRGB(0.05 + 0.05 * f, 0.2 + 0.6 * f, 0.9 - 0.2 * f);
    } else if (t < 0.5) {
      const f = (t - 0.25) / 0.25;
      color.setRGB(0.1 + 0.2 * f, 0.8 + 0.2 * f, 0.7 - 0.7 * f);
    } else if (t < 0.75) {
      const f = (t - 0.5) / 0.25;
      color.setRGB(0.3 + 0.7 * f, 1.0 - 0.1 * f, 0.0);
    } else {
      const f = (t - 0.75) / 0.25;
      color.setRGB(1.0, 0.9 - 0.7 * f, 0.1 - 0.1 * f);
    }
    return color;
  };

  // Three.js 3D WebGL Canvas Lifecycle
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Dimensions
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 520;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050810);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(42, width / height, 1, 3000);
    camera.position.set(180, 220, 260);
    camera.lookAt(0, -30, 0);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    container.innerHTML = "";
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0x38bdf8, 1.2);
    dirLight1.position.set(200, 300, 150);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0xf43f5e, 0.6);
    dirLight2.position.set(-200, -100, -150);
    scene.add(dirLight2);

    // Build Platform Substrate Baseplate
    const substrateGeo = new THREE.BoxGeometry(420, 8, 300);
    const substrateMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      metalness: 0.8,
      roughness: 0.4,
      wireframe: false,
    });
    const substrateMesh = new THREE.Mesh(substrateGeo, substrateMat);
    substrateMesh.position.set(0, -4, 0);
    scene.add(substrateMesh);

    // Grid Floor
    const gridHelper = new THREE.GridHelper(400, 20, 0x1e293b, 0x0f172a);
    gridHelper.position.set(0, 0.1, 0);
    scene.add(gridHelper);

    // Orientation Coordinate Axes
    const axesHelper = new THREE.AxesHelper(60);
    axesHelper.position.set(-180, 2, -120);
    scene.add(axesHelper);

    // Group for dynamic simulation geometry
    const simGroup = new THREE.Group();
    simGroup.name = "simulation-group";
    scene.add(simGroup);

    // Mouse Interaction for Orbit / Pan
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;
    let sphericalTheta = Math.PI / 4;
    let sphericalPhi = Math.PI / 3.5;
    let sphericalRadius = 380;

    const updateCameraPos = () => {
      camera.position.x = sphericalRadius * Math.sin(sphericalPhi) * Math.sin(sphericalTheta);
      camera.position.y = sphericalRadius * Math.cos(sphericalPhi);
      camera.position.z = sphericalRadius * Math.sin(sphericalPhi) * Math.cos(sphericalTheta);
      camera.lookAt(0, -30, 0);
    };
    updateCameraPos();

    const handleMouseDown = (e: MouseEvent) => {
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const deltaX = e.clientX - prevMouseX;
      const deltaY = e.clientY - prevMouseY;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;

      sphericalTheta -= deltaX * 0.008;
      sphericalPhi = Math.max(0.1, Math.min(Math.PI / 2 - 0.05, sphericalPhi - deltaY * 0.008));
      updateCameraPos();
    };

    const handleMouseUp = () => {
      isDragging = false;
    };

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      sphericalRadius = Math.max(120, Math.min(750, sphericalRadius + e.deltaY * 0.4));
      updateCameraPos();
    };

    const canvasDom = renderer.domElement;
    canvasDom.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    canvasDom.addEventListener("wheel", handleWheel, { passive: false });

    // Resize Observer
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: newW, height: newH } = entry.contentRect;
        if (newW > 0 && newH > 0) {
          camera.aspect = newW / newH;
          camera.updateProjectionMatrix();
          renderer.setSize(newW, newH);
        }
      }
    });
    resizeObserver.observe(container);

    // Animation Loop
    let clock = new THREE.Clock();
    const animate = () => {
      animFrameRef.current = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      // Gentle laser spot pulsing
      const laserBeam = scene.getObjectByName("laser-beam-indicator");
      if (laserBeam) {
        (laserBeam as THREE.Mesh).scale.set(
          1 + 0.05 * Math.sin(elapsedTime * 8),
          1,
          1 + 0.05 * Math.sin(elapsedTime * 8)
        );
      }

      renderer.render(scene, camera);
    };
    animate();

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      resizeObserver.disconnect();
      canvasDom.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      canvasDom.removeEventListener("wheel", handleWheel);
      renderer.dispose();
    };
  }, []);

  // Update 3D Visual Objects when simResult or display toggles change
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !simResult) return;

    let simGroup = scene.getObjectByName("simulation-group") as THREE.Group;
    if (simGroup) {
      // Clear previous meshes
      while (simGroup.children.length > 0) {
        const obj = simGroup.children[0];
        simGroup.remove(obj);
        if ((obj as any).geometry) (obj as any).geometry.dispose();
        if ((obj as any).material) {
          if (Array.isArray((obj as any).material)) {
            (obj as any).material.forEach((m: any) => m.dispose());
          } else {
            (obj as any).material.dispose();
          }
        }
      }
    } else {
      simGroup = new THREE.Group();
      simGroup.name = "simulation-group";
      scene.add(simGroup);
    }

    const { meltPoolGeometry, heatmap3D, porosityPrediction, marangoniHydrodynamics } = simResult;
    const scaleFactor = 0.8; // Scale µm to Three.js world units

    // 1. Melt Pool Boundary Hull (Semi-ellipsoid Wireframe & Translucent Membrane)
    if (showMeltHull) {
      const length_u = meltPoolGeometry.length_um * scaleFactor;
      const width_u = meltPoolGeometry.width_um * scaleFactor;
      const depth_u = meltPoolGeometry.depth_um * scaleFactor;

      const hullGeo = new THREE.SphereGeometry(1, 32, 24, 0, Math.PI * 2, 0, Math.PI / 2);
      hullGeo.scale(width_u / 2, depth_u, length_u / 2);
      hullGeo.rotateX(Math.PI); // Orient downwards (-Y) into baseplate
      hullGeo.translate(0, 0, -length_u * 0.2); // Shift trailing rear

      const hullMat = new THREE.MeshPhysicalMaterial({
        color: 0x06b6d4,
        transparent: true,
        opacity: 0.18,
        roughness: 0.1,
        metalness: 0.1,
        transmission: 0.6,
        ior: 1.3,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const hullMesh = new THREE.Mesh(hullGeo, hullMat);
      simGroup.add(hullMesh);

      // Wireframe overlay of melt pool
      const wireMat = new THREE.MeshBasicMaterial({
        color: 0x38bdf8,
        wireframe: true,
        transparent: true,
        opacity: 0.25,
      });
      const wireMesh = new THREE.Mesh(hullGeo, wireMat);
      simGroup.add(wireMesh);
    }

    // 2. Laser Beam Spot Indicator
    const r0_u = (beamDiameter_um / 2) * scaleFactor;
    const beamCylinderGeo = new THREE.CylinderGeometry(r0_u, r0_u * 0.8, 120, 24);
    const beamCylinderMat = new THREE.MeshBasicMaterial({
      color: 0xec4899,
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const beamCylinder = new THREE.Mesh(beamCylinderGeo, beamCylinderMat);
    beamCylinder.position.set(0, 60, 0);
    beamCylinder.name = "laser-beam-indicator";
    simGroup.add(beamCylinder);

    // Laser Spot Core on Surface
    const spotCoreGeo = new THREE.RingGeometry(0, r0_u, 24);
    const spotCoreMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      side: THREE.DoubleSide,
    });
    const spotCore = new THREE.Mesh(spotCoreGeo, spotCoreMat);
    spotCore.rotation.x = -Math.PI / 2;
    spotCore.position.set(0, 0.5, 0);
    simGroup.add(spotCore);

    // 3. Volumetric 3D Heatmap Voxels
    const voxels = heatmap3D.voxels;
    const voxelBoxGeo = new THREE.BoxGeometry(4.5, 4.5, 4.5);
    const filteredVoxels = voxels.filter((v) => {
      // Probability threshold filter
      if (displayScalar === "pore-prob" && v.prob_pct < minProbThreshold) return false;
      if (v.phase === "solid" && displayScalar === "pore-prob") return false;

      // Slice plane filtering
      if (slicePlane === "xy-top") {
        const maxZ = 0;
        const sliceZ = maxZ - (sliceOffset_pct / 100) * meltPoolGeometry.depth_um;
        return v.z_um >= sliceZ;
      }
      if (slicePlane === "xz-longitudinal") {
        const maxOffset = meltPoolGeometry.width_um / 2;
        const sliceY = (sliceOffset_pct / 100) * maxOffset;
        return v.y_um >= sliceY - 8 && v.y_um <= sliceY + 8;
      }
      if (slicePlane === "yz-transverse") {
        const sliceX = (sliceOffset_pct / 100) * (meltPoolGeometry.length_um / 2);
        return v.x_um >= sliceX - 10 && v.x_um <= sliceX + 10;
      }
      return true;
    });

    // InstancedMesh for high performance 3D voxel point cloud rendering
    if (filteredVoxels.length > 0) {
      const instancedMesh = new THREE.InstancedMesh(
        voxelBoxGeo,
        new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.85 }),
        filteredVoxels.length
      );

      const dummy = new THREE.Object3D();
      filteredVoxels.forEach((v, idx) => {
        // Map voxel coordinates (x is scan axis -> Z in Three.js, y is transverse -> X, z is depth -> Y)
        const posX = v.y_um * scaleFactor;
        const posY = v.z_um * scaleFactor;
        const posZ = v.x_um * scaleFactor;

        dummy.position.set(posX, posY, posZ);

        // Scale box based on probability or magnitude
        const scaleVal = displayScalar === "pore-prob" ? Math.max(0.4, v.prob_pct / 100) : 0.8;
        dummy.scale.set(scaleVal, scaleVal, scaleVal);
        dummy.updateMatrix();

        instancedMesh.setMatrixAt(idx, dummy.matrix);
        const color = getScalarColor(v, displayScalar, simResult);
        instancedMesh.setColorAt(idx, color);
      });

      instancedMesh.instanceMatrix.needsUpdate = true;
      if (instancedMesh.instanceColor) instancedMesh.instanceColor.needsUpdate = true;
      simGroup.add(instancedMesh);
    }

    // 4. Marangoni Convective Vortex Streamlines
    if (showStreamlines) {
      const isFlowInward = marangoniHydrodynamics.flowDirection.includes("Inward");
      const numLines = 14;

      for (let s = 0; s < numLines; s++) {
        const angle = (s / numLines) * Math.PI * 2;
        const radiusOut = (meltPoolGeometry.width_um / 2) * scaleFactor * 0.85;
        const radiusIn = r0_u * 0.4;
        const depthCurve = -meltPoolGeometry.depth_um * scaleFactor * 0.65;

        const curvePoints: THREE.Vector3[] = [];
        if (!isFlowInward) {
          // Outward flow: Center -> Surface Edge -> Downwards vortex -> Recirculate inward at bottom
          curvePoints.push(new THREE.Vector3(radiusIn * Math.cos(angle), 0.2, radiusIn * Math.sin(angle)));
          curvePoints.push(new THREE.Vector3(radiusOut * 0.6 * Math.cos(angle), 0.1, radiusOut * 0.6 * Math.sin(angle)));
          curvePoints.push(new THREE.Vector3(radiusOut * Math.cos(angle), -5, radiusOut * Math.sin(angle)));
          curvePoints.push(new THREE.Vector3(radiusOut * 0.8 * Math.cos(angle), depthCurve * 0.7, radiusOut * 0.8 * Math.sin(angle)));
          curvePoints.push(new THREE.Vector3(radiusIn * 1.5 * Math.cos(angle), depthCurve, radiusIn * 1.5 * Math.sin(angle)));
        } else {
          // Inward centripetal jet (Surfactant inversion): Edge -> Center surface -> Deep downward plunge
          curvePoints.push(new THREE.Vector3(radiusOut * Math.cos(angle), 0.2, radiusOut * Math.sin(angle)));
          curvePoints.push(new THREE.Vector3(radiusOut * 0.4 * Math.cos(angle), 0.1, radiusOut * 0.4 * Math.sin(angle)));
          curvePoints.push(new THREE.Vector3(radiusIn * Math.cos(angle), -8, radiusIn * Math.sin(angle)));
          curvePoints.push(new THREE.Vector3(radiusIn * 0.3 * Math.cos(angle), depthCurve * 0.9, radiusIn * 0.3 * Math.sin(angle)));
        }

        const curve = new THREE.CatmullRomCurve3(curvePoints);
        const tubeGeo = new THREE.TubeGeometry(curve, 20, 1.2, 8, false);
        const tubeMat = new THREE.MeshStandardMaterial({
          color: isFlowInward ? 0xf59e0b : 0x06b6d4,
          emissive: isFlowInward ? 0xb45309 : 0x0284c7,
          emissiveIntensity: 0.6,
          metalness: 0.8,
          roughness: 0.2,
        });
        const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
        simGroup.add(tubeMesh);
      }
    }

    // 5. Discrete 3D Trapped Gas Pores (Spheres)
    if (showPoreSpheres && porosityPrediction.trappedPores) {
      porosityPrediction.trappedPores.forEach((p) => {
        const poreRadius = Math.max(2.5, (p.diameter_um / 2) * scaleFactor * 0.45);
        const poreGeo = new THREE.SphereGeometry(poreRadius, 16, 16);
        const poreMat = new THREE.MeshStandardMaterial({
          color: 0xf43f5e,
          emissive: 0xbe123c,
          emissiveIntensity: 0.8,
          metalness: 0.9,
          roughness: 0.1,
        });
        const poreMesh = new THREE.Mesh(poreGeo, poreMat);
        poreMesh.position.set(p.y_um * scaleFactor, p.z_um * scaleFactor, p.x_um * scaleFactor);
        simGroup.add(poreMesh);
      });
    }
  }, [simResult, displayScalar, minProbThreshold, slicePlane, sliceOffset_pct, showStreamlines, showPoreSpheres, showMeltHull]);

  // Camera Presets
  const setCameraPreset = (preset: "iso" | "top" | "side" | "front") => {
    const camera = cameraRef.current;
    if (!camera) return;

    if (preset === "iso") {
      camera.position.set(180, 220, 260);
    } else if (preset === "top") {
      camera.position.set(0, 380, 0.1);
    } else if (preset === "side") {
      camera.position.set(380, -20, 0); // Along transverse looking at XZ
    } else if (preset === "front") {
      camera.position.set(0, -20, 380); // Looking along scan axis YZ
    }
    camera.lookAt(0, -30, 0);
  };

  // Copy Python code snippet
  const handleCopyCode = () => {
    const code = getPythonCodeSnippet();
    navigator.clipboard.writeText(code);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  // Download Python Script (.py)
  const handleDownloadCode = () => {
    const code = getPythonCodeSnippet();
    const blob = new Blob([code], { type: "text/x-python" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `marangoni_pore_sim_${selectedMaterial.toLowerCase().replace(/[^a-z0-9]/g, "_")}.py`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Generate runnable Python standalone code matching simulation state
  const getPythonCodeSnippet = () => {
    return `#!/usr/bin/env python3
"""
MetalliX HPC Subsystem: 3D Marangoni Flow Instability & Gas Entrapment Solver
Material: ${selectedMaterial}
Laser Power: ${laserPower_W} W | Scan Speed: ${scanSpeed_mms} mm/s | Beam Ø: ${beamDiameter_um} µm
Surfactant Sulfur: ${surfactantSulfur_ppm} ppm | Shielding Gas: ${shieldingGas}
"""

import numpy as np
import math

def solve_marangoni_gas_entrapment():
    # 1. Thermophysical & Surfactant Constants
    laser_power_W = ${laserPower_W}
    scan_speed_m_s = ${scanSpeed_mms} / 1000.0
    r0_m = (${beamDiameter_um} / 2.0) * 1e-6
    preheat_T0_K = ${preheatTemp_C} + 273.15
    sulfur_ppm = ${surfactantSulfur_ppm}

    # Material properties for ${selectedMaterial}
    liquidus_K = ${currentAlloy.liquidus_C} + 273.15
    solidus_K = ${currentAlloy.solidus_C} + 273.15
    rho = ${currentAlloy.density_kg_m3}
    mu = ${currentAlloy.viscosity_Pa_s}
    gamma_0 = ${currentAlloy.surfaceTension_N_m}
    d_gamma_dT_pure = ${currentAlloy.d_gamma_dT_pure}

    # Sahoo-DebRoy surfactant activity formulation
    d_gamma_dT = d_gamma_dT_pure + sulfur_ppm * 0.000035

    # 2. Peak Temperature & Marangoni Velocity
    delta_T_peak = 1250.0  # Peak thermal excursion
    u_Ma = math.sqrt(abs(d_gamma_dT) * delta_T_peak / rho) * 2.8

    # 3. Dimensionless Numbers
    char_length_L = 60e-6
    alpha_th = 29.0 / (rho * 730.0)
    Ma = (abs(d_gamma_dT) * delta_T_peak * char_length_L) / (mu * alpha_th)
    Ma_crit = ${currentAlloy.critical_Ma}
    instability_ratio = Ma / Ma_crit

    print(f"=== MARANGONI HYDRODYNAMICS ===")
    print(f"Effective dγ/dT: {d_gamma_dT:+.6f} N/(m·K)")
    print(f"Peak Marangoni Velocity u_Ma: {u_Ma:.2f} m/s")
    print(f"Marangoni Number Ma: {Ma:.0f} (Critical: {Ma_crit:.0f}, Instability: {instability_ratio:.2f}x)")

    # 4. 3D Gas Entrapment Heatmap Discretization
    Nx, Ny, Nz = 24, 16, 12
    x_grid = np.linspace(-180, 80, Nx)  # µm
    y_grid = np.linspace(-60, 60, Ny)   # µm
    z_grid = np.linspace(-85, 0, Nz)    # µm

    pore_prob_heatmap = np.zeros((Nx, Ny, Nz))
    for i, x in enumerate(x_grid):
        for j, y in enumerate(y_grid):
            for k, z in enumerate(z_grid):
                r_norm = math.sqrt((x/180)**2 + (y/60)**2 + (z/85)**2)
                if r_norm < 1.0:
                    vortex_zone = math.exp(-3.5 * ((x/180 + 0.45)**2)) * math.exp(-3.0 * ((y/60)**2))
                    p_pore = (0.5 * vortex_zone + 0.3 * min(1.0, instability_ratio)) * 100.0
                    pore_prob_heatmap[i, j, k] = min(98.0, max(1.0, p_pore))

    high_risk_voxels = np.sum(pore_prob_heatmap > 60.0)
    rel_density = max(98.5, 100.0 - (high_risk_voxels / (Nx*Ny*Nz)) * 1.5)
    print(f"Predicted Relative Density: {rel_density:.2f}%")
    print(f"High Entrapment Risk Voxels: {high_risk_voxels} / {Nx*Ny*Nz}")

if __name__ == "__main__":
    solve_marangoni_gas_entrapment()
`;
  };

  return (
    <div className="space-y-4">
      {/* Top Banner & Control Deck */}
      <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 sm:p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-cyan-500/10 via-blue-500/5 to-transparent blur-3xl pointer-events-none" />

        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 relative z-10">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-cyan-500 via-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-[0_0_30px_rgba(6,182,212,0.4)] border border-cyan-400/40 shrink-0">
              <Waves className="w-6 h-6" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                  3D Marangoni Flow Instability &amp; Gas Entrapment Pore Heatmap Lab
                </h2>
                <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/40 font-bold font-mono">
                  Python 3.10 HPC + 3D WebGL
                </span>
                <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-400/30 font-bold font-mono">
                  Sahoo-DebRoy &amp; Keene Model
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                Simulates thermocapillary Marangoni vortex rolls, surfactant (d&gamma;/dT) flow inversion, vortex shear instability, and calculates a 3D spatial probability heatmap P(pore, x, y, z) of gas entrapment defects.
              </p>
            </div>
          </div>

          {/* Action Header Buttons */}
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={runSimulation}
              disabled={isRunningSim}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white text-xs font-bold font-mono transition flex items-center gap-2 shadow-[0_0_20px_rgba(6,182,212,0.35)] disabled:opacity-50"
            >
              {isRunningSim ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              <span>{isRunningSim ? "Solving 3D Navier-Stokes..." : "Run Python Simulation"}</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveCodeTab(activeCodeTab === "viewer" ? "python-source" : "viewer")}
              className={`px-3 py-2.5 rounded-xl border text-xs font-mono font-bold transition flex items-center gap-1.5 ${
                activeCodeTab === "python-source"
                  ? "bg-purple-500/20 text-purple-200 border-purple-400/50 shadow-[0_0_15px_rgba(168,85,247,0.3)]"
                  : "bg-[#050810] text-slate-300 border-[#1e2d46] hover:border-cyan-400/40"
              }`}
            >
              <Terminal className="w-4 h-4 text-purple-400" />
              <span>Python Source</span>
            </button>
          </div>
        </div>

        {/* Material Presets Selector Bar */}
        <div className="mt-5 pt-4 border-t border-[#162032] flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
            <span className="text-slate-400 font-semibold font-mono">Alloy:</span>
            {MARANGONI_ALLOYS.map((alloy) => (
              <button
                key={alloy.id}
                type="button"
                onClick={() => {
                  setSelectedMaterial(alloy.name);
                  setLaserPower_W(alloy.recPower_W);
                  setScanSpeed_mms(alloy.recSpeed_mms);
                  setSurfactantSulfur_ppm(alloy.defaultSulfur_ppm);
                }}
                className={`px-3 py-1.5 rounded-lg whitespace-nowrap transition text-[11px] font-mono flex items-center gap-1.5 ${
                  selectedMaterial === alloy.name
                    ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/50 font-bold shadow-[0_0_12px_rgba(6,182,212,0.25)]"
                    : "bg-[#050810] text-slate-400 hover:text-white border border-[#1e2d46]"
                }`}
              >
                <span>{alloy.name}</span>
                {alloy.id === "ss316l" && (
                  <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-normal">
                    Flow Inversion Prone
                  </span>
                )}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 font-mono text-[11px] text-slate-400">
            <span>Shielding Gas:</span>
            {["Argon (Ar)", "Helium (He)", "Nitrogen (N2)"].map((gas) => (
              <button
                key={gas}
                type="button"
                onClick={() => setShieldingGas(gas)}
                className={`px-2.5 py-1 rounded-lg border transition ${
                  shieldingGas === gas
                    ? "bg-blue-500/20 text-blue-200 border-blue-400/50 font-bold"
                    : "bg-[#050810] text-slate-400 border-[#1e2d46]"
                }`}
              >
                {gas.split(" ")[0]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Grid: Left 3D Viewport & Terminal, Right Process Parameter Sliders & KPIs */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (8 Cols): 3D Viewport or Python Source */}
        <div className="lg:col-span-8 space-y-4">
          {activeCodeTab === "viewer" ? (
            <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-4 space-y-3 relative shadow-xl">
              {/* Top Viewport Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs border-b border-[#162032] pb-3">
                {/* Scalar Field Switcher */}
                <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
                  <span className="text-slate-400 font-mono text-[11px] mr-1 flex items-center gap-1">
                    <Eye className="w-3 h-3 text-cyan-400" />
                    <span>Field:</span>
                  </span>
                  {[
                    { id: "pore-prob", label: "Pore Probability P(x,y,z)", color: "cyan" },
                    { id: "temperature", label: "Temperature T(x,y,z)", color: "rose" },
                    { id: "velocity", label: "Velocity |u|", color: "blue" },
                    { id: "downward-drag", label: "Downward Drag (uz)", color: "amber" },
                    { id: "vorticity", label: "Vorticity |ω|", color: "purple" },
                  ].map((field) => (
                    <button
                      key={field.id}
                      type="button"
                      onClick={() => setDisplayScalar(field.id as any)}
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-mono whitespace-nowrap transition ${
                        displayScalar === field.id
                          ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/50 font-bold shadow-[0_0_10px_rgba(6,182,212,0.2)]"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {field.label}
                    </button>
                  ))}
                </div>

                {/* Camera Preset Quick Buttons */}
                <div className="flex items-center gap-1 font-mono text-[11px]">
                  <span className="text-slate-500 mr-1">Camera:</span>
                  {(["iso", "top", "side", "front"] as const).map((cam) => (
                    <button
                      key={cam}
                      type="button"
                      onClick={() => setCameraPreset(cam)}
                      className="px-2 py-0.5 rounded bg-[#050810] border border-[#1e2d46] hover:border-cyan-400 text-slate-400 hover:text-white uppercase text-[10px]"
                    >
                      {cam}
                    </button>
                  ))}
                </div>
              </div>

              {/* 3D WebGL Canvas */}
              <div
                ref={mountRef}
                className="w-full h-[470px] rounded-xl overflow-hidden cursor-grab active:cursor-grabbing relative bg-[#050810] border border-[#162032]"
              >
                {/* Overlay Scale Bar */}
                <div className="absolute top-3 right-3 bg-[#090e18]/90 backdrop-blur border border-[#1e2d46] p-2.5 rounded-xl text-[10px] text-slate-300 space-y-1 pointer-events-none shadow-lg z-10 font-mono">
                  <div className="flex items-center justify-between gap-4 font-bold text-cyan-300 uppercase text-[9px]">
                    <span>{displayScalar.replace("-", " ")}</span>
                    <span>
                      {displayScalar === "pore-prob"
                        ? "0 – 100%"
                        : displayScalar === "temperature"
                        ? `${preheatTemp_C} – ${simResult?.meltPoolGeometry.peakTemp_C || 2400}°C`
                        : displayScalar === "velocity"
                        ? `0 – ${simResult?.marangoniHydrodynamics.peakVelocity_m_s || 3.5} m/s`
                        : "Scalar Range"}
                    </span>
                  </div>
                  <div className="w-36 h-2.5 rounded-full bg-gradient-to-r from-blue-600 via-cyan-400 via-yellow-400 to-red-600 border border-white/20" />
                  <div className="flex justify-between text-[8px] text-slate-400">
                    <span>Safe / Low</span>
                    <span>Critical Peak</span>
                  </div>
                </div>

                {/* Bottom Left Navigation Hint */}
                <div className="absolute bottom-3 left-3 bg-[#090e18]/85 backdrop-blur border border-[#1e2d46] px-3 py-1.5 rounded-xl text-[10px] text-slate-400 flex items-center gap-2 pointer-events-none font-mono">
                  <Compass className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Orbit: Drag Mouse • Zoom: Scroll • Laser Vector: +Z</span>
                </div>
              </div>

              {/* Viewport Slicing & Filter Sliders Bar */}
              <div className="p-3.5 bg-[#050810] border border-[#162032] rounded-xl flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
                {/* Voxel Filter */}
                <div className="flex items-center gap-2 flex-1 min-w-[200px]">
                  <Filter className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  <span className="text-slate-400 text-[11px] whitespace-nowrap">
                    Min Prob Threshold: <strong className="text-cyan-300">{minProbThreshold}%</strong>
                  </span>
                  <input aria-label="Min Prob Threshold"
                    type="range"
                    min="0"
                    max="80"
                    step="5"
                    value={minProbThreshold}
                    onChange={(e) => setMinProbThreshold(parseInt(e.target.value))}
                    className="w-full accent-cyan-400 cursor-pointer"
                  />
                </div>

                {/* Slicing Plane Selector */}
                <div className="flex items-center gap-2">
                  <span className="text-slate-400 text-[11px]">Slice Plane:</span>
                  {(["none", "xy-top", "xz-longitudinal", "yz-transverse"] as const).map((plane) => (
                    <button
                      key={plane}
                      type="button"
                      onClick={() => setSlicePlane(plane)}
                      className={`px-2 py-1 rounded text-[10px] border ${
                        slicePlane === plane
                          ? "bg-cyan-500/20 text-cyan-300 border-cyan-400/50 font-bold"
                          : "bg-[#090e18] text-slate-400 border-[#1e2d46]"
                      }`}
                    >
                      {plane.replace("-", " ")}
                    </button>
                  ))}
                </div>

                {/* Toggles */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowStreamlines(!showStreamlines)}
                    className={`px-2 py-1 rounded text-[10px] border transition ${
                      showStreamlines
                        ? "bg-blue-500/20 text-blue-300 border-blue-400/50"
                        : "bg-[#090e18] text-slate-500 border-[#1e2d46]"
                    }`}
                  >
                    Vortex Streamlines
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowPoreSpheres(!showPoreSpheres)}
                    className={`px-2 py-1 rounded text-[10px] border transition ${
                      showPoreSpheres
                        ? "bg-rose-500/20 text-rose-300 border-rose-400/50"
                        : "bg-[#090e18] text-slate-500 border-[#1e2d46]"
                    }`}
                  >
                    Gas Pores
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* Python Source Code Window */
            <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-4 space-y-3 shadow-xl">
              <div className="flex items-center justify-between border-b border-[#162032] pb-3 text-xs font-mono">
                <div className="flex items-center gap-2 text-cyan-400">
                  <Terminal className="w-4 h-4" />
                  <span className="font-bold">marangoni_pore_instability_solver.py</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleCopyCode}
                    className="px-2.5 py-1 rounded bg-[#050810] border border-[#1e2d46] hover:border-cyan-400 text-slate-300 text-[11px] flex items-center gap-1 transition"
                  >
                    {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-cyan-400" />}
                    <span>{isCopied ? "Copied" : "Copy Code"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleDownloadCode}
                    className="px-2.5 py-1 rounded bg-[#050810] border border-[#1e2d46] hover:border-cyan-400 text-slate-300 text-[11px] flex items-center gap-1 transition"
                  >
                    <Download className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Download .py</span>
                  </button>
                </div>
              </div>

              <pre className="p-4 bg-[#050810] border border-[#162032] rounded-xl text-xs font-mono text-emerald-300 overflow-x-auto h-[480px] leading-relaxed">
                {getPythonCodeSnippet()}
              </pre>
            </div>
          )}

          {/* Live Solver Terminal Output Console */}
          <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-4 space-y-2 font-mono text-xs shadow-xl">
            <div className="flex items-center justify-between text-slate-400 border-b border-[#162032] pb-2">
              <span className="flex items-center gap-1.5 text-cyan-400 font-bold">
                <Activity className="w-3.5 h-3.5" />
                <span>Python Solver Terminal Output</span>
              </span>
              <span className="text-[10px] text-slate-500">
                Engine: {simResult?.engine || "CPython 3.10+"} | Status: Ready
              </span>
            </div>

            <div className="bg-[#050810] p-3 rounded-xl border border-[#162032] h-28 overflow-y-auto text-[11px] space-y-1 text-slate-300">
              {consoleLogs.length > 0 ? (
                consoleLogs.map((log, idx) => (
                  <div
                    key={idx}
                    className={`${
                      log.includes("[ERROR]")
                        ? "text-rose-400"
                        : log.includes("[SUCCESS]") || log.includes("[CONVERGED]")
                        ? "text-emerald-400 font-bold"
                        : log.includes("[HYDRODYNAMICS]") || log.includes("[POROSITY]")
                        ? "text-cyan-300"
                        : "text-slate-400"
                    }`}
                  >
                    {log}
                  </div>
                ))
              ) : (
                <div className="text-slate-500">Click &quot;Run Python Simulation&quot; to initialize solver.</div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column (4 Cols): Process Knobs, Surfactant Inversion & Keyframe KPIs */}
        <div className="lg:col-span-4 space-y-4">
          {/* Key Hydrodynamic & Defect KPIs (4 Cards) */}
          <div className="grid grid-cols-2 gap-2.5 font-mono">
            {/* 1. Relative Density */}
            <div className="p-3.5 bg-[#090e18] border border-[#1e2d46] rounded-xl space-y-1">
              <span className="text-slate-400 text-[10px] uppercase font-bold block">Relative Density:</span>
              <span
                className={`text-xl font-bold block ${
                  (simResult?.porosityPrediction.relativeDensity_pct || 99.8) >= 99.7
                    ? "text-emerald-400"
                    : (simResult?.porosityPrediction.relativeDensity_pct || 99.8) >= 99.3
                    ? "text-amber-400"
                    : "text-rose-400"
                }`}
              >
                {simResult?.porosityPrediction.relativeDensity_pct || 99.82}%
              </span>
              <span className="text-[10px] text-slate-500">
                Pore Vol: {simResult?.porosityPrediction.poreVolumeFraction_pct || 0.18}%
              </span>
            </div>

            {/* 2. Marangoni Number Ma */}
            <div className="p-3.5 bg-[#090e18] border border-[#1e2d46] rounded-xl space-y-1">
              <span className="text-slate-400 text-[10px] uppercase font-bold block">Marangoni Number:</span>
              <span className="text-xl font-bold text-cyan-400 block">
                {simResult?.marangoniHydrodynamics.marangoniNumber_Ma.toLocaleString() || "4,820"}
              </span>
              <span className="text-[10px] text-slate-500">
                Crit: {simResult?.marangoniHydrodynamics.criticalMarangoni_Ma_crit.toLocaleString() || "4,500"}
              </span>
            </div>

            {/* 3. Instability Ratio */}
            <div className="p-3.5 bg-[#090e18] border border-[#1e2d46] rounded-xl space-y-1">
              <span className="text-slate-400 text-[10px] uppercase font-bold block">Instability Ratio:</span>
              <span
                className={`text-lg font-bold block ${
                  (simResult?.marangoniHydrodynamics.instabilityRatio || 1.0) > 1.4
                    ? "text-rose-400"
                    : (simResult?.marangoniHydrodynamics.instabilityRatio || 1.0) > 1.0
                    ? "text-amber-400"
                    : "text-emerald-400"
                }`}
              >
                {simResult?.marangoniHydrodynamics.instabilityRatio || 1.07}x
              </span>
              <span className="text-[10px] text-slate-500">Ma / Ma_crit</span>
            </div>

            {/* 4. Peak Marangoni Velocity */}
            <div className="p-3.5 bg-[#090e18] border border-[#1e2d46] rounded-xl space-y-1">
              <span className="text-slate-400 text-[10px] uppercase font-bold block">Peak Marangoni Velocity:</span>
              <span className="text-lg font-bold text-blue-400 block">
                {simResult?.marangoniHydrodynamics.peakVelocity_m_s || 3.15} m/s
              </span>
              <span className="text-[10px] text-slate-500">Hydrodynamic roll speed</span>
            </div>
          </div>

          {/* Process Controls Box */}
          <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4 shadow-xl font-mono">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Sliders className="w-4 h-4 text-cyan-400" />
              <span>Hydrodynamic Process Knobs</span>
            </h3>

            {/* Laser Power Slider */}
            <div className="p-3 bg-[#050810] rounded-xl border border-[#1e2d46] space-y-1.5">
              <div className="flex justify-between text-xs text-slate-300">
                <span>Laser Power (P):</span>
                <span className="text-cyan-400 font-bold">{laserPower_W} W</span>
              </div>
              <input aria-label="Laser Power (P)"
                type="range"
                min="100"
                max="600"
                step="10"
                value={laserPower_W}
                onChange={(e) => setLaserPower_W(parseFloat(e.target.value))}
                className="w-full accent-cyan-400 cursor-pointer"
              />
            </div>

            {/* Scan Speed Slider */}
            <div className="p-3 bg-[#050810] rounded-xl border border-[#1e2d46] space-y-1.5">
              <div className="flex justify-between text-xs text-slate-300">
                <span>Scan Speed (v):</span>
                <span className="text-blue-400 font-bold">{scanSpeed_mms} mm/s</span>
              </div>
              <input aria-label="Scan Speed (v)"
                type="range"
                min="400"
                max="2400"
                step="50"
                value={scanSpeed_mms}
                onChange={(e) => setScanSpeed_mms(parseFloat(e.target.value))}
                className="w-full accent-blue-400 cursor-pointer"
              />
            </div>

            {/* Beam Spot Diameter */}
            <div className="p-3 bg-[#050810] rounded-xl border border-[#1e2d46] space-y-1.5">
              <div className="flex justify-between text-xs text-slate-300">
                <span>Beam Diameter (2r₀):</span>
                <span className="text-purple-400 font-bold">{beamDiameter_um} µm</span>
              </div>
              <input aria-label="Beam Diameter (2r₀)"
                type="range"
                min="50"
                max="160"
                step="5"
                value={beamDiameter_um}
                onChange={(e) => setBeamDiameter_um(parseFloat(e.target.value))}
                className="w-full accent-purple-400 cursor-pointer"
              />
            </div>

            {/* Surfactant Sulfur Activity Slider (Crucial for flow inversion) */}
            <div className="p-3 bg-[#050810] rounded-xl border border-[#1e2d46] space-y-1.5">
              <div className="flex justify-between text-xs text-slate-300">
                <span className="flex items-center gap-1">
                  <span>Surfactant Sulfur:</span>
                  <Info className="w-3 h-3 text-amber-400" />
                </span>
                <span
                  className={`font-bold ${
                    (simResult?.marangoniHydrodynamics.effective_d_gamma_dT_N_mK || -0.0004) > 0
                      ? "text-rose-400"
                      : "text-emerald-400"
                  }`}
                >
                  {surfactantSulfur_ppm} ppm
                  <span className="text-[10px] ml-1 text-slate-500 font-normal">
                    (dγ/dT: {(simResult?.marangoniHydrodynamics.effective_d_gamma_dT_N_mK || -0.0004).toFixed(5)})
                  </span>
                </span>
              </div>
              <input aria-label="Surfactant Sulfur"
                type="range"
                min="2"
                max="100"
                step="2"
                value={surfactantSulfur_ppm}
                onChange={(e) => setSurfactantSulfur_ppm(parseFloat(e.target.value))}
                className="w-full accent-amber-400 cursor-pointer"
              />
              <div className="flex justify-between text-[9px] text-slate-500">
                <span>2 ppm (Pure Outward)</span>
                <span>Inversion Boundary</span>
                <span>100 ppm (Deep Inward)</span>
              </div>
            </div>

            {/* Flow Mode Status Badge */}
            <div className="p-3 rounded-xl bg-[#050810] border border-[#1e2d46] space-y-1 text-xs">
              <span className="text-slate-400 text-[10px] block">Marangoni Flow Mode:</span>
              <div className="flex items-center gap-2 font-bold text-slate-200">
                {(simResult?.marangoniHydrodynamics.effective_d_gamma_dT_N_mK || -0.0004) > 0 ? (
                  <span className="text-amber-400 flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Inward Centripetal Jet (dγ/dT &gt; 0)</span>
                  </span>
                ) : (
                  <span className="text-cyan-300 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Outward Convective Rolls (dγ/dT &lt; 0)</span>
                  </span>
                )}
              </div>
              <p className="text-[10px] text-slate-400 font-sans leading-snug pt-1">
                {(simResult?.marangoniHydrodynamics.effective_d_gamma_dT_N_mK || -0.0004) > 0
                  ? "Positive surface tension gradient drags liquid toward the center, creating a deep downward convective vortex that pulls shielding gas bubbles into the bottom mushy zone."
                  : "Negative surface tension gradient drives outward fluid rolls toward cooler edges, facilitating bubble escape."}
              </p>
            </div>
          </div>

          {/* AI Defect Mitigation Guidance */}
          <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-4 space-y-2.5 shadow-xl text-xs font-sans">
            <span className="font-bold text-white flex items-center gap-1.5 font-mono">
              <Shield className="w-4 h-4 text-cyan-400" />
              <span>Marangoni Defect Mitigation Protocol</span>
            </span>

            <div className="space-y-2 text-[11px] text-slate-300">
              {simResult?.mitigationRecommendations.map((rec, i) => (
                <div key={i} className="p-2.5 rounded-lg bg-[#050810] border border-[#162032] flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
